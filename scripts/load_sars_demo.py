"""
Loads the SARS 2002/03 outbreak replay data into the signals collection.
Three time points — each should trigger a different threat tier:
  Week 1  (Nov 16 2002) → WATCH  (score ~38)
  Week 4  (Dec 15 2002) → ALERT  (score ~64)
  Week 8  (Jan 20 2003) → EMERGENCY (score ~87)

This is the primary hackathon demo dataset.
All documents marked with demo_tag: "sars_replay" for easy filtering/cleanup.
"""

from pymongo import MongoClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "ewars_db"

SARS_SIGNALS = [

    # ── WEEK 1: Nov 16 2002 ── Expected tier: WATCH ──────────────────────────
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "foshan-hospital-1",
            "region_id": "guangdong-cn",
            "pathogen_suspected": None,
        },
        "timestamp": datetime(2002, 11, 16, 8, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.13, 23.02]},
        "syndrome_codes": ["SARI"],
        "case_count": 8,
        "severity_distribution": {"mild": 2, "moderate": 4, "severe": 2},
        "age_groups": {"under5": 0, "5_17": 1, "18_60": 5, "over60": 2},
        "raw_text": "8 cases atypical pneumonia, 2 healthcare workers among patients, "
                    "chest X-ray shows bilateral infiltrates, not responding to antibiotics",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 1,
    },
    {
        "metadata": {
            "signal_type": "pharmacy_sale",
            "source_id": "foshan-pharmacy-district",
            "region_id": "guangdong-cn",
            "pathogen_suspected": None,
        },
        "timestamp": datetime(2002, 11, 16, 10, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.10, 23.05]},
        "syndrome_codes": ["ILI"],
        "case_count": 340,   # proxy: units of antipyretics sold above baseline
        "severity_distribution": {"mild": 340, "moderate": 0, "severe": 0},
        "age_groups": {"under5": 20, "5_17": 60, "18_60": 220, "over60": 40},
        "raw_text": "Antipyretic (paracetamol/ibuprofen) sales 340 units above weekly baseline. "
                    "Cough suppressant sales also elevated +28%.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 1,
    },
    {
        "metadata": {
            "signal_type": "social_report",
            "source_id": "nlp-feed-guangdong",
            "region_id": "guangdong-cn",
            "pathogen_suspected": None,
        },
        "timestamp": datetime(2002, 11, 17, 14, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.25, 23.15]},
        "syndrome_codes": ["ILI", "SARI"],
        "case_count": 45,   # NLP-extracted symptom reports
        "severity_distribution": {"mild": 30, "moderate": 12, "severe": 3},
        "age_groups": {"under5": 5, "5_17": 10, "18_60": 25, "over60": 5},
        "raw_text": "NLP extract: 45 posts mentioning fever+cough in Foshan/Guangzhou area. "
                    "3 posts mention hospitalisation. Source: pre-processed social feed.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 1,
    },

    # ── WEEK 4: Dec 15 2002 ── Expected tier: ALERT ──────────────────────────
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "guangzhou-hospital-1",
            "region_id": "guangdong-cn",
            "pathogen_suspected": None,
        },
        "timestamp": datetime(2002, 12, 15, 9, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.26, 23.13]},
        "syndrome_codes": ["SARI"],
        "case_count": 47,
        "severity_distribution": {"mild": 5, "moderate": 25, "severe": 17},
        "age_groups": {"under5": 2, "5_17": 4, "18_60": 33, "over60": 8},
        "raw_text": "47 SARI cases this week. 4 confirmed healthcare worker infections. "
                    "ICU capacity at 78%. Novel pneumonia — culture negative for known pathogens.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 4,
    },
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "foshan-hospital-1",
            "region_id": "guangdong-cn",
            "pathogen_suspected": None,
        },
        "timestamp": datetime(2002, 12, 15, 10, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.13, 23.02]},
        "syndrome_codes": ["SARI"],
        "case_count": 31,
        "severity_distribution": {"mild": 3, "moderate": 18, "severe": 10},
        "age_groups": {"under5": 1, "5_17": 3, "18_60": 22, "over60": 5},
        "raw_text": "31 additional SARI cases at Foshan. Total cumulative: 86. "
                    "Doubling time estimated at 9 days.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 4,
    },
    {
        "metadata": {
            "signal_type": "pharmacy_sale",
            "source_id": "guangdong-pharmacy-network",
            "region_id": "guangdong-cn",
            "pathogen_suspected": None,
        },
        "timestamp": datetime(2002, 12, 16, 8, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.20, 23.10]},
        "syndrome_codes": ["ILI", "SARI"],
        "case_count": 890,
        "severity_distribution": {"mild": 890, "moderate": 0, "severe": 0},
        "age_groups": {"under5": 80, "5_17": 150, "18_60": 560, "over60": 100},
        "raw_text": "Pharmacy network report: antipyretic sales 890 units above baseline "
                    "(week-on-week +162%). Antiviral stock depleted at 3 pharmacies.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 4,
    },
    {
        "metadata": {
            "signal_type": "lab_result",
            "source_id": "guangdong-cdc-lab",
            "region_id": "guangdong-cn",
            "pathogen_suspected": "unknown-respiratory-pathogen",
        },
        "timestamp": datetime(2002, 12, 17, 16, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.27, 23.14]},
        "syndrome_codes": ["SARI"],
        "case_count": 12,   # lab-confirmed cases
        "severity_distribution": {"mild": 0, "moderate": 5, "severe": 7},
        "age_groups": {"under5": 0, "5_17": 1, "18_60": 8, "over60": 3},
        "raw_text": "12 samples: negative influenza A/B, negative RSV, negative bacterial culture. "
                    "Electron microscopy pending. Novel coronavirus morphology suspected.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 4,
    },

    # ── WEEK 8: Jan 20 2003 ── Expected tier: EMERGENCY ──────────────────────
    {
        "metadata": {
            "signal_type": "clinic_visit",
            "source_id": "guangdong-multi-facility",
            "region_id": "guangdong-cn",
            "pathogen_suspected": "sars-cov",
        },
        "timestamp": datetime(2003, 1, 20, 8, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.50, 23.20]},
        "syndrome_codes": ["SARI"],
        "case_count": 305,
        "severity_distribution": {"mild": 30, "moderate": 150, "severe": 125},
        "age_groups": {"under5": 10, "5_17": 20, "18_60": 200, "over60": 75},
        "raw_text": "305 SARI cases across 8 facilities. Doubling time 4.2 days. "
                    "28 healthcare workers infected. R estimate 2.4. "
                    "First case reported Hong Kong — cross-border spread confirmed. "
                    "4 deaths reported. Novel coronavirus confirmed by PCR.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 8,
    },
    {
        "metadata": {
            "signal_type": "pharmacy_sale",
            "source_id": "guangdong-pharmacy-network",
            "region_id": "guangdong-cn",
            "pathogen_suspected": "sars-cov",
        },
        "timestamp": datetime(2003, 1, 20, 10, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.30, 23.18]},
        "syndrome_codes": ["SARI", "ILI"],
        "case_count": 3200,
        "severity_distribution": {"mild": 3200, "moderate": 0, "severe": 0},
        "age_groups": {"under5": 200, "5_17": 500, "18_60": 2100, "over60": 400},
        "raw_text": "Pharmacy network: complete depletion of antivirals, N95 masks. "
                    "Antipyretic sales 3200 units above baseline (+850% vs 8 weeks ago).",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 8,
    },
    {
        "metadata": {
            "signal_type": "social_report",
            "source_id": "nlp-feed-guangdong",
            "region_id": "guangdong-cn",
            "pathogen_suspected": "sars-cov",
        },
        "timestamp": datetime(2003, 1, 21, 6, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.45, 23.22]},
        "syndrome_codes": ["SARI"],
        "case_count": 1450,
        "severity_distribution": {"mild": 900, "moderate": 400, "severe": 150},
        "age_groups": {"under5": 80, "5_17": 200, "18_60": 950, "over60": 220},
        "raw_text": "NLP extract: 1450 symptom reports, fear of hospital spread, "
                    "healthcare worker deaths mentioned. Cross-province travel reports.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 8,
    },
    {
        "metadata": {
            "signal_type": "lab_result",
            "source_id": "guangdong-cdc-lab",
            "region_id": "guangdong-cn",
            "pathogen_suspected": "sars-cov",
        },
        "timestamp": datetime(2003, 1, 21, 12, 0, tzinfo=timezone.utc),
        "location": {"type": "Point", "coordinates": [113.27, 23.14]},
        "syndrome_codes": ["SARI"],
        "case_count": 89,
        "severity_distribution": {"mild": 0, "moderate": 30, "severe": 59},
        "age_groups": {"under5": 2, "5_17": 7, "18_60": 60, "over60": 20},
        "raw_text": "89 PCR-confirmed novel coronavirus. CFR in hospitalised cases: 9.3%. "
                    "Genome sequencing underway. IHR notification prepared.",
        "normalized_by_agent": False,
        "demo_tag": "sars_replay",
        "demo_week": 8,
    },
]


def load_sars_demo():
    print("\n========== EWARS Phase 2 — Step 3: SARS Demo Data ==========")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    # Clear any existing SARS demo data (idempotent)
    deleted = db.signals.delete_many({"demo_tag": "sars_replay"})
    print(">>>>>>>", deleted)
    if deleted.deleted_count:
        print(f"  ↩ Cleared {deleted.deleted_count} existing SARS demo docs")

    inserts = db.signals.insert_many(SARS_SIGNALS)
    print(inserts)
    # Verify by week
    for week in [1, 4, 8]:
        count = db.signals.count_documents({"demo_tag": "sars_replay", "demo_week": week})
        tier = {1: "WATCH", 4: "ALERT", 8: "EMERGENCY"}[week]
        print(f"  ✅ Week {week} ({tier}): {count} signal documents loaded")

    print(f"\n  Total SARS signals: {len(SARS_SIGNALS)}")
    print("=============================================================\n")
    client.close()


if __name__ == "__main__":
    load_sars_demo()