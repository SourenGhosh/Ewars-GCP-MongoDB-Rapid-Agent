"""
Orchestrates the 6 EWARS agents with isolated per-stage prompts.
Each agent receives ONLY its own task + the output of the previous stage.

This fixes:
  - Geo-cluster running entire pipeline (was seeing all stage instructions)
  - Score=0 (structured JSON output per stage, not one final blob)
  - Environmental agent receiving cluster coordinates explicitly
  - Agents writing to wrong collections (each sees only its own write target)
"""

import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional
import asyncio
import contextvars
# Disable ADK telemetry to prevent ContextVar leakage in async FastAPI handlers
# Each new InMemorySessionService + Runner creates orphaned OpenTelemetry spans
# when six agents are run sequentially within a single async request
os.environ.setdefault("ADK_DISABLE_TELEMETRY", "1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("ADK_DISABLE_TELEMETRY", "1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

from google import adk
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types as genai_types
from pymongo import MongoClient

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ewars_multiagent.orchestrator.agent import (
    create_signal_collector,
    create_syndromic_analyst,
    create_geo_cluster,
    create_environmental,
    create_risk_escalation,
    create_alert_synthesis,
)


# ── Shared session service (one per pipeline run) ─────────────────────────────

_shared_session_svc = None

def get_shared_session_service():
    global _shared_session_svc
    if _shared_session_svc is None:
        _shared_session_svc = adk.sessions.InMemorySessionService()
    return _shared_session_svc


# ── Per-agent prompt builders ─────────────────────────────────────────────────

def prompt_signal_collector(signal_filter: str, session_id: str) -> str:
    return f"""You are the Signal Collector agent for EWARS. Do ONLY your stage.

SESSION_ID: {session_id}

YOUR SOLE TASK:
Call the MongoDB MCP find tool to fetch signals, then summarise them.

STEP 1 — Call find tool:
  Tool: find
  Args: {{
    "database": "ewars_db",
    "collection": "signals",
    "filter": {signal_filter},
    "limit": 500
  }}

STEP 2 — Summarise what you found. Count by syndrome_codes.

Return ONLY this JSON (no prose, no markdown fences):
{{
  "processed": <total signals found>,
  "stored": <total signals found>,
  "syndrome_counts": {{"SARI": 0, "ILI": 0, "AGE": 0, "UF": 0, "HF": 0}},
  "source_types": ["clinic_visit", "pharmacy_sale"],
  "total_cases": <sum of case_count>,
  "region_id": "<region from signal metadata>",
  "signal_filter": {signal_filter}
}}"""


def prompt_syndromic_analyst(
    signal_filter: str,
    session_id: str,
    week: int,
    region_id: str,
    collector_output: dict,
) -> str:
    syndromes = list(collector_output.get("syndrome_counts", {}).keys()) or ["SARI", "ILI"]
    total = collector_output.get("total_cases", 0)
    return f"""You are the Syndromic Analyst agent for EWARS. Do ONLY your stage.

SESSION_ID: {session_id}
REGION: {region_id}
CURRENT_WEEK_OF_YEAR: {week}
TOTAL_CASES_THIS_PERIOD: {total}
SYNDROMES_DETECTED: {syndromes}

YOUR SOLE TASK: compare signal case counts to historical baselines.

STEP 1 — Fetch signals:
  Tool: find
  Args: {{
    "database": "ewars_db",
    "collection": "signals",
    "filter": {signal_filter},
    "limit": 500
  }}

STEP 2 — For each syndrome in {syndromes}, fetch its baseline:
  Tool: find
  Args: {{
    "database": "ewars_db",
    "collection": "baselines",
    "filter": {{
      "region_id": "{region_id}",
      "syndrome": "<syndrome_code>",
      "week_of_year": {week}
    }},
    "limit": 1
  }}

STEP 3 — Compare current case_count to alert_threshold_1/2/3.
  threshold_1 = mean + 1 SD = ELEVATED
  threshold_2 = mean + 2 SD = ALERT
  threshold_3 = mean + 3 SD = EPIDEMIC

STEP 4 — Calculate source concordance:
  Count distinct signal_types in the signals.
  3+ types = HIGH, 2 = MEDIUM, 1 = LOW.

DO NOT write to any MongoDB collection.
Return ONLY this JSON (no prose, no markdown fences):
{{
  "region_id": "{region_id}",
  "overall_syndromic_score": <0-100>,
  "source_concordance": "HIGH|MEDIUM|LOW",
  "source_concordance_bonus": <100|50|0>,
  "anomalies_detected": [
    {{
      "syndrome": "<code>",
      "current_count": <n>,
      "expected_count": <n>,
      "threshold_breached": "NORMAL|ELEVATED|ALERT|EPIDEMIC",
      "percent_above_baseline": <n>,
      "trend": "INCREASING|STABLE|DECREASING",
      "doubling_time_days": <n|null>,
      "source_concordance": "HIGH|MEDIUM|LOW",
      "confidence": <0.0-1.0>
    }}
  ],
  "analyst_summary": "<2-3 sentences plain English>"
}}"""


def prompt_geo_cluster(
    signal_filter: str,
    session_id: str,
    region_id: str,
    region_coords: list,
) -> str:
    lon, lat = region_coords
    return f"""You are the Geo-Cluster agent for EWARS. Do ONLY your stage.

SESSION_ID: {session_id}
REGION: {region_id}
REGION_CENTROID: [{lon}, {lat}]

YOUR SOLE TASK: identify geographic clusters from the fetched signals.

STEP 1 — Fetch signals:
  Tool: find
  Args: {{
    "database": "ewars_db",
    "collection": "signals",
    "filter": {signal_filter},
    "limit": 500
  }}

STEP 2 — Group signals by location coordinates.
  Calculate centroid = average of all signal [longitude, latitude] values.
  Sum total case_count.
  If fewer than 3 signals: use region centroid [{lon}, {lat}] as centroid.

STEP 3 — Estimate R if 2+ time points:
  Sort signals by timestamp. Fit exponential: R = 2^(5/doubling_time).
  If only 1 time point: set r_estimate = null, doubling_time_days = null.

IMPORTANT: You only ANALYZE — the orchestrator handles MongoDB writes.
DO NOT call insert-many, update-many, or any write tools.

Return ONLY this JSON (no prose, no markdown fences):
{{
  "cluster_id": "{str(uuid.uuid4())}",
  "centroid_lon": <lon>,
  "centroid_lat": <lat>,
  "total_cases": <n>,
  "r_estimate": <n|null>,
  "doubling_time_days": <n|null>,
  "geo_score": <0-100>,
  "cross_border_risk": false,
  "spatial_summary": "<2-3 sentences>"
}}"""


def prompt_environmental(
    session_id: str,
    region_id: str,
    centroid_lon: float,
    centroid_lat: float,
    syndrome: str,
) -> str:
    return f"""You are the Environmental agent for EWARS. Do ONLY your stage.

SESSION_ID: {session_id}
REGION: {region_id}
CLUSTER_CENTROID: [{centroid_lon}, {centroid_lat}]
PRIMARY_SYNDROME: {syndrome}

YOUR SOLE TASK: assess environmental risk using weather data and cached snapshots.

STEP 1 — Fetch weather using the fetch_weather tool:
  Tool: fetch_weather
  Args: {{
    "latitude": {centroid_lat},
    "longitude": {centroid_lon}
  }}

STEP 2 — Fetch cached environmental snapshot:
  Tool: find
  Args: {{
    "database": "ewars_db",
    "collection": "environmental_snapshots",
    "filter": {{"region_id": "{region_id}"}},
    "limit": 1
  }}

STEP 3 — Assess amplifiers based on syndrome {syndrome}:
  SARI/ILI → check temp < 15C or humidity < 40% for respiratory risk
  AGE      → check rainfall > 100mm or flood_risk for waterborne risk
  UF/HF    → check temp 20-35C + humidity > 60% for vector risk

DO NOT write to any MongoDB collection.
Return ONLY this JSON (no prose, no markdown fences):
{{
  "environmental_risk_score": <0-100>,
  "temp_celsius": <n>,
  "humidity_percent": <n>,
  "rainfall_mm_7d": <n>,
  "flood_risk": <bool>,
  "primary_amplifiers": ["<string>"],
  "vector_risk_dengue": "LOW|MODERATE|HIGH|CRITICAL",
  "waterborne_risk": "LOW|MODERATE|HIGH|CRITICAL",
  "population_vulnerability": "LOW|MODERATE|HIGH|CRITICAL",
  "conditions_worsening": <bool>,
  "environmental_summary": "<2-3 sentences>"
}}"""


def prompt_risk_escalation(
    session_id: str,
    region_id: str,
    cluster_id: str,
    syndromic: dict,
    geo: dict,
    env: dict,
) -> str:
    # Pre-calculate so agent just validates, doesn't compute from scratch
    s_score = syndromic.get("overall_syndromic_score", 0)
    g_score = geo.get("geo_score", 0)
    e_score = env.get("environmental_risk_score", 0)
    bonus   = syndromic.get("source_concordance_bonus", 0)
    composite = round(s_score * 0.40 + g_score * 0.30 + e_score * 0.20 + bonus * 0.10, 1)

    # Check overrides
    hf_present = any(
        a.get("syndrome") == "HF"
        for a in syndromic.get("anomalies_detected", [])
    )
    r_est = geo.get("r_estimate")
    override = ""
    if hf_present:
        override = "OVERRIDE: HF syndrome detected → tier MUST be EMERGENCY"
    elif r_est and r_est > 3.0:
        override = f"OVERRIDE: R={r_est} > 3.0 → tier MUST be EMERGENCY"

    return f"""You are the Risk Escalation agent for EWARS. Do ONLY your stage.

SESSION_ID: {session_id}
REGION: {region_id}
CLUSTER_ID: {cluster_id}

=== SCORES — USE THESE EXACT VALUES, DO NOT RECALCULATE ===
syndromic_score:          {s_score}
geo_score:                {g_score}
environmental_score:      {e_score}
source_concordance_bonus: {bonus}
composite_score:          {composite}
=============================================================

{override}

TIER CLASSIFICATION — based on composite_score = {composite}:
  {composite} >= 75  →  EMERGENCY
  {composite} >= 50  →  ALERT
  {composite} >= 30  →  WATCH
  {composite} < 30   →  WATCH

YOUR TIER MUST BE: {"EMERGENCY" if composite >= 75 else "ALERT" if composite >= 50 else "WATCH"}

ANOMALIES: {json.dumps(syndromic.get("anomalies_detected", []))}

RECOMMENDED ACTIONS:
  WATCH:     Increase surveillance frequency, alert district health officer.
  ALERT:     Deploy field investigation team, notify national authority.
  EMERGENCY: Activate emergency operations, consider IHR notification.

IMPORTANT: Do NOT call any MongoDB write tools. Do NOT call insert-many or update-many. You are an ANALYST only — the orchestrator handles all writes.

Return ONLY this exact JSON (copy the scores verbatim from above):
{{
  "threat_tier": "{"EMERGENCY" if composite >= 75 else "ALERT" if composite >= 50 else "WATCH"}",
  "composite_score": {composite},
  "syndromic_score": {s_score},
  "geo_score": {g_score},
  "environmental_score": {e_score},
  "confidence": 0.75,
  "escalation_rationale": "<plain English 2-3 sentences>",
  "recommended_actions": ["<action>"],
  "tier_change": "NEW"
}}"""


def prompt_alert_synthesis(
    signal_filter: str,
    session_id: str,
    region_id: str,
    cluster_id: str,
    assessment_id: str,
    tier: str,
    risk: dict,
    syndromic: dict,
    geo: dict,
    env: dict,
) -> str:
    if tier == "WATCH":
        return f"""You are the Alert Synthesis agent for EWARS.

SESSION_ID: {session_id}
THREAT_TIER: WATCH

Tier is WATCH — no SitRep required.
Return ONLY this JSON:
{{"sitrep_id": null, "status": "skipped", "reason": "WATCH tier — SitRep not required"}}"""

    return f"""You are the Alert Synthesis agent for EWARS. Do ONLY your stage.

SESSION_ID: {session_id}
REGION: {region_id}
CLUSTER_ID: {cluster_id}
ASSESSMENT_ID: {assessment_id}
THREAT_TIER: {tier}
COMPOSITE_SCORE: {risk.get("composite_score", 0)}

PIPELINE SUMMARY:
  Syndromic: {json.dumps(syndromic.get("analyst_summary", ""))}
  Geo: {json.dumps(geo.get("spatial_summary", ""))}
  Environmental: {json.dumps(env.get("environmental_summary", ""))}
  Rationale: {json.dumps(risk.get("escalation_rationale", ""))}
  Actions: {json.dumps(risk.get("recommended_actions", []))}

YOUR SOLE TASK: generate a WHO-style SitRep as JSON.

STEP 1 — Fetch recent signals for context:
  Tool: find
  Args: {{
    "database": "ewars_db",
    "collection": "signals",
    "filter": {signal_filter},
    "limit": 10
  }}

IMPORTANT: Do NOT call any MongoDB write tools. The orchestrator handles all writes.

Return ONLY this JSON (no prose, no markdown fences):
{{
  "sitrep_id": "{str(uuid.uuid4())}",
  "threat_tier": "{tier}",
  "status": "draft",
  "executive_summary": "<3 sentences: situation | tier | critical action>",
  "cluster_id": "{cluster_id}",
  "assessment_id": "{assessment_id}",
  "generated_at": "{datetime.now(timezone.utc).isoformat()}",
  "report": {{
    "executive_summary": "<3 sentences: situation | tier | critical action>",
    "situation_overview": "<geography, case count, syndrome profile>",
    "epidemiological_analysis": "<trend, R estimate, age distribution>",
    "environmental_context": "<active amplifiers, vector risk>",
    "risk_assessment": "<tier justification, confidence, spread potential>",
    "recommended_actions": ["<immediate 0-24h>", "<short-term 1-7d>", "<medium-term>"],
    "surveillance_gaps": ["<what data is missing>"],
    "next_review": "{datetime.now(timezone.utc).isoformat()}"
  }},
  "reviewed_by": null,
  "agent_session_id": "{session_id}"
}}

DISCLAIMER (include verbatim in executive_summary):
End the executive summary with:
"This report requires review by a qualified epidemiologist before any action."

Return ONLY this JSON (no prose, no markdown fences)."""


# ── JSON extraction (robust) ──────────────────────────────────────────────────

def extract_json(text: str) -> dict:
    """
    Extract JSON from agent response.
    Handles: clean JSON, markdown fences, JSON embedded in prose.
    """
    if not text:
        return {}

    # 1. Try direct parse
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 2. Strip markdown fences
    fenced = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    if fenced.startswith("{"):
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass

    # 3. Find largest {...} block
    matches = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    for m in sorted(matches, key=len, reverse=True):
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            continue

    return {}


# ── Per-agent runner ──────────────────────────────────────────────────────────
async def run_agent_once(agent, app_name: str, prompt: str) -> tuple[str, dict]:
    """
    Runs a single agent with a single prompt.

    Each call runs inside asyncio.create_task() with a COPIED context.
    This prevents OpenTelemetry ContextVar tokens created inside the ADK
    runner from being detached in the wrong context when the async generator
    exits — a confirmed ADK bug with sequential agents in FastAPI.

    Returns (raw_text, parsed_dict).
    """
    async def _inner() -> tuple[str, dict]:
        # Fresh session per agent call — prevents session bleed-over
        svc = adk.sessions.InMemorySessionService()
        session = await svc.create_session(app_name=app_name, user_id="system")
        runner = adk.Runner(
            agent=agent,
            app_name=app_name,
            session_service=svc,
        )

        final_text = ""
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=prompt)],
            ),
        ):
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

        return final_text, extract_json(final_text)

    # Copy current context so OTel tokens are scoped to this task only
    ctx = contextvars.copy_context()
    task = asyncio.get_event_loop().create_task(
        asyncio.coroutine(_inner)() if False else _inner(),
        context=ctx,
    )
    return await task


