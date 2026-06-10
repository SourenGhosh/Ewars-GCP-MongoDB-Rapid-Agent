from pymongo import MongoClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URI"))["ewars_db"]

EBOLA_SIGNALS = [
    # Week 1 — Dec 2013 — index case Meliandou village, Guinea
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "gueckedou-hospital",
            "region_id": "gueckedou-gn",
            "pathogen_suspected": None,
        },
        "timestamp": datetime(2013, 12, 26, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [-10.13, 8.57]},
        "syndrome_codes": ["HF"],    # HF = Haemorrhagic Fever → auto EMERGENCY override
        "case_count": 4,
        "severity_distribution": {"mild": 0, "moderate": 1, "severe": 3},
        "age_groups": {"under5": 2, "5_17": 0, "18_60": 2, "over60": 0},
        "raw_text": (
            "4 cases severe haemorrhagic fever, 3 deaths. "
            "Bloody diarrhoea, vomiting. Index case 2-year-old child."
        ),
        "normalized_by_agent": False,
        "demo_tag": "ebola_replay",
        "demo_week": 1,
    },
    # Week 8 — Feb 2014 — spread to Conakry capital
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "conakry-donka-hospital",
            "region_id": "gueckedou-gn",
            "pathogen_suspected": "filovirus-suspected",
        },
        "timestamp": datetime(2014, 2, 9, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [-13.68, 9.52]},
        "syndrome_codes": ["HF"],
        "case_count": 29,
        "severity_distribution": {"mild": 0, "moderate": 5, "severe": 24},
        "age_groups": {"under5": 4, "5_17": 3, "18_60": 18, "over60": 4},
        "raw_text": (
            "29 HF cases, 18 deaths (CFR 62%). Healthcare worker deaths: 2. "
            "Spread from forest region to capital Conakry. "
            "Cross-border cases suspected Sierra Leone."
        ),
        "normalized_by_agent": False,
        "demo_tag": "ebola_replay",
        "demo_week": 8,
    },
]

# Also seed a baseline for the new region
GUINEA_BASELINES = []
for syndrome in ["ILI", "AGE", "SARI", "AFP", "UF", "HF"]:
    for year in [2011, 2012, 2013]:
        for week in range(1, 53):
            base = {"ILI": 40, "AGE": 30, "SARI": 8, "AFP": 1, "UF": 15, "HF": 0}[syndrome]
            sd = base * 0.3
            GUINEA_BASELINES.append({
                "region_id": "gueckedou-gn",
                "syndrome": syndrome,
                "week_of_year": week,
                "year": year,
                "expected_count": round(base, 1),
                "std_deviation": round(sd, 1),
                "alert_threshold_1": round(base + sd, 1),
                "alert_threshold_2": round(base + 2*sd, 1),
                "alert_threshold_3": round(base + 3*sd, 1),
                "data_points_used": 45,
                "last_updated": datetime.now(timezone.utc),
            })

db.signals.delete_many({"demo_tag": "ebola_replay"})
db.signals.insert_many(EBOLA_SIGNALS)
db.baselines.insert_many(GUINEA_BASELINES)
print(f"Loaded {len(EBOLA_SIGNALS)} Ebola signals + {len(GUINEA_BASELINES)} baselines")