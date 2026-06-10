"""
Loads two additional demo scenarios for the hackathon:
  1. Cholera scenario — flood + AGE spike in Lagos (ALERT tier)
  2. Dengue scenario  — vector conditions + ILI spike in Jakarta (WATCH→ALERT)

These demonstrate EWARS works beyond SARS — shows system generalisability.
"""

from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "ewars_db"

# Current date signals (so anomaly detection uses 2023 baselines)
NOW = datetime(2023, 8, 14, tzinfo=timezone.utc)   # Week 33 — monsoon season

CHOLERA_SIGNALS = [
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "lagos-general-hospital",
            "region_id": "lagos-ng",
            "pathogen_suspected": "vibrio-cholerae",
        },
        "timestamp": NOW,
        "location": {"type": "Point", "coordinates": [3.38, 6.45]},
        "syndrome_codes": ["AGE"],
        "case_count": 287,
        "severity_distribution": {"mild": 80, "moderate": 140, "severe": 67},
        "age_groups": {"under5": 95, "5_17": 62, "18_60": 110, "over60": 20},
        "raw_text": "287 AGE cases following flooding in Mainland Lagos. "
                    "Severe dehydration, rice-water stools reported. "
                    "Same water source for 3 affected communities.",
        "normalized_by_agent": False,
        "demo_tag": "cholera_scenario",
    },
    {
        "metadata": {
            "signal_type": "pharmacy_sale",
            "source_id": "lagos-pharmacy-network",
            "region_id": "lagos-ng",
            "pathogen_suspected": None,
        },
        "timestamp": NOW - timedelta(hours=6),
        "location": {"type": "Point", "coordinates": [3.35, 6.47]},
        "syndrome_codes": ["AGE"],
        "case_count": 520,
        "severity_distribution": {"mild": 520, "moderate": 0, "severe": 0},
        "age_groups": {"under5": 100, "5_17": 130, "18_60": 250, "over60": 40},
        "raw_text": "ORS (oral rehydration salts) sales 520 units above baseline. "
                    "Zinc and metronidazole also elevated.",
        "normalized_by_agent": False,
        "demo_tag": "cholera_scenario",
    },
    {
        "metadata": {
            "signal_type": "social_report",
            "source_id": "nlp-feed-lagos",
            "region_id": "lagos-ng",
            "pathogen_suspected": None,
        },
        "timestamp": NOW - timedelta(hours=2),
        "location": {"type": "Point", "coordinates": [3.40, 6.43]},
        "syndrome_codes": ["AGE"],
        "case_count": 183,
        "severity_distribution": {"mild": 100, "moderate": 60, "severe": 23},
        "age_groups": {"under5": 45, "5_17": 38, "18_60": 80, "over60": 20},
        "raw_text": "NLP extract: 183 reports of diarrhoea/vomiting after flooding. "
                    "Community reports flooded latrines, contaminated wells.",
        "normalized_by_agent": False,
        "demo_tag": "cholera_scenario",
    },
    # Environmental context for this scenario
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "lagos-satellite-clinic-2",
            "region_id": "lagos-ng",
            "pathogen_suspected": "vibrio-cholerae",
        },
        "timestamp": NOW - timedelta(days=1),
        "location": {"type": "Point", "coordinates": [3.42, 6.41]},
        "syndrome_codes": ["AGE"],
        "case_count": 145,
        "severity_distribution": {"mild": 40, "moderate": 70, "severe": 35},
        "age_groups": {"under5": 55, "5_17": 35, "18_60": 45, "over60": 10},
        "raw_text": "145 AGE prior day — cluster expanding. IV fluid supply depleted.",
        "normalized_by_agent": False,
        "demo_tag": "cholera_scenario",
    },
]