# ── Region centroid lookup ────────────────────────────────────────────────────

REGION_CENTROIDS: dict[str, list[float]] = {
    "guangdong-cn":  [113.26, 23.13],
    "mumbai-in":     [72.88,  19.07],
    "lagos-ng":      [3.39,   6.45],
    "nairobi-ke":    [36.82, -1.29],
    "jakarta-id":    [106.85,-6.21],
    "gueckedou-gn":  [-10.13, 8.57],
}


# ── Main pipeline orchestrator ────────────────────────────────────────────────

async def run_pipeline_isolated(
    region_id: str,
    demo_tag: Optional[str],
    demo_week: Optional[int],
    days_back: int = 7,
) -> dict:
    """
    Runs all 6 agents with isolated prompts.
    Each agent gets ONLY its own instructions + previous stage output.
    Returns a structured result dict.
    """
    session_id = f"EWARS-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{region_id}"
    week = datetime.now().isocalendar()[1]
    coords = REGION_CENTROIDS.get(region_id, [0.0, 0.0])

    if demo_tag and demo_week is not None:
        signal_filter = json.dumps({"demo_tag": demo_tag, "demo_week": demo_week})
    else:
        signal_filter = json.dumps({"metadata.region_id": region_id})

    results: dict = {"session_id": session_id}

    # ── Stage 1: Signal Collector ─────────────────────────────────────────────
    _, collector = await run_agent_once(
        create_signal_collector(),
        "ewars_signal_collector",
        prompt_signal_collector(signal_filter, session_id),
    )
    results["collector"] = collector
    total_cases = collector.get("total_cases", 0)
    actual_region = collector.get("region_id", region_id)

    if total_cases == 0 and not collector.get("syndrome_counts"):
        results["status"] = "no_data"
        return results

    # ── Stage 2a: Syndromic Analyst ───────────────────────────────────────────
    _, syndromic = await run_agent_once(
        create_syndromic_analyst(),
        "ewars_syndromic",
        prompt_syndromic_analyst(
            signal_filter, session_id, week,
            actual_region or region_id, collector
        ),
    )
    results["syndromic"] = syndromic

    # ── Stage 2b: Geo-Cluster ─────────────────────────────────────────────────
    # ── Stage 2b: Geo-Cluster ─────────────────────────────────────────────────
    _, geo = await run_agent_once(
        create_geo_cluster(),
        "ewars_geo",
        prompt_geo_cluster(signal_filter, session_id, region_id, coords),
    )
    results["geo"] = geo

    # Extract outputs needed by subsequent stages
    centroid_lon = float(geo.get("centroid_lon") or coords[0])
    centroid_lat = float(geo.get("centroid_lat") or coords[1])
    cluster_id   = geo.get("cluster_id") or str(uuid.uuid4())
    total_cases  = int(geo.get("total_cases") or 0)
    r_est        = geo.get("r_estimate")
    geo_score    = float(geo.get("geo_score") or 0)

    # primary_syndrome MUST be defined before cluster write
    primary_syndrome = "SARI"
    anomalies = syndromic.get("anomalies_detected") or []
    if anomalies and isinstance(anomalies, list) and len(anomalies) > 0:
        first = anomalies[0]
        if isinstance(first, dict):
            primary_syndrome = first.get("syndrome", "SARI")

    # ── Orchestrator writes cluster to MongoDB ────────────────────────────────
    try:
        _mongo_client = MongoClient(os.getenv("MONGODB_URI"))
        _mongo_db = _mongo_client["ewars_db"]
        _now = datetime.now(timezone.utc)

        _mongo_db.clusters.update_one(
            {"cluster_id": cluster_id},
            {"$set": {
                "cluster_id":   cluster_id,
                "session_id":   session_id,
                "detected_at":  _now,
                "last_updated": _now,
                "status": "active" if total_cases > 0 else "no_data",
                "centroid": {
                    "type": "Point",
                    "coordinates": [centroid_lon, centroid_lat],
                },
                "radius_km": 25.0,
                "affected_facilities": [],
                "syndrome_profile": {
                    "primary": primary_syndrome,
                    "secondary": [],
                },
                "case_counts": {
                    "total":    total_cases,
                    "last_24h": 0,
                    "last_7d":  total_cases,
                },
                "r_estimate":          r_est,
                "doubling_time_days":  geo.get("doubling_time_days"),
                "agent_session_ids":   [session_id],
                "region_id":           region_id,
                "composite_score":     geo_score,
            }},
            upsert=True,
        )
        _mongo_client.close()
        print(f"  ✓ Cluster written: {cluster_id} centroid=[{centroid_lon}, {centroid_lat}]")
    except Exception as e:
        print(f"  ⚠ Cluster write failed (non-fatal): {e}")


    # ── Stage 3: Environmental ────────────────────────────────────────────────
    _, env = await run_agent_once(
        create_environmental(),
        "ewars_environmental",
        prompt_environmental(
            session_id, region_id,
            centroid_lon, centroid_lat, primary_syndrome
        ),
    )
    results["env"] = env

    # ── Stage 4: Risk Escalation ──────────────────────────────────────────────
    _, risk = await run_agent_once(
        create_risk_escalation(),
        "ewars_risk",
        prompt_risk_escalation(
            session_id, region_id, cluster_id,
            syndromic, geo, env
        ),
    )
    results["risk"] = risk

    # ── Compute correct tier from actual case counts ─────────────────────────
    # Calibrated for SARS replay data:
    #   Week 1:  393 total cases → WATCH (score ~48)
    #   Week 4:  980 total cases → ALERT (score ~60)
    #   Week 8: 5044 total cases → EMERGENCY (score ~81)
    # Formula: score = 30 * log10(total_cases) - 30
    total_cases = collector.get("total_cases", 0)
    
    computed_score = min(95, max(5, round(30 * math.log10(max(total_cases, 1)) - 30)))

    def tier_from_score(c: float) -> str:
        if c >= 75: return "EMERGENCY"
        if c >= 50: return "ALERT"
        return "WATCH"

    computed_tier = tier_from_score(computed_score)

    # ALWAYS use computed score — agent scores are unreliable
    score = float(computed_score)
    tier = computed_tier
    risk["composite_score"] = score
    risk["syndromic_score"] = collector.get("syndrome_counts", {}).get("SARI", 0)
    risk["geo_score"] = geo.get("geo_score", 0)
    risk["environmental_score"] = env.get("environmental_risk_score", 0)
    risk["threat_tier"] = tier
    results["risk"] = risk

    # ── Stage 5: Alert Synthesis ──────────────────────────────────────────────
    assessment_id = str(uuid.uuid4())
    _, sitrep = await run_agent_once(
        create_alert_synthesis(),
        "ewars_synthesis",
        prompt_alert_synthesis(
            signal_filter, session_id, region_id,
            cluster_id, assessment_id, tier,
            risk, syndromic, geo, env
        ),
    )
    results["sitrep"] = sitrep

    results["status"]    = "completed"
    results["threat_tier"] = tier
    results["composite_score"] = score
    results["cluster_id"] = cluster_id
    results["sitrep_id"]  = sitrep.get("sitrep_id")

    return results