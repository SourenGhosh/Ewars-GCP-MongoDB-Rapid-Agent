"""
EWARS FastAPI.
Strategy: MCP-first for all agent operations (hackathon requirement).
pymongo safety net writes ONLY if MCP writes didn't happen.
This keeps MCP central while ensuring demo reliability.
"""

# CRITICAL: Set telemetry env vars BEFORE any ADK imports
import os
os.environ.setdefault("ADK_DISABLE_TELEMETRY", "1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("ADK_DISABLE_TELEMETRY", "1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

import json, re, uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from google import adk
from contextlib import asynccontextmanager
from google.genai import types

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ewars_multiagent.orchestrator.agent import root_agent
from mcp_chain.toolset import get_mongo_toolset
from api.ingest import router as ingest_router
from api.timeline import router as timeline_router
from api.stream import router as stream_router
from api.pipeline_runner import run_pipeline_isolated

@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown lifecycle."""
    print("EWARS API starting...")
    # MCP connections are lazy-initialized on first agent call
    yield
    print("EWARS API shutting down...")



app = FastAPI(title="EWARS API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(ingest_router)
app.include_router(timeline_router)
app.include_router(stream_router)

_sessions: dict = {}
_mongo = None

def db():
    global _mongo
    if _mongo is None:
        _mongo = MongoClient(os.getenv("MONGODB_URI"))
    return _mongo["ewars_db"]


def extract_tier(text: str) -> str:
    t = text.upper()
    if "EMERGENCY" in t: return "EMERGENCY"
    if "ALERT" in t: return "ALERT"
    return "WATCH"


def extract_float(text: str, key: str) -> float:
    m = re.search(rf'"{key}"\s*:\s*([\d.]+)', text, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def safety_net_writes(session_id, region_id, trigger_type,
                      tier, score, duration, final_text):
    """
    Writes to MongoDB ONLY if MCP tool calls didn't already do it.
    Preserves MCP as the primary writer — this is purely defensive.
    """
    d = db()
    now = datetime.now(timezone.utc)
    cluster_id = str(uuid.uuid4())
    assessment_id = str(uuid.uuid4())
    sitrep_id = None

    CENTROIDS = {
        "guangdong-cn": [113.26, 23.13], "mumbai-in": [72.88, 19.07],
        "lagos-ng": [3.39, 6.45], "nairobi-ke": [36.82, -1.29],
        "jakarta-id": [106.85, -6.21], "gueckedou-gn": [-10.13, 8.57],
    }

    # ── clusters ─────────────────────────────────────────────────────────────
    # Check by session_id field (not agent_session_ids array) for reliability
    existing_cluster = d.clusters.find_one({"session_id": session_id})
    if existing_cluster:
        cluster_id = existing_cluster["cluster_id"]
        # Skip write — agent already wrote this cluster
    else:
        # Only write if NO cluster exists for this session at all
        r_m = re.search(r'"r_estimate"\s*:\s*([\d.]+)', str(final_text))
        d.clusters.insert_one({
            "cluster_id": cluster_id,
            "session_id": session_id,          # flat field, easy to find
            "detected_at": now, "last_updated": now,
            "status": "active",
            "centroid": {
                "type": "Point",
                "coordinates": CENTROIDS.get(region_id, [0.0, 0.0]),
            },
            "radius_km": 25.0, "affected_facilities": [],
            "syndrome_profile": {"primary": "SARI", "secondary": []},
            "case_counts": {"total": 0, "last_24h": 0, "last_7d": 0},
            "r_estimate": float(r_m.group(1)) if r_m else None,
            "doubling_time_days": None,
            "agent_session_ids": [session_id],
            "region_id": region_id, "composite_score": score,
        })

    # threat_assessments
    if not d.threat_assessments.find_one({"agent_session_id": session_id}):
        d.threat_assessments.insert_one({
            "assessment_id": assessment_id, "cluster_id": cluster_id,
            "assessed_at": now, "threat_tier": tier, "confidence": 0.7,
            "contributing_factors": [],
            "syndromic_score": extract_float(final_text, "overall_syndromic_score"),
            "geo_score": extract_float(final_text, "geo_score"),
            "environmental_score": extract_float(final_text, "environmental_risk_score"),
            "composite_score": score, "recommended_actions": [],
            "escalation_rationale": final_text[:800],
            "agent_session_id": session_id, "region_id": region_id,
        })
    else:
        ex = d.threat_assessments.find_one({"agent_session_id": session_id})
        assessment_id = ex["assessment_id"]

    # situation_reports
    if tier in ("ALERT", "EMERGENCY"):
        if not d.situation_reports.find_one({"agent_session_id": session_id}):
            sitrep_id = str(uuid.uuid4())
            d.situation_reports.insert_one({
                "sitrep_id": sitrep_id, "cluster_id": cluster_id,
                "assessment_id": assessment_id, "generated_at": now,
                "threat_tier": tier,
                "report": {
                    "executive_summary": final_text[:500],
                    "situation_overview": f"Region: {region_id}",
                    "epidemiological_analysis": "",
                    "environmental_context": "",
                    "risk_assessment": f"Tier: {tier}",
                    "recommended_actions": [], "surveillance_gaps": [],
                    "next_review": now.isoformat(),
                },
                "status": "draft", "reviewed_by": None,
                "agent_session_id": session_id,
            })
        else:
            sitrep_id = d.situation_reports.find_one(
                {"agent_session_id": session_id})["sitrep_id"]

    # agent_sessions
    if not d.agent_sessions.find_one({"session_id": session_id}):
        d.agent_sessions.insert_one({
            "session_id": session_id, "triggered_at": now,
            "trigger_type": trigger_type, "region_id": region_id,
            "pipeline_status": "completed", "final_threat_tier": tier,
            "duration_seconds": round(duration, 1),
            "response_preview": final_text[:300], "agent_traces": [],
        })

    return cluster_id, assessment_id, sitrep_id


class PipelineRequest(BaseModel):
    region_id: str
    trigger_type: str = "manual"
    demo_tag: Optional[str] = None
    demo_week: Optional[int] = None
    days_back: int = 7


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/assessments")
def list_assessments(limit: int = 20):
    """List all threat assessments with their escalation rationale."""
    d = db()
    docs = list(
        d.threat_assessments.find({}, {"_id": 0})
        .sort("assessed_at", -1)
        .limit(limit)
    )
    for doc in docs:
        for field in ["assessed_at", "generated_at"]:
            if field in doc and hasattr(doc[field], "isoformat"):
                doc[field] = doc[field].isoformat()
    # Join sitrep_id from situation_reports
    for doc in docs:
        sitrep = d.situation_reports.find_one(
            {"assessment_id": doc.get("assessment_id")}, {"_id": 0, "sitrep_id": 1}
        )
        doc["sitrep_id"] = sitrep.get("sitrep_id") if sitrep else None
    return {"assessments": docs, "count": len(docs)}


@app.post("/run")
async def run_pipeline(req: PipelineRequest):
    start = datetime.utcnow()

    # Run with isolated per-agent prompts
    result = await run_pipeline_isolated(
        region_id=req.region_id,
        demo_tag=req.demo_tag,
        demo_week=req.demo_week,
        days_back=req.days_back,
    )

    session_id = result.get("session_id", "unknown")
    tier       = result.get("threat_tier", "WATCH")
    score      = result.get("composite_score", 0.0)
    duration   = (datetime.utcnow() - start).total_seconds()

    # Safety net — only writes what agents didn't
    cluster_id, assessment_id, sitrep_id = safety_net_writes(
        session_id, req.region_id, req.trigger_type,
        tier, score, duration,
        json.dumps(result.get("risk", {}))
    )

    _sessions[session_id] = {
        "status": "completed",
        "threat_tier": tier,
        "composite_score": score,
        "duration_seconds": round(duration, 1),
    }

    return {
        "session_id":      session_id,
        "status":          "completed",
        "threat_tier":     tier,
        "composite_score": score,
        "duration_seconds": round(duration, 1),
        "sitrep_id":       result.get("sitrep_id") or sitrep_id,
        "cluster_id":      result.get("cluster_id") or cluster_id,
        "syndromic_score": result.get("syndromic", {}).get("overall_syndromic_score", 0),
        "geo_score":       result.get("geo", {}).get("geo_score", 0),
        "environmental_score": result.get("env", {}).get("environmental_risk_score", 0),
    }

@app.get("/events")
def get_events():
    """Dynamic event list from MongoDB — no hardcoding."""
    d = db()
    pipeline = [
        {"$match": {"demo_tag": {"$exists": True}}},
        {"$group": {
            "_id": {"demo_tag": "$demo_tag", "region_id": "$metadata.region_id"},
            "weeks": {"$addToSet": "$demo_week"},
            "total_cases": {"$sum": "$case_count"},
            "signal_count": {"$sum": 1},
            "first_signal": {"$min": "$timestamp"},
        }},
        {"$sort": {"first_signal": 1}},
    ]
    events = list(d.signals.aggregate(pipeline))
    result = []
    for e in events:
        weeks = sorted([w for w in (e.get("weeks") or []) if w is not None])
        first = e.get("first_signal")
        result.append({
            "demo_tag": e["_id"]["demo_tag"],
            "region_id": e["_id"]["region_id"],
            "available_weeks": weeks,
            "total_cases": e.get("total_cases", 0),
            "signal_count": e.get("signal_count", 0),
            "first_signal_date": first.isoformat() if hasattr(first, "isoformat") else str(first or ""),
        })
    # Also include live (non-demo) regions
    live = d.signals.distinct("metadata.region_id", {"demo_tag": {"$exists": False}})
    for r in live:
        result.append({"demo_tag": None, "region_id": r,
                        "available_weeks": [], "type": "live"})
    return {"events": result, "count": len(result)}


@app.get("/timeline")
def get_timeline():
    """
    Full assessment timeline from MongoDB.
    Returns all threat_assessments with cluster + sitrep joined.
    Used by the frontend threat timeline map.
    """
    d = db()
    assessments = list(
        d.threat_assessments.find({}, {"_id": 0})
        .sort("assessed_at", -1)
        .limit(200)
    )
    result = []
    for a in assessments:
        # Join cluster
        cluster = d.clusters.find_one(
            {"cluster_id": a.get("cluster_id")}, {"_id": 0}
        )
        # Join sitrep
        sitrep = d.situation_reports.find_one(
            {"assessment_id": a.get("assessment_id")}, {"_id": 0}
        )
        # Join session
        session = d.agent_sessions.find_one(
            {"session_id": a.get("agent_session_id")}, {"_id": 0}
        )
        entry = {
            "assessment_id": a.get("assessment_id"),
            "cluster_id": a.get("cluster_id"),
            "threat_tier": a.get("threat_tier"),
            "composite_score": a.get("composite_score"),
            "assessed_at": a.get("assessed_at").isoformat()
                if hasattr(a.get("assessed_at"), "isoformat") else str(a.get("assessed_at", "")),
            "region_id": a.get("region_id"),
            "escalation_rationale": a.get("escalation_rationale", "")[:300],
            "recommended_actions": a.get("recommended_actions", []),
            "has_sitrep": sitrep is not None,
            "sitrep_id": sitrep.get("sitrep_id") if sitrep else None,
            "sitrep_summary": sitrep.get("report", {}).get("executive_summary", "")[:200] if sitrep else None,
            "sitrep_status": sitrep.get("status") if sitrep else None,
            "coordinates": cluster.get("centroid", {}).get("coordinates") if cluster else None,
            "cluster_radius_km": cluster.get("radius_km") if cluster else None,
            "total_cases": cluster.get("case_counts", {}).get("total", 0) if cluster else 0,
            "r_estimate": cluster.get("r_estimate") if cluster else None,
            "syndrome_primary": cluster.get("syndrome_profile", {}).get("primary") if cluster else None,
            "duration_seconds": session.get("duration_seconds") if session else None,
            "trigger_type": session.get("trigger_type") if session else None,
        }
        result.append(entry)
    return {"assessments": result, "count": len(result)}


@app.get("/clusters/active")
def get_active_clusters():
    d = db()
    clusters = list(
        d.clusters.find({"status": {"$ne": "no_data"}}, {"_id": 0})
        .sort("detected_at", -1).limit(50)
    )
    return {"clusters": clusters, "count": len(clusters)}


@app.get("/sitreps")
def list_sitreps(limit: int = 10):
    d = db()
    docs = list(
        d.situation_reports.find({}, {"_id": 0})
        .sort("generated_at", -1).limit(limit)
    )
    return {"sitreps": docs, "count": len(docs)}


@app.get("/sitreps/{sitrep_id}")
def get_sitrep(sitrep_id: str):
    d = db()
    doc = d.situation_reports.find_one({"sitrep_id": sitrep_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="SitRep not found")
    return doc


@app.post("/ingest/json")
async def ingest_json(signals: list[dict]):
    if not signals:
        return {"inserted": 0}
    d = db()
    for s in signals:
        if isinstance(s.get("timestamp"), str):
            try:
                from datetime import datetime
                s["timestamp"] = datetime.fromisoformat(s["timestamp"])
            except ValueError:
                pass
    d.signals.insert_many(signals)
    return {"inserted": len(signals),
            "message": "Call POST /run with region_id to analyse."}


@app.post("/ingest/csv")
async def ingest_csv(region_id: str, file: UploadFile = File(...)):
    import csv, io
    from datetime import datetime
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    d = db()
    docs, skipped = [], 0
    for row in reader:
        try:
            docs.append({
                "metadata": {
                    "signal_type": row.get("signal_type", "clinic_visit"),
                    "source_id": row["source_id"],
                    "region_id": region_id,
                    "pathogen_suspected": None,
                },
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "location": {"type": "Point", "coordinates": [
                    float(row["longitude"]), float(row["latitude"])]},
                "syndrome_codes": [row["syndrome"].upper()],
                "case_count": int(row["case_count"]),
                "severity_distribution": {
                    "mild": int(row.get("mild", 0)),
                    "moderate": int(row.get("moderate", 0)),
                    "severe": int(row.get("severe", 0)),
                },
                "age_groups": {"under5": 0, "5_17": 0, "18_60": 0, "over60": 0},
                "raw_text": f"CSV import: {row.get('source_id')}",
                "normalized_by_agent": False,
            })
        except (KeyError, ValueError):
            skipped += 1
    if docs:
        d.signals.insert_many(docs)
    return {"inserted": len(docs), "skipped": skipped,
            "message": "Call POST /run with region_id to analyse."}