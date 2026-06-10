# agents/data_normalisation_agent.py
"""
DataNormalisationAgent — accepts any input format and extracts EWARS signals.

Uses Gemini structured output (response_schema) to guarantee the model
always returns valid EWARS signal documents regardless of input format.

This is the hackathon's showcase of:
  - Gemini structured output (Pydantic schema enforcement)
  - MongoDB MCP insert-many for storage
  - Handling real-world messy health data
"""

import json
import sys, os
from datetime import datetime, timezone
from typing import Optional

from google.adk.agents import LlmAgent
from google.genai import types as genai_types
from pydantic import BaseModel, Field

sys.path.insert(
  0, 
  os.path.dirname(
    os.path.dirname(os.path.dirname(__file__))
  )
)

from mcp_chain.toolset import get_mongo_toolset

# ── Pydantic schema — enforced by Gemini structured output ───────────────────

class SignalLocation(BaseModel):
    longitude: float = Field(description="Longitude coordinate")
    latitude: float  = Field(description="Latitude coordinate")


class SeverityDistribution(BaseModel):
    mild: int     = Field(default=0)
    moderate: int = Field(default=0)
    severe: int   = Field(default=0)


class AgeGroups(BaseModel):
    under5: int  = Field(default=0)
    age_5_17: int = Field(default=0, alias="5_17")
    age_18_60: int = Field(default=0, alias="18_60")
    over60: int  = Field(default=0)

    class Config:
        populate_by_name = True


class ExtractedSignal(BaseModel):
    """
    One EWARS signal document extracted from unstructured input.
    Gemini is constrained to always produce this exact structure.
    """
    source_id: str = Field(
        description="Facility, feed, or source identifier. Infer from context."
    )
    region_id: str = Field(
        description=(
            "Standardised EWARS region code. Map to nearest known region: "
            "guangdong-cn, mumbai-in, lagos-ng, nairobi-ke, jakarta-id. "
            "For unknown regions use country ISO code + city slug e.g. 'foshan-cn'."
        )
    )
    signal_type: str = Field(
        description=(
            "One of: clinic_visit, pharmacy_sale, social_report, lab_result, "
            "official_report, news_article"
        )
    )
    syndrome_codes: list[str] = Field(
        description=(
            "List of EWARS syndrome codes. "
            "ILI=Influenza-Like Illness (fever+cough), "
            "SARI=Severe Acute Respiratory (ILI+hospitalisation), "
            "AGE=Acute Gastroenteritis (diarrhoea/vomiting), "
            "AFP=Acute Flaccid Paralysis, "
            "UF=Undifferentiated Fever (>38C no focus), "
            "HF=Haemorrhagic Fever (fever+bleeding). "
            "Choose all that apply."
        )
    )
    case_count: int = Field(
        description="Number of cases. For proxy data (pharmacy sales) use units sold."
    )
    timestamp: str = Field(
        description=(
            "ISO 8601 date string of the signal. If only year/month given, "
            "use first day of that month. If no date, use today."
        )
    )
    longitude: float = Field(
        description="Longitude. Infer from region/city name if not explicit."
    )
    latitude: float = Field(
        description="Latitude. Infer from region/city name if not explicit."
    )
    severity_mild: int     = Field(default=0, description="Mild cases count")
    severity_moderate: int = Field(default=0, description="Moderate cases count")
    severity_severe: int   = Field(default=0, description="Severe/critical cases count")
    pathogen_suspected: Optional[str] = Field(
        default=None,
        description="Pathogen name if mentioned (e.g. 'influenza-a', 'cholera'). Null if unknown."
    )
    raw_text: str = Field(
        description="Verbatim excerpt from the source that supports this signal."
    )
    extraction_confidence: str = Field(
        description="HIGH/MEDIUM/LOW — how confident the extraction is."
    )
    extraction_note: Optional[str] = Field(
        default=None,
        description="Note any assumptions made or missing data filled by inference."
    )


