"""
Seeds 3 years (2021–2023) of synthetic weekly baseline data for
5 representative regions and 6 syndrome codes.

Baselines define 'normal' for the Syndromic Analyst Agent — without
them, anomaly detection cannot function.

Total documents: 5 regions × 6 syndromes × 52 weeks × 3 years = 4,680
Runtime: ~15 seconds
"""

from pymongo import MongoClient, UpdateOne
from datetime import datetime, timezone
import random
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "ewars_db"

# ── Regions ──────────────────────────────────────────────────────────────────
# Each region has a population tier that scales base case counts
REGIONS = {
    "guangdong-cn": {
        "name": "Guangdong, China",
        "population_millions": 130,
        "climate": "subtropical",
        "tier": "large_urban",
    },
    "mumbai-in": {
        "name": "Mumbai, India",
        "population_millions": 21,
        "climate": "tropical_monsoon",
        "tier": "large_urban",
    },
    "lagos-ng": {
        "name": "Lagos, Nigeria",
        "population_millions": 15,
        "climate": "tropical_wet",
        "tier": "large_urban",
    },
    "nairobi-ke": {
        "name": "Nairobi, Kenya",
        "population_millions": 5,
        "climate": "semi_arid",
        "tier": "medium_urban",
    },
    "jakarta-id": {
        "name": "Jakarta, Indonesia",
        "population_millions": 11,
        "climate": "tropical_rainforest",
        "tier": "large_urban",
    },
}

# ── Base weekly case counts by region tier ────────────────────────────────────
# These are cases REPORTED to surveillance systems (fraction of true burden)
BASE_COUNTS_BY_TIER = {
    "large_urban": {
        "ILI": 180,    # Influenza-Like Illness
        "AGE": 120,    # Acute Gastroenteritis
        "SARI": 35,    # Severe Acute Respiratory Infection
        "AFP": 3,      # Acute Flaccid Paralysis
        "UF": 60,      # Undifferentiated Fever
        "HF": 1,       # Haemorrhagic Fever (baseline very low)
    },
    "medium_urban": {
        "ILI": 80,
        "AGE": 55,
        "SARI": 15,
        "AFP": 1,
        "UF": 25,
        "HF": 0,
    },
}

# ── Seasonal multipliers (52 weeks) ──────────────────────────────────────────
# Built with epidemiologically realistic patterns:
# ILI peaks in cool/dry season; AGE peaks during monsoon/flooding;
# SARI tracks ILI but with higher severity; UF peaks dry-hot season;
# AFP and HF have minimal seasonality.

def make_seasonal_profile(syndrome: str, climate: str) -> list:
    """
    Returns a list of 52 weekly multipliers (1.0 = average week).
    Patterns vary by syndrome AND climate zone.
    """
    base = [1.0] * 52

    if syndrome == "ILI":
        if climate in ("subtropical", "semi_arid"):
            # Northern hemisphere-ish: peaks weeks 1-8 (winter) and 45-52
            for i in range(0, 8):   base[i] = 1.6
            for i in range(8, 16):  base[i] = 1.3
            for i in range(16, 36): base[i] = 0.75
            for i in range(36, 44): base[i] = 1.1
            for i in range(44, 52): base[i] = 1.5
        elif climate in ("tropical_monsoon", "tropical_wet", "tropical_rainforest"):
            # Dry season flu peak: weeks 28-40
            for i in range(28, 40): base[i] = 1.5
            for i in range(0, 12):  base[i] = 1.2
            for i in range(12, 28): base[i] = 0.85

    elif syndrome == "AGE":
        if climate in ("tropical_monsoon", "tropical_wet", "tropical_rainforest"):
            # Monsoon season: weeks 20-36 (June-September)
            for i in range(20, 36): base[i] = 1.8
            for i in range(36, 44): base[i] = 1.2
            for i in range(0, 12):  base[i] = 0.85
        else:
            # Moderate year-round with rainy season bump
            for i in range(16, 28): base[i] = 1.4
            for i in range(28, 36): base[i] = 1.2

    elif syndrome == "SARI":
        # Tracks ILI but 2-week lag, higher severity
        ili = make_seasonal_profile("ILI", climate)
        base = [ili[(i - 2) % 52] * 0.9 for i in range(52)]

    elif syndrome == "UF":
        if climate in ("semi_arid", "subtropical"):
            # Hot-dry season: weeks 16-28
            for i in range(16, 28): base[i] = 1.6
            for i in range(28, 40): base[i] = 1.2
        elif climate in ("tropical_monsoon", "tropical_wet"):
            # Pre-monsoon heat: weeks 12-20
            for i in range(12, 20): base[i] = 1.7
            for i in range(20, 36): base[i] = 1.3  # stays elevated in monsoon

    elif syndrome in ("AFP", "HF"):
        # Minimal seasonality — slight elevation in warm wet months
        for i in range(20, 36): base[i] = 1.15

    # Add small random jitter (±5%) to simulate real-world variation
    random.seed(42)  # reproducible
    base = [round(v * random.uniform(0.95, 1.05), 3) for v in base]

    return base


