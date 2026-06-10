# orchestrator/pipeline.py — FULL REPLACEMENT

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta

from pymongo import MongoClient
from google.adk.agents import SequentialAgent, ParallelAgent
from google import adk

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agent import root_agent
from config import config


def get_db():
    client = MongoClient(config.MONGODB_URI)
    return client[config.DB_NAME], client


def build_prompt(region_id: str, session_id: str, demo_week: int = None) -> str:
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    week = now.isocalendar()[1]

    now_iso          = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    seven_ago_iso    = seven_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    if demo_week:
        signal_instruction = (
            f"Query the 'signals' collection with filter: "
            f"{{\"demo_tag\": \"sars_replay\", \"demo_week\": {demo_week}}}. "
            f"Do NOT filter by timestamp for demo data."
        )
    else:
        signal_instruction = (
            f"Query the 'signals' collection with filter: "
            f"{{\"metadata.region_id\": \"{region_id}\", "
            f"\"timestamp\": {{\"$gte\": \"{seven_ago_iso}\"}}}}."
        )

    return f"""
Run EWARS epidemic surveillance pipeline.

PRE-COMPUTED VALUES — use these directly, do not recalculate:
  region_id:        {region_id}
  session_id:       {session_id}
  now:              {now_iso}
  seven_days_ago:   {seven_ago_iso}
  current_week:     {week}
  database:         ewars_db

CRITICAL: Do NOT call now(), datetime(), timedelta() — these are not tools.
CRITICAL: Do NOT ask the user for data — all data is in MongoDB already.
CRITICAL: Use only these MongoDB tool names: find, aggregate, count,
          list-collections, list-databases

SIGNAL DATA: {signal_instruction}

BASELINES: Query collection 'baselines' with filter:
  {{"region_id": "{region_id}", "week_of_year": {week}}}

EXECUTE pipeline stages in this order and return results as JSON:
  Stage 1 — Signal summary: count signals, list syndrome codes found
  Stage 2 — Syndromic analysis: compare to baselines, detect anomalies
  Stage 3 — Geo clustering: identify geographic clusters from signal locations
  Stage 4 — Environmental: call fetch_weather for cluster centroids
  Stage 5 — Risk classification: calculate composite score, assign tier
  Stage 6 — SitRep: only if tier is ALERT or EMERGENCY

Final output must include:
  threat_tier: WATCH | ALERT | EMERGENCY
  composite_score: 0-100
  syndromic_score: 0-100
  geo_score: 0-100
  environmental_score: 0-100
  escalation_rationale: plain English explanation
"""


async def run_pipeline_async(region_id: str, session_id: str,
                              demo_week: int = None) -> dict:
    """
    Runs the ADK pipeline and returns structured results.
    Python orchestrator handles all MongoDB writes.
    """
    prompt = build_prompt(region_id, session_id, demo_week)

    session_svc = adk.sessions.InMemorySessionService()
    session = await session_svc.create_session(
        app_name="ewars_pipeline",
        user_id="ewars_system",
    )
    runner = adk.Runner(
        agent=root_agent,
        app_name="ewars_pipeline",
        session_service=session_svc,
    )

    final_text = ""
    async for event in runner.run_async(
        user_id="ewars_system",
        session_id=session.id,
        new_message=adk.types.Content(
            role="user",
            parts=[adk.types.Part(text=prompt)],
        ),
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text = part.text

    # Extract threat tier from response
    tier = "WATCH"
    if "EMERGENCY" in final_text.upper():
        tier = "EMERGENCY"
    elif "ALERT" in final_text.upper():
        tier = "ALERT"

    # Python writes results to MongoDB (not the agent)
    db, client = get_db()
    try:
        assessment_id = str(uuid.uuid4())
        db.threat_assessments.insert_one({
            "assessment_id": assessment_id,
            "session_id": session_id,
            "region_id": region_id,
            "demo_week": demo_week,
            "assessed_at": datetime.now(timezone.utc),
            "threat_tier": tier,
            "agent_response_summary": final_text[:2000],
        })

        sitrep_id = None
        if tier in ("ALERT", "EMERGENCY"):
            sitrep_id = str(uuid.uuid4())
            db.situation_reports.insert_one({
                "sitrep_id": sitrep_id,
                "assessment_id": assessment_id,
                "session_id": session_id,
                "region_id": region_id,
                "generated_at": datetime.now(timezone.utc),
                "threat_tier": tier,
                "report": {
                    "executive_summary": final_text[:500],
                    "full_response": final_text,
                },
                "status": "draft",
                "reviewed_by": None,
            })
    finally:
        client.close()

    return {
        "session_id": session_id,
        "status": "completed",
        "threat_tier": tier,
        "sitrep_id": sitrep_id,
        "response_preview": final_text[:300],
    }


def run_ewars_pipeline(region_id: str, session_id: str,
                        demo_week: int = None) -> dict:
    """Synchronous wrapper for use in FastAPI and tests."""
    return asyncio.run(run_pipeline_async(region_id, session_id, demo_week))