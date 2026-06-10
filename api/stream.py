# api/stream.py
"""
SSE streaming endpoint for the EWARS pipeline.

GET /run/stream?region_id=guangdong-cn&demo_tag=sars_replay&demo_week=1

Streams one JSON event per line in SSE format:
  data: {"type": "agent_start", "agent": "signal_collector", ...}\n\n
  data: {"type": "tool_call", "agent": "geo_cluster", "tool": "find", ...}\n\n
  data: {"type": "tool_result", "agent": "geo_cluster", "tool": "find", ...}\n\n
  data: {"type": "agent_done", "agent": "signal_collector", ...}\n\n
  data: {"type": "pipeline_done", "threat_tier": "WATCH", ...}\n\n
  data: {"type": "error", "agent": "...", "message": "..."}\n\n

The browser connects once and receives all events until pipeline_done.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter
from pymongo import MongoClient
from fastapi.responses import StreamingResponse
from google import adk
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types as genai_types

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ewars_multiagent.orchestrator.agent import root_agent
from api.pipeline_runner import (
    run_agent_once,
    prompt_signal_collector,
    prompt_syndromic_analyst,
    prompt_geo_cluster,
    prompt_environmental,
    prompt_risk_escalation,
    prompt_alert_synthesis,
    extract_json,
    REGION_CENTROIDS,
)
from ewars_multiagent.orchestrator.agent  import (
    create_signal_collector, create_syndromic_analyst,
    create_geo_cluster, create_environmental,
    create_risk_escalation, create_alert_synthesis,
)


router = APIRouter(tags=["streaming"])

# Map ADK author names to human-readable labels + model info
AGENT_META = {
    "ewars_pipeline":    {"label": "EWARS Pipeline",    "model": "orchestrator"},
    "signal_collector":  {"label": "Signal Collector",  "model": "Flash"},
    "syndromic_analyst": {"label": "Syndromic Analyst", "model": "Pro"},
    "geo_cluster":       {"label": "Geo-Cluster",       "model": "Flash"},
    "environmental":     {"label": "Environmental",     "model": "Flash"},
    "risk_escalation":   {"label": "Risk Escalation",   "model": "Pro"},
    "alert_synthesis":   {"label": "Alert Synthesis",   "model": "Pro"},
    "parallel_analysis": {"label": "Parallel Stage",    "model": "orchestrator"},
    "data_normalisation":{"label": "Data Normaliser",   "model": "Pro"},
    "prediction_agent":  {"label": "Prediction Agent",  "model": "Pro"},
}

# Ordered pipeline stages for progress tracking
PIPELINE_STAGES = [
    "signal_collector",
    "syndromic_analyst",
    "geo_cluster",
    "environmental",
    "risk_escalation",
    "alert_synthesis",
]


def sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, default=str)}\n\n"


def extract_tool_info(event) -> Optional[dict]:
    """
    Extract tool call information from an ADK event.
    Returns None if the event is not a tool call.
    """
    if not (hasattr(event, "content") and event.content):
        return None
    for part in event.content.parts:
        if hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            return {
                "tool": getattr(fc, "name", "unknown"),
                "args": dict(getattr(fc, "args", {}) or {}),
            }
    return None


def extract_tool_result(event) -> Optional[dict]:
    """
    Extract tool result from an ADK event.
    Returns None if not a tool result.
    """
    if not (hasattr(event, "content") and event.content):
        return None
    for part in event.content.parts:
        if hasattr(part, "function_response") and part.function_response:
            fr = part.function_response
            raw = getattr(fr, "response", {}) or {}
            # Extract text content from MCP response
            content_list = raw.get("content", [])
            text = " ".join(
                c.get("text", "") for c in content_list
                if isinstance(c, dict) and c.get("type") == "text"
            )
            is_error = raw.get("isError", False)
            return {
                "tool": getattr(fr, "name", "unknown"),
                "result_preview": text[:300] if text else str(raw)[:300],
                "is_error": is_error,
                "doc_count": _extract_doc_count(text),
            }
    return None


def _extract_doc_count(text: str) -> Optional[int]:
    """Pull document count from MCP find response text."""
    m = re.search(r'resulted in (\d+) document', text)
    return int(m.group(1)) if m else None


def extract_text_fragment(event) -> Optional[str]:
    """Get any text content from the event (partial or complete)."""
    if not (hasattr(event, "content") and event.content):
        return None
    for part in event.content.parts:
        if hasattr(part, "text") and part.text:
            return part.text[:500]
    return None


def extract_tier(text: str) -> str:
    t = (text or "").upper()
    if "EMERGENCY" in t: return "EMERGENCY"
    if "ALERT" in t: return "ALERT"
    return "WATCH"


def extract_float(text: str, key: str) -> float:
    m = re.search(rf'"{key}"\s*:\s*([\d.]+)', text or "", re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


async def pipeline_stream(region_id, demo_tag, demo_week, days_back):
    """
    SSE-streaming version of run_pipeline_isolated.
    Yields agent_start / tool_call / tool_result / agent_done events
    for each stage as it completes.
    """
    import uuid
    session_id = f"EWARS-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{region_id}"
    week   = datetime.now().isocalendar()[1]
    coords = REGION_CENTROIDS.get(region_id, [0.0, 0.0])
    start  = datetime.utcnow()

    if demo_tag and demo_week is not None:
        signal_filter = json.dumps({"demo_tag": demo_tag, "demo_week": demo_week})
    else:
        signal_filter = json.dumps({"metadata.region_id": region_id})

    yield sse({
        "type": "pipeline_start",
        "session_id": session_id,
        "region_id": region_id,
        "demo_tag": demo_tag,
        "demo_week": demo_week,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stages": PIPELINE_STAGES,
    })

    # ── Helper: run one agent and stream its events ───────────────────────────
    # ── Helper: run one agent, collect its result ───────────────────────────
    async def run_agent_and_stream(agent, app_name, prompt, agent_name):
        """
        Runs one agent. Yields SSE events for it. When done, sets agent_result.
        Since this is an async generator, results are communicated via closure.
        """
        nonlocal agent_result
        agent_result = {}  # will be overwritten by each agent's result
        meta = AGENT_META.get(agent_name, {"label": agent_name, "model": "unknown"})

        yield sse({
            "type": "agent_start",
            "agent": agent_name,
            "label": meta["label"],
            "model": meta["model"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        svc = adk.sessions.InMemorySessionService()
        session = await svc.create_session(app_name=app_name, user_id="system")
        runner = adk.Runner(agent=agent, app_name=app_name, session_service=svc)

        full_text_parts: list[str] = []
        pending_tool: Optional[dict] = None

        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=prompt)],
            ),
        ):
            error_code = getattr(event, "error_code", None)
            finish     = getattr(event, "finish_reason", None)

            # Tool call
            tool_call = extract_tool_info(event)
            if tool_call:
                pending_tool = tool_call
                yield sse({
                    "type": "tool_call",
                    "agent": agent_name,
                    "label": meta["label"],
                    "tool": tool_call["tool"],
                    "collection": tool_call["args"].get("collection", "unknown"),
                    "filter_preview": json.dumps(
                        tool_call["args"].get("filter", {}), default=str
                    )[:150],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Tool result
            tool_result = extract_tool_result(event)
            if tool_result:
                pending_tool = None
                yield sse({
                    "type": "tool_result",
                    "agent": agent_name,
                    "label": meta["label"],
                    "tool": tool_result["tool"],
                    "doc_count": tool_result["doc_count"],
                    "result_preview": tool_result["result_preview"],
                    "is_error": tool_result["is_error"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Errors
            if error_code:
                yield sse({
                    "type": "error",
                    "agent": agent_name,
                    "label": meta["label"],
                    "error_code": error_code,
                    "message": (getattr(event, "error_message", "") or "")[:300],
                    "hint": (
                        "Agent wrote Python code instead of calling MCP tool. "
                        "Check agent instruction."
                    ) if error_code == "MALFORMED_FUNCTION_CALL" else "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Accumulate full text
            frag = extract_text_fragment(event)
            if frag:
                full_text_parts.append(frag)

            # Agent done
            if finish == "STOP" and pending_tool is None:
                final_text = "\n".join(full_text_parts)
                parsed = extract_json(final_text)
                agent_result[agent_name] = parsed
                yield sse({
                    "type": "agent_done",
                    "agent": agent_name,
                    "label": meta["label"],
                    "output_preview": final_text[:200],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return


    # ── Run stages in order, yielding SSE events ──────────────────────────────
    agent_result: dict = {}
    try:
        # Stage 1: Signal Collector
        async for _ev in run_agent_and_stream(
            create_signal_collector(), "ewars_signal_collector",
            prompt_signal_collector(signal_filter, session_id),
            "signal_collector",
        ):
            yield _ev
        collector = agent_result.get("signal_collector", {})

        # Stage 2a: Syndromic Analyst
        async for _ev in run_agent_and_stream(
            create_syndromic_analyst(), "ewars_syndromic",
            prompt_syndromic_analyst(
                signal_filter, session_id, week,
                collector.get("region_id", region_id), collector
            ),
            "syndromic_analyst",
        ):
            yield _ev
        syndromic = agent_result.get("syndromic_analyst", {})

        # Stage 2b: Geo-Cluster
        async for _ev in run_agent_and_stream(
            create_geo_cluster(), "ewars_geo",
            prompt_geo_cluster(signal_filter, session_id, region_id, coords),
            "geo_cluster",
        ):
            yield _ev
        geo = agent_result.get("geo_cluster", {})

        centroid_lon = geo.get("centroid_lon") or coords[0]
        centroid_lat = geo.get("centroid_lat") or coords[1]
        cluster_id   = geo.get("cluster_id", str(uuid.uuid4()))
        syndrome     = (syndromic.get("anomalies_detected") or [{}])[0].get("syndrome", "SARI")

        # Stage 3: Environmental
        async for _ev in run_agent_and_stream(
            create_environmental(), "ewars_environmental",
            prompt_environmental(
                session_id, region_id, centroid_lon, centroid_lat, syndrome
            ),
            "environmental",
        ):
            yield _ev
        env = agent_result.get("environmental", {})

        # Stage 4: Risk Escalation
        async for _ev in run_agent_and_stream(
            create_risk_escalation(), "ewars_risk",
            prompt_risk_escalation(
                session_id, region_id, cluster_id, syndromic, geo, env
            ),
            "risk_escalation",
        ):
            yield _ev
        risk = agent_result.get("risk_escalation", {})

        # Score fallback (same as pipeline_runner.py)
        s_score_input = syndromic.get("overall_syndromic_score", 0)
        g_score_input = geo.get("geo_score", 0)
        e_score_input = env.get("environmental_risk_score", 0)
        bonus_input   = syndromic.get("source_concordance_bonus", 0)
        composite_calculated = round(
            s_score_input * 0.40 + g_score_input * 0.30 +
            e_score_input * 0.20 + bonus_input * 0.10, 1,
        )
        def tier_from_score(c):
            if c >= 75: return "EMERGENCY"
            if c >= 50: return "ALERT"
            return "WATCH"
        correct_tier = tier_from_score(composite_calculated)
        agent_score = float(risk.get("composite_score", 0))
        if agent_score == 0 and composite_calculated > 0:
            risk["composite_score"] = composite_calculated
            risk["syndromic_score"] = s_score_input
            risk["geo_score"] = g_score_input
            risk["environmental_score"] = e_score_input
            risk["threat_tier"] = correct_tier

        tier  = risk.get("threat_tier", correct_tier)
        score = float(risk.get("composite_score", composite_calculated))

        # Stage 5: Alert Synthesis
        assessment_id = str(uuid.uuid4())
        async for _ev in run_agent_and_stream(
            create_alert_synthesis(), "ewars_synthesis",
            prompt_alert_synthesis(
                signal_filter, session_id, region_id,
                cluster_id, assessment_id, tier,
                risk, syndromic, geo, env
            ),
            "alert_synthesis",
        ):
            yield _ev
        sitrep = agent_result.get("alert_synthesis", {})

        # Orchestrator writes (same pattern as pipeline_runner)
        duration = (datetime.utcnow() - start).total_seconds()
        _mongo_client = MongoClient(os.getenv("MONGODB_URI"))
        _mongo_db = _mongo_client["ewars_db"]
        _now = datetime.now(timezone.utc)

        # Write cluster
        _mongo_db.clusters.update_one(
            {"cluster_id": cluster_id},
            {"$set": {
                "cluster_id": cluster_id, "session_id": session_id,
                "detected_at": _now, "last_updated": _now,
                "status": "active",
                "centroid": {"type": "Point", "coordinates": [centroid_lon, centroid_lat]},
                "radius_km": 25.0, "affected_facilities": [],
                "syndrome_profile": {"primary": syndrome, "secondary": []},
                "case_counts": {"total": 0, "last_24h": 0, "last_7d": 0},
                "r_estimate": geo.get("r_estimate"),
                "doubling_time_days": geo.get("doubling_time_days"),
                "agent_session_ids": [session_id],
                "region_id": region_id, "composite_score": g_score_input,
            }},
            upsert=True,
        )

        # Write threat assessment
        _mongo_db.threat_assessments.update_one(
            {"agent_session_id": session_id},
            {"$set": {
                "assessment_id": assessment_id,
                "cluster_id": cluster_id,
                "assessed_at": _now,
                "threat_tier": tier,
                "confidence": 0.75,
                "syndromic_score": s_score_input,
                "geo_score": g_score_input,
                "environmental_score": e_score_input,
                "composite_score": score,
                "recommended_actions": risk.get("recommended_actions", []),
                "escalation_rationale": risk.get("escalation_rationale", ""),
                "agent_session_id": session_id,
                "region_id": region_id,
            }},
            upsert=True,
        )

        # Write sitrep if ALERT or EMERGENCY
        sitrep_id = sitrep.get("sitrep_id")
        if tier in ("ALERT", "EMERGENCY") and sitrep_id:
            _mongo_db.situation_reports.update_one(
                {"agent_session_id": session_id},
                {"$set": {
                    "sitrep_id": sitrep_id,
                    "cluster_id": cluster_id,
                    "assessment_id": assessment_id,
                    "generated_at": _now,
                    "threat_tier": tier,
                    "report": sitrep.get("report", {}),
                    "status": "draft",
                    "reviewed_by": None,
                    "agent_session_id": session_id,
                }},
                upsert=True,
            )

        # Write agent session
        _mongo_db.agent_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "session_id": session_id,
                "triggered_at": _now,
                "trigger_type": "stream",
                "region_id": region_id,
                "pipeline_status": "completed",
                "final_threat_tier": tier,
                "duration_seconds": round(duration, 1),
                "response_preview": json.dumps(risk)[:300],
            }},
            upsert=True,
        )
        _mongo_client.close()

        yield sse({
            "type": "pipeline_done",
            "session_id": session_id,
            "threat_tier": tier,
            "composite_score": score,
            "syndromic_score": s_score_input,
            "geo_score": g_score_input,
            "environmental_score": e_score_input,
            "sitrep_id": sitrep_id,
            "cluster_id": cluster_id,
            "duration_seconds": round(duration, 1),
            "agents_completed": PIPELINE_STAGES,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        yield sse({
            "type": "fatal_error",
            "message": str(e)[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


@router.get("/run/stream")
async def run_stream(
    region_id: str,
    demo_tag: Optional[str] = None,
    demo_week: Optional[int] = None,
    days_back: int = 7,
):
    """
    SSE endpoint — streams real-time pipeline events to the browser.
    Connect with EventSource in the frontend.
    """
    return StreamingResponse(
        pipeline_stream(region_id, demo_tag, demo_week, days_back),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable Nginx buffering
            "Connection": "keep-alive",
        },
    )