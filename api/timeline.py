# api/timeline.py
"""
Timeline and prediction endpoints.
Serves all data needed by the EpidemicTimeline frontend component.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from google import adk
from google.genai import types as genai_types

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ewars_multiagent.prediction_agent.prediction_agent import create_prediction_agent

router = APIRouter(prefix="/timeline", tags=["timeline"])

# WHO / official declaration milestones for known events
# In production these would be stored in MongoDB — hardcoded here for known history
WHO_MILESTONES = {
    "sars_replay": [
        {
            "week_offset": 12,
            "date": "2003-02-11",
            "label": "China reports to WHO",
            "type": "official_report",
            "color": "#6366f1",
        },
        {
            "week_offset": 17,
            "date": "2003-03-12",
            "label": "WHO Global Alert",
            "type": "who_alert",
            "color": "#f97316",
        },
        {
            "week_offset": 18,
            "date": "2003-03-15",
            "label": "WHO PHEIC Declaration",
            "type": "pheic",
            "color": "#ef4444",
        },
        {
            "week_offset": 37,
            "date": "2003-07-05",
            "label": "WHO: SARS Contained",
            "type": "contained",
            "color": "#22c55e",
        },
    ],
    "ebola_replay": [
        {
            "week_offset": 10,
            "date": "2014-03-22",
            "label": "Guinea confirms Ebola",
            "type": "official_report",
            "color": "#6366f1",
        },
        {
            "week_offset": 39,
            "date": "2014-08-08",
            "label": "WHO PHEIC Declaration",
            "type": "pheic",
            "color": "#ef4444",
        },
    ],
}

_mongo = None

def db():
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.getenv("MONGODB_URI"))
    return _mongo["ewars_db"]


class PredictRequest(BaseModel):
    region_id: str
    demo_tag: Optional[str] = None
    weeks_observed: list[dict]   # [{"week": 1, "cases": 8}, ...]
    syndrome: str = "SARI"
    population: int = 10_000_000


@router.get("/full")
def get_full_timeline(
    region_id: str,
    demo_tag: Optional[str] = None,
):
    """
    Returns the complete timeline for a region/event:
    - All signals grouped by week with case counts
    - All EWARS assessments per week with tier
    - Prediction curve if available
    - WHO milestones
    """
    d = db()

    # ── 1. Build actual weekly case counts from signals ───────────────────────
    signal_filter: dict = {}
    if demo_tag:
        signal_filter["demo_tag"] = demo_tag
    else:
        signal_filter["metadata.region_id"] = region_id

    signals = list(d.signals.find(signal_filter, {"_id": 0}).sort("timestamp", 1))

    # Group by demo_week (demo) or ISO week (live)
    weekly: dict[int, dict] = {}
    for s in signals:
        if demo_tag:
            week = s.get("demo_week") or 0
        else:
            ts = s.get("timestamp")
            week = ts.isocalendar()[1] if hasattr(ts, "isocalendar") else 0

        if week not in weekly:
            weekly[week] = {
                "week": week,
                "actual_cases": 0,
                "syndromes": set(),
                "source_types": set(),
                "signals": [],
                "date": s.get("timestamp").isoformat()
                    if hasattr(s.get("timestamp"), "isoformat") else str(s.get("timestamp", "")),
            }
        weekly[week]["actual_cases"] += s.get("case_count", 0)
        for code in s.get("syndrome_codes", []):
            weekly[week]["syndromes"].add(code)
        weekly[week]["source_types"].add(
            s.get("metadata", {}).get("signal_type", "unknown")
        )

    # ── 2. Join EWARS assessments ─────────────────────────────────────────────
    assessments = list(
        d.threat_assessments.find(
            {"region_id": region_id}, {"_id": 0}
        ).sort("assessed_at", 1)
    )

    # Map session → week (by matching session timestamps to signal weeks)
    # Simplified: assign each assessment to the most recently run week
    for i, assessment in enumerate(assessments):
        target_week = sorted(weekly.keys())[min(i, len(weekly) - 1)] if weekly else 0
        week_data = weekly.get(target_week, {})
        if target_week in weekly:
            weekly[target_week]["assessment"] = {
                "assessment_id": assessment.get("assessment_id"),
                "threat_tier": assessment.get("threat_tier"),
                "composite_score": assessment.get("composite_score", 0),
                "syndromic_score": assessment.get("syndromic_score", 0),
                "geo_score": assessment.get("geo_score", 0),
                "environmental_score": assessment.get("environmental_score", 0),
                "r_estimate": None,
            }

        # Join SitRep if exists
        sitrep = d.situation_reports.find_one(
            {"assessment_id": assessment.get("assessment_id")}, {"_id": 0}
        )
        if sitrep and target_week in weekly:
            weekly[target_week]["sitrep"] = {
                "sitrep_id": sitrep.get("sitrep_id"),
                "executive_summary": sitrep.get("report", {}).get(
                    "executive_summary", ""
                )[:300],
                "recommended_actions": sitrep.get("report", {}).get(
                    "recommended_actions", []
                ),
                "status": sitrep.get("status"),
            }

    # ── 3. Fetch stored predictions ───────────────────────────────────────────
    prediction_doc = d.predictions.find_one(
        {"region_id": region_id, "demo_tag": demo_tag or "live"},
        {"_id": 0},
        sort=[("created_at", -1)],
    ) if "predictions" in d.list_collection_names() else None

    # ── 4. Serialise ──────────────────────────────────────────────────────────
    weeks_list = []
    for week_num in sorted(weekly.keys()):
        w = weekly[week_num]
        weeks_list.append({
            "week": week_num,
            "date": w["date"],
            "actual_cases": w["actual_cases"],
            "syndromes": list(w["syndromes"]),
            "source_types": list(w["source_types"]),
            "assessment": w.get("assessment"),
            "sitrep": w.get("sitrep"),
            "has_run": w.get("assessment") is not None,
        })

    return {
        "region_id": region_id,
        "demo_tag": demo_tag,
        "weeks": weeks_list,
        "total_weeks": len(weeks_list),
        "total_cases": sum(w["actual_cases"] for w in weeks_list),
        "prediction": prediction_doc,
        "who_milestones": WHO_MILESTONES.get(demo_tag or "", []),
    }


@router.post("/predict")
async def predict_trajectory(req: PredictRequest):
    """
    Runs the PredictionAgent on observed week data.
    Returns 8-week forecast with SIR/exponential model.
    Stores result in MongoDB for later retrieval.
    """
    if not req.weeks_observed:
        raise HTTPException(status_code=400, detail="No observed data provided")

    agent = create_prediction_agent()

    weeks_str = "\n".join(
        f"  Week {w['week']}: {w['cases']} cases"
        for w in sorted(req.weeks_observed, key=lambda x: x["week"])
    )
    is_new_outbreak = len(req.weeks_observed) == 1

    prompt = f"""Generate an epidemic trajectory prediction.

