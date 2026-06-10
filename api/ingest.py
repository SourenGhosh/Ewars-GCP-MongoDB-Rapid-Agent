# api/ingest.py
"""
Universal ingest endpoint.
Accepts any text/CSV/JSON and runs DataNormalisationAgent to extract signals.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from google import adk
from google.genai import types as genai_types

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ewars_multiagent.data_normalization_agent.data_normalisation_agent import (
    create_data_normalisation_agent,
    ExtractionResult,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_csv_like(text: str) -> bool:
    """Rough heuristic — first non-empty line has 3+ comma-separated values."""
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return len(line.split(",")) >= 3
    return False


async def _run_normalisation_agent(raw_input: str, source_hint: str) -> dict:
    """
    Runs the DataNormalisationAgent on raw_input.
    Returns the extraction result dict.
    """
    agent = create_data_normalisation_agent()

    prompt = f"""Extract all EWARS health signals from the following input.

SOURCE TYPE HINT: {source_hint}

=== INPUT START ===
{raw_input[:15000]}
=== INPUT END ===

{"NOTE: Input was truncated to 15,000 characters. Process what is shown." if len(raw_input) > 15000 else ""}

Extract all signals, store them via MongoDB MCP insert-many, then return
your structured extraction summary.
"""

    svc = adk.sessions.InMemorySessionService()
    session = await svc.create_session(
        app_name="ewars_ingest", user_id="ingest_system"
    )
    runner = adk.Runner(
        agent=agent,
        app_name="ewars_ingest",
        session_service=svc,
    )

    final_text = ""
    async for event in runner.run_async(
        user_id="ingest_system",
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

    # Parse structured output
    try:
        # Gemini structured output returns clean JSON
        result = json.loads(final_text)
    except json.JSONDecodeError:
        # Fallback: extract JSON from text
        m = re.search(r'\{.*\}', final_text, re.DOTALL)
        if m:
            result = json.loads(m.group())
        else:
            result = {
                "signals": [],
                "input_summary": "Could not parse extraction result.",
                "extraction_warnings": [final_text[:500]],
            }

    return result


# ── Endpoints ─────────────────────────────────────────────────────────────────

class TextIngestRequest(BaseModel):
    text: str
    source_hint: Optional[str] = "unstructured text"


@router.post("/text")
async def ingest_text(req: TextIngestRequest):
    """
    Ingest any free-form text.
    Examples:
      - News article: "47 cases of atypical pneumonia in Guangdong..."
      - WHO SitRep text
      - Hospital discharge summary
      - Social media symptom report extract
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text field is empty")

    hint = req.source_hint or (
        "CSV data" if _is_csv_like(req.text) else "unstructured text"
    )
    result = await _run_normalisation_agent(req.text, hint)

    return {
        "status": "ok",
        "signals_extracted": len(result.get("signals", [])),
        "input_summary": result.get("input_summary", ""),
        "extraction_warnings": result.get("extraction_warnings", []),
        "next_step": "POST /run with the relevant region_id to analyse.",
    }


@router.post("/file")
async def ingest_file(
    file: UploadFile = File(...),
    source_hint: Optional[str] = Form(default=None),
):
    """
    Ingest any file type: .txt, .csv, .json, .md, .pdf (text layer).
    The agent extracts signals regardless of format.
    """
    content_bytes = await file.read()

    # Handle PDF — extract text layer
    if file.filename and file.filename.lower().endswith(".pdf"):
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            raw_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            hint = source_hint or "PDF document"
        except ImportError:
            raise HTTPException(
                status_code=422,
                detail="pypdf not installed. Run: pip install pypdf",
            )
    else:
        # Try UTF-8, fall back to latin-1
        try:
            raw_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = content_bytes.decode("latin-1")

        if file.filename and file.filename.lower().endswith(".json"):
            hint = source_hint or "JSON data"
        elif file.filename and file.filename.lower().endswith(".csv"):
            hint = source_hint or "CSV data"
        else:
            hint = source_hint or "text file"

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="File appears to be empty")

    result = await _run_normalisation_agent(raw_text, hint)

    return {
        "status": "ok",
        "filename": file.filename,
        "signals_extracted": len(result.get("signals", [])),
        "input_summary": result.get("input_summary", ""),
        "extraction_warnings": result.get("extraction_warnings", []),
        "next_step": "POST /run with the relevant region_id to analyse.",
    }


@router.post("/url")
async def ingest_url(url: str):
    """
    Fetch a URL (WHO SitRep, news article, DHIS2 export link) and extract signals.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            raw_text = response.text
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Could not fetch URL: {e}"
        )

    result = await _run_normalisation_agent(raw_text, f"web page: {url}")

    return {
        "status": "ok",
        "url": url,
        "signals_extracted": len(result.get("signals", [])),
        "input_summary": result.get("input_summary", ""),
        "extraction_warnings": result.get("extraction_warnings", []),
        "next_step": "POST /run with the relevant region_id to analyse.",
    }