class ExtractionResult(BaseModel):
    """Top-level structured output from the normalisation agent."""
    signals: list[ExtractedSignal] = Field(
        description="All EWARS signals extracted from the input. Empty list if nothing extractable."
    )
    input_summary: str = Field(
        description="1-2 sentence summary of what the input contained."
    )
    extraction_warnings: list[str] = Field(
        default_factory=list,
        description="Any data quality issues, ambiguities, or assumptions made."
    )


# ── Agent instruction ─────────────────────────────────────────────────────────

INSTRUCTION = """
You are an epidemiological data extraction specialist for EWARS.
Your job is to extract structured health signal data from ANY input format.

INPUT FORMATS YOU HANDLE:
- Free text ("There were 47 pneumonia cases in Guangdong last week")
- News articles and WHO situation reports
- CSV with non-standard column names
- JSON with non-EWARS field names
- DHIS2 exports, hospital discharge summaries
- Twitter/social media extracts about symptoms
- Mixed or partially structured data

EXTRACTION RULES:
1. Extract EVERY distinct signal from the input — one signal per
   facility/source/time period combination.
2. Map symptoms to EWARS syndrome codes:
   fever + cough/throat → ILI
   ILI + hospitalisation → SARI
   diarrhoea/vomiting → AGE
   fever + bleeding → HF (always flag HF — triggers EMERGENCY override)
   limb weakness/paralysis → AFP
   fever >38C no focus → UF

3. Infer location from city/region names:
   Guangdong/Foshan/Guangzhou → lon=113.26, lat=23.13, region=guangdong-cn
   Mumbai/Maharashtra → lon=72.88, lat=19.07, region=mumbai-in
   Lagos/Nigeria → lon=3.39, lat=6.45, region=lagos-ng
   Nairobi/Kenya → lon=36.82, lat=-1.29, region=nairobi-ke
   Jakarta/Indonesia → lon=106.85, lat=-6.21, region=jakarta-id
   For other locations, look up approximate coordinates.

4. Infer timestamp from context clues ("last week", "November 2002", "Q3").
   Always produce a valid ISO 8601 date string.

5. Set extraction_confidence:
   HIGH: explicit case count + date + location present
   MEDIUM: count or date inferred from context
   LOW: significant inference needed, uncertain data

6. If nothing medically relevant is in the input, return signals=[] and
   explain in input_summary.

AFTER EXTRACTION:
Store all extracted signals in MongoDB using the MCP insert-many tool:

  Tool: insert-many
  Args: {
    "collection": "signals",
    "documents": [
      {
        "metadata": {
          "signal_type": "<type>",
          "source_id": "<source_id>",
          "region_id": "<region_id>",
          "pathogen_suspected": <null or string>
        },
        "timestamp": {"$date": "<ISO 8601 string>"},
        "location": {"type": "Point", "coordinates": [<lon>, <lat>]},
        "syndrome_codes": ["<codes>"],
        "case_count": <integer>,
        "severity_distribution": {
          "mild": <n>, "moderate": <n>, "severe": <n>
        },
        "age_groups": {"under5": 0, "5_17": 0, "18_60": 0, "over60": 0},
        "raw_text": "<verbatim excerpt>",
        "normalized_by_agent": true,
        "extraction_confidence": "<HIGH|MEDIUM|LOW>",
        "extraction_note": "<string or null>"
      }
    ]
  }

Return a JSON summary with keys:
  signals_extracted, signals_stored, input_summary, extraction_warnings
"""


def create_data_normalisation_agent() -> LlmAgent:
    """
    Creates the DataNormalisationAgent.

    Uses response_schema to enforce Gemini structured output —
    the model is constrained to always return ExtractionResult JSON.
    This prevents the MALFORMED_FUNCTION_CALL problem for the extraction step.
    The MCP insert-many is a separate tool call after extraction.
    """
    return LlmAgent(
        name="data_normalisation",
        model="gemini-2.5-pro",
        description=(
            "Extracts EWARS health signals from any input format "
            "(unstructured text, CSV, JSON, news articles) and stores "
            "normalised documents in MongoDB via MCP."
        ),
        instruction=INSTRUCTION,
        tools=[get_mongo_toolset(read_only=False)],
        # Structured output schema — Gemini enforces this on the extraction step
        output_schema=ExtractionResult,
    )