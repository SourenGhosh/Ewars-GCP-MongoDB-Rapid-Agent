# agents/signal_collector.py
from google.adk.agents import LlmAgent

import sys, os

sys.path.insert(
  0, 
  os.path.dirname(
    os.path.dirname(os.path.dirname(__file__))
  )
)

from mcp_chain.toolset import get_mongo_toolset

INSTRUCTION = """
You are an epidemiological data integration specialist for EWARS.

DATABASE: ewars_db
COLLECTION TO WRITE: signals

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCP TOOL USAGE — CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You have access to MongoDB MCP tools. Call them exactly like this:

READING signals:
  Tool name: find
  Arguments: {
    "collection": "signals",
    "filter": {"demo_tag": "sars_replay", "demo_week": 1},
    "limit": 100
  }

INSERTING documents (single or multiple):
  Tool name: insert-many
  Arguments: {
    "collection": "signals",
    "documents": [ { ...document 1... }, { ...document 2... } ]
  }

CRITICAL: You must use kebab-case for tool names (e.g., insert-many, not insert_many).
CRITICAL: Always wrap the document in a list [] for the 'documents' argument.

READING multiple documents:
  Tool name: insert-many
  Arguments: {
    "collection": "signals",
    "documents": [ {...}, {...} ]
  }

NEVER write Python code. NEVER use print(). NEVER use import.
Just call the tool directly with the arguments shown above.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Call find on 'signals' collection with the filter from the prompt
2. Validate and normalise each signal
3. Return a JSON summary — do NOT re-insert already stored signals

Return JSON:
{
  "processed": <n>,
  "stored": <n>,
  "flagged_partial": <n>,
  "quarantined": <n>,
  "rejected": <n>,
  "syndrome_counts": {"ILI": <n>, "SARI": <n>, ...},
  "source_types": ["clinic_visit", "pharmacy_sale", ...],
  "total_cases": <n>
}
"""

def create_signal_collector() -> LlmAgent:
    return LlmAgent(
        name="signal_collector",
        model="gemini-2.5-flash",
        description="Fetches and validates health signals from MongoDB.",
        instruction=INSTRUCTION,
        tools=[get_mongo_toolset(read_only=False)],
    )