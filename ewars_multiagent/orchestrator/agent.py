

"""
EWARS agents — individual factory functions.
Each agent is scoped to exactly one pipeline stage.
The pipeline_runner.py orchestrates them with isolated prompts.

No more single root_agent for the full pipeline.
app/agent.py now exports individual create_*() functions.
"""

from google.adk.agents import LlmAgent

import os
import sys

from google.adk.agents import SequentialAgent, ParallelAgent

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp_chain.toolset import get_mongo_toolset

from environmental_agent.environmental import fetch_weather
from google.adk.tools import FunctionTool


def create_signal_collector() -> LlmAgent:
    return LlmAgent(
        name="signal_collector",
        model="gemini-2.5-flash",
        description="Fetches and validates health signals from MongoDB signals collection.",
        instruction=(
            "You are the Signal Collector agent. "
            "Follow the exact instructions in the user message. "
            "Call MCP tools directly — never write Python code. "
            "Return only the JSON specified in the prompt."
        ),
        tools=[get_mongo_toolset(read_only=True)],
    )


def create_syndromic_analyst() -> LlmAgent:
    return LlmAgent(
        name="syndromic_analyst",
        model="gemini-2.5-flash",   # Flash sufficient for threshold comparison
        description="Detects syndromic anomalies by comparing signals to baselines.",
        instruction=(
            "You are the Syndromic Analyst agent. "
            "Follow the exact instructions in the user message. "
            "Call MCP tools directly — never write Python code. "
            "Return only the JSON specified in the prompt."
        ),
        tools=[get_mongo_toolset(read_only=True)],
    )


def create_geo_cluster() -> LlmAgent:
    return LlmAgent(
        name="geo_cluster",
        model="gemini-2.5-flash",
        description="Identifies geographic clusters from signals (read-only analysis).",
        instruction=(
            "You are the Geo-Cluster agent. "
            "Follow the exact instructions in the user message. "
            "Call MCP find tool to read signals. "
            "Do NOT call insert-many, update-many, or any write tools. "
            "Return only the JSON specified in the prompt."
        ),
        tools=[get_mongo_toolset(read_only=True)],
    )


def create_environmental() -> LlmAgent:
    return LlmAgent(
        name="environmental",
        model="gemini-2.5-flash",
        description="Assesses environmental risk using weather data.",
        instruction=(
            "You are the Environmental agent. "
            "Follow the exact instructions in the user message. "
            "Call fetch_weather with the exact latitude and longitude from the prompt. "
            "Return only the JSON specified in the prompt."
        ),
        tools=[
            get_mongo_toolset(read_only=True),
            FunctionTool(func=fetch_weather),
        ],
    )


def create_risk_escalation() -> LlmAgent:
    return LlmAgent(
        name="risk_escalation",
        model="gemini-2.5-flash",   # Downgraded — scoring is arithmetic not reasoning
        description="Classifies threat tier and writes threat assessment to MongoDB.",
        instruction=(
            "You are the Risk Escalation agent. "
            "Follow the exact instructions in the user message. "
            "The composite_score is pre-calculated in the prompt — use it directly. "
            "ONLY insert to threat_assessments collection. "
            "Return only the JSON specified in the prompt."
        ),
        tools=[get_mongo_toolset(read_only=False)],
    )


def create_alert_synthesis() -> LlmAgent:
    return LlmAgent(
        name="alert_synthesis",
        model="gemini-2.5-pro",    # Pro needed for SitRep writing quality
        description="Writes WHO-style SitRep and inserts to situation_reports.",
        instruction=(
            "You are the Alert Synthesis agent. "
            "Follow the exact instructions in the user message. "
            "ONLY insert to situation_reports collection. "
            "Return only the JSON specified in the prompt."
        ),
        tools=[get_mongo_toolset(read_only=False)],
    )


# Legacy root_agent for adk web playground (not used in production pipeline)
# pipeline_runner.py is the production orchestrator
from google.adk.agents import SequentialAgent

root_agent = SequentialAgent(
    name="ewars_pipeline",
    description="EWARS pipeline (dev/playground only — use pipeline_runner in production)",
    sub_agents=[
        create_signal_collector(),
        create_syndromic_analyst(),
    ],
)