OBSERVED DATA ({len(req.weeks_observed)} week{'s' if len(req.weeks_observed) > 1 else ''}):
{weeks_str}

OUTBREAK CONTEXT:
  Region: {req.region_id}
  Primary syndrome: {req.syndrome}
  Estimated population at risk: {req.population:,}
  {"NEW OUTBREAK — no baseline for comparison. Use default R₀ for syndrome type." if is_new_outbreak else ""}

Select the appropriate model (exponential if < 5 weeks, SIR if >= 5 weeks).
Generate prediction for weeks {max(w['week'] for w in req.weeks_observed) + 1} through {max(w['week'] for w in req.weeks_observed) + 8}.
Generate the without-intervention counterfactual as well.
Provide plain English narrative for epidemiologists.
"""

    svc = adk.sessions.InMemorySessionService()
    session = await svc.create_session(
        app_name="ewars_predict", user_id="system"
    )
    runner = adk.Runner(
        agent=agent,
        app_name="ewars_predict",
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

    try:
        prediction = json.loads(final_text)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', final_text, re.DOTALL)
        prediction = json.loads(m.group()) if m else {}

    # Store prediction in MongoDB
    d = db()
    if "predictions" not in d.list_collection_names():
        d.create_collection("predictions")

    from datetime import datetime, timezone
    prediction_doc = {
        "region_id": req.region_id,
        "demo_tag": req.demo_tag or "live",
        "syndrome": req.syndrome,
        "weeks_observed": req.weeks_observed,
        "prediction": prediction,
        "created_at": datetime.now(timezone.utc),
    }
    d.predictions.insert_one(prediction_doc)

    return prediction