DENGUE_SIGNALS = [
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "jakarta-rscm-hospital",
            "region_id": "jakarta-id",
            "pathogen_suspected": "dengue-virus",
        },
        "timestamp": NOW - timedelta(days=3),
        "location": {"type": "Point", "coordinates": [106.85, -6.21]},
        "syndrome_codes": ["UF", "HF"],
        "case_count": 94,
        "severity_distribution": {"mild": 40, "moderate": 42, "severe": 12},
        "age_groups": {"under5": 28, "5_17": 35, "18_60": 28, "over60": 3},
        "raw_text": "94 undifferentiated fever + 12 with haemorrhagic signs. "
                    "Positive NS1 antigen in 34 cases. Dengue season early this year.",
        "normalized_by_agent": False,
        "demo_tag": "dengue_scenario",
    },
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "jakarta-persahabatan-hospital",
            "region_id": "jakarta-id",
            "pathogen_suspected": "dengue-virus",
        },
        "timestamp": NOW - timedelta(days=2),
        "location": {"type": "Point", "coordinates": [106.88, -6.19]},
        "syndrome_codes": ["UF", "HF"],
        "case_count": 118,
        "severity_distribution": {"mild": 45, "moderate": 55, "severe": 18},
        "age_groups": {"under5": 38, "5_17": 42, "18_60": 33, "over60": 5},
        "raw_text": "118 dengue-suspected cases. Week-over-week increase 26%. "
                    "Aedes aegypti trap index elevated in North Jakarta.",
        "normalized_by_agent": False,
        "demo_tag": "dengue_scenario",
    },
    {
        "metadata": {
            "signal_type": "pharmacy_sale",
            "source_id": "jakarta-pharmacy-network",
            "region_id": "jakarta-id",
            "pathogen_suspected": None,
        },
        "timestamp": NOW - timedelta(days=1),
        "location": {"type": "Point", "coordinates": [106.82, -6.23]},
        "syndrome_codes": ["UF"],
        "case_count": 680,
        "severity_distribution": {"mild": 680, "moderate": 0, "severe": 0},
        "age_groups": {"under5": 80, "5_17": 160, "18_60": 380, "over60": 60},
        "raw_text": "Paracetamol sales 680 units above baseline. "
                    "DEET insect repellent sales up 340% — community awareness.",
        "normalized_by_agent": False,
        "demo_tag": "dengue_scenario",
    },
]

# Environmental snapshots for the scenarios
ENVIRONMENTAL_SNAPSHOTS = [
    {
        "region_id": "lagos-ng",
        "captured_at": NOW,
        "location": {"type": "Point", "coordinates": [3.39, 6.45]},
        "weather": {
            "temp_celsius": 27.4,
            "humidity_percent": 92,
            "rainfall_mm_7d": 187.3,
            "flood_risk": True,
        },
        "vector_risk": {
            "dengue_aedes_index": 0.45,
            "malaria_anopheles_index": 0.68,
            "temperature_suitable_for_transmission": True,
        },
        "population_density_per_km2": 6871,
        "sanitation_index": 0.28,
        "risk_amplifiers": ["flooding", "displacement"],
        "demo_tag": "cholera_scenario",
    },
    {
        "region_id": "jakarta-id",
        "captured_at": NOW - timedelta(days=1),
        "location": {"type": "Point", "coordinates": [106.85, -6.21]},
        "weather": {
            "temp_celsius": 29.1,
            "humidity_percent": 85,
            "rainfall_mm_7d": 62.4,
            "flood_risk": False,
        },
        "vector_risk": {
            "dengue_aedes_index": 0.82,      # HIGH — key amplifier
            "malaria_anopheles_index": 0.15,
            "temperature_suitable_for_transmission": True,
        },
        "population_density_per_km2": 15900,
        "sanitation_index": 0.52,
        "risk_amplifiers": ["mass_gathering"],
        "demo_tag": "dengue_scenario",
    },
]


def load_scenarios():
    print("\n========== EWARS Phase 2 — Step 4: Scenario Data ==========")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    # Clear existing scenario data
    for tag in ["cholera_scenario", "dengue_scenario"]:
        db.signals.delete_many({"demo_tag": tag})
        db.environmental_snapshots.delete_many({"demo_tag": tag})

    # Load signals
    db.signals.insert_many(CHOLERA_SIGNALS)
    db.signals.insert_many(DENGUE_SIGNALS)
    db.environmental_snapshots.insert_many(ENVIRONMENTAL_SNAPSHOTS)

    print(f"  ✅ Cholera scenario: {len(CHOLERA_SIGNALS)} signals loaded (Lagos)")
    print(f"  ✅ Dengue scenario:  {len(DENGUE_SIGNALS)} signals loaded (Jakarta)")
    print(f"  ✅ Environmental snapshots: {len(ENVIRONMENTAL_SNAPSHOTS)} loaded")
    print("=============================================================\n")
    client.close()


if __name__ == "__main__":
    load_scenarios()