def seed_baselines():
    print("\n========== EWARS Phase 2 — Step 2: Seed Baselines ==========")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    total = 0
    operations = []

    for region_id, region_info in REGIONS.items():
        climate = region_info["climate"]
        tier = region_info["tier"]
        base_counts = BASE_COUNTS_BY_TIER[tier]

        for syndrome, base_count in base_counts.items():
            seasonal = make_seasonal_profile(syndrome, climate)

            for year in [2021, 2022, 2023]:
                # Year-over-year drift: slight increase each year (population growth)
                year_multiplier = 1.0 + (year - 2021) * 0.03

                for week in range(1, 53):
                    multiplier = seasonal[week - 1] * year_multiplier
                    expected = base_count * multiplier

                    # Coefficient of variation varies by syndrome:
                    # AFP/HF have high relative variance (rare events)
                    cv = {
                        "ILI": 0.20, "AGE": 0.22, "SARI": 0.25,
                        "AFP": 0.50, "UF": 0.28, "HF": 0.80
                    }.get(syndrome, 0.25)

                    sd = expected * cv
                    expected = round(expected, 1)
                    sd = max(round(sd, 1), 0.5)  # minimum SD of 0.5

                    doc = {
                        "region_id": region_id,
                        "syndrome": syndrome,
                        "week_of_year": week,
                        "year": year,
                        "expected_count": expected,
                        "std_deviation": sd,
                        "alert_threshold_1": round(expected + sd, 1),
                        "alert_threshold_2": round(expected + 2 * sd, 1),
                        "alert_threshold_3": round(expected + 3 * sd, 1),
                        "data_points_used": random.randint(42, 52),
                        "last_updated": datetime.now(timezone.utc),
                        "region_name": region_info["name"],
                        "climate_zone": climate,
                    }

                    # Upsert — safe to re-run
                    operations.append(UpdateOne(
                        filter={
                            "region_id": region_id,
                            "syndrome": syndrome,
                            "week_of_year": week,
                            "year": year,
                        },
                        update={"$set": doc},
                        upsert=True,
                    ))
                    total += 1

                    # Batch write every 500
                    if len(operations) >= 500:
                        db.baselines.bulk_write(operations, ordered=False)
                        operations = []
                        print(f"  Written {total} baseline docs so far...", end="\r")

    # Flush remaining
    if operations:
        db.baselines.bulk_write(operations, ordered=False)

    count = db.baselines.count_documents({})
    print(f"\n✅ Baseline seeding complete: {count} documents in 'baselines' collection")
    print(f"   Regions: {len(REGIONS)}")
    print(f"   Syndromes: ILI, AGE, SARI, AFP, UF, HF")
    print(f"   Years: 2021, 2022, 2023")
    print(f"   Weeks per year: 52")
    client.close()
    print("=============================================================\n")


if __name__ == "__main__":
    seed_baselines()