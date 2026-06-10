# agents/prediction_agent.py
"""
PredictionAgent — forecasts epidemic trajectory from available case data.

Two models depending on data availability:
  Exponential: 2-4 data points (early outbreak, unknown peak)
  SIR:         5+ data points  (can estimate peak time and size)

Uses Gemini structured output to return a clean prediction object.
Also provides narrative interpretation for non-experts.
"""

import math
from typing import Optional
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.genai import types as genai_types


# ── Structured output schemas ─────────────────────────────────────────────────

class WeekPrediction(BaseModel):
    week_number: int           = Field(description="Week number from outbreak start (1, 2, 3...)")
    predicted_cases: float     = Field(description="Predicted case count for this week")
    lower_bound: float         = Field(description="80% confidence interval lower bound")
    upper_bound: float         = Field(description="Upper bound")
    predicted_tier: str        = Field(description="Predicted EWARS tier: WATCH/ALERT/EMERGENCY")


class PredictionOutput(BaseModel):
    model_used: str = Field(
        description="'exponential' or 'SIR' — which model was used and why"
    )
    r_estimate: float = Field(
        description="Basic reproduction number R estimated from data"
    )
    doubling_time_days: Optional[float] = Field(
        default=None,
        description="Estimated doubling time in days (exponential phase)"
    )
    peak_week: Optional[int] = Field(
        default=None,
        description="Estimated week of outbreak peak (SIR model only, null if unknown)"
    )
    peak_cases: Optional[float] = Field(
        default=None,
        description="Estimated peak weekly case count"
    )
    weeks_forecast: list[WeekPrediction] = Field(
        description="Predicted weekly values for next 8 weeks"
    )
    without_intervention: list[WeekPrediction] = Field(
        description=(
            "Counter-factual: predicted curve WITHOUT any public health intervention. "
            "Same length as weeks_forecast. Used to show the 'cost of inaction'."
        )
    )
    narrative: str = Field(
        description=(
            "3-4 sentence plain English interpretation for public health decision-makers. "
            "State the predicted peak, timeline, and key uncertainties."
        )
    )
    confidence_level: str = Field(
        description="HIGH/MEDIUM/LOW — based on number of data points and consistency"
    )
    assumptions: list[str] = Field(
        description="Key assumptions made (e.g. 'no intervention', 'serial interval 5 days')"
    )


# ── Agent instruction ─────────────────────────────────────────────────────────

INSTRUCTION = """
You are an epidemic modelling specialist for EWARS.

Your job is to fit epidemiological models to observed case data and generate
a predicted trajectory for the next 8 weeks.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MODEL SELECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use EXPONENTIAL model when: fewer than 5 data points available.
  Formula: C(t) = C₀ × e^(r×t)
  where r = ln(C_n / C_1) / (n-1)
  doubling_time = ln(2) / r

Use SIR model when: 5 or more data points available.
  Compartments: S (susceptible), I (infected), R (recovered)
  Equations:
    dS/dt = -β×S×I/N
    dI/dt = β×S×I/N - γ×I
    dR/dt = γ×I
  Parameters:
    β = transmission rate (fit from data)
    γ = recovery rate = 1/infectious_period (use 5 days for respiratory)
    R₀ = β/γ
  Fit β by minimising squared error between model I(t) and observed cases.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFIDENCE INTERVALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For 80% confidence band, multiply/divide predicted value by:
  2 data points:  factor = 3.0  (wide uncertainty)
  3-4 points:     factor = 2.0
  5-7 points:     factor = 1.5
  8+ points:      factor = 1.25

lower_bound = predicted / factor
upper_bound = predicted × factor

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIER THRESHOLDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use R estimate and case growth to predict tier:
  R < 1.0 → WATCH (declining)
  R 1.0–1.4 → WATCH
  R 1.4–2.0 → ALERT
  R > 2.0 OR HF syndrome → EMERGENCY

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WITHOUT-INTERVENTION COUNTERFACTUAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generate a second curve assuming NO public health response:
  - R₀ stays constant at initial estimate
  - No reduction in transmission
  - This shows the "cost of inaction" baseline
  - The gap between this and the predicted curve is the estimated
    benefit of current/expected interventions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEW OUTBREAK (no historical comparison)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If this is a new outbreak with no baseline data:
  - Use default R₀ = 2.0 for unknown respiratory pathogens
  - Use R₀ = 1.5 for AGE/waterborne
  - Use R₀ = 3.0 for HF pathogens
  - Note in assumptions: "No historical baseline — default R₀ used"

Return ONLY the JSON matching the output schema. No prose outside JSON.
"""


def create_prediction_agent() -> LlmAgent:
    return LlmAgent(
        name="prediction_agent",
        model="gemini-2.5-pro",
        description=(
            "Fits SIR/exponential epidemic models to case data and generates "
            "8-week predictions with confidence intervals."
        ),
        instruction=INSTRUCTION,
        tools=[],   # Pure computation — no tool calls needed
        output_schema=PredictionOutput,
    )