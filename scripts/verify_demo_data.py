"""
Run this after all Phase 2 steps.
All checks must pass before moving to Phase 3.
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "ewars_db"


def verify():
    print("\n========== EWARS Phase 2 — Verification ==========")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    results = {}
    all_ok = True

    # 1. All 7 collections exist
    collections = set(db.list_collection_names())
    required = {"signals", "baselines", "clusters", "environmental_snapshots",
                "threat_assessments", "situation_reports", "agent_sessions"}
    missing = required - collections
    results["Collections (7 required)"] = (
        "✅ All present" if not missing else f"❌ Missing: {missing}"
    )

    # 2. signals is time-series
    try:
        info = db.command("listCollections", filter={"name": "signals"})
        first = list(info["cursor"]["firstBatch"])[0]
        is_ts = first.get("options", {}).get("timeseries") is not None
        results["signals is time-series"] = "✅ Confirmed" if is_ts else "❌ NOT time-series"
    except Exception as e:
        results["signals is time-series"] = f"❌ {e}"

    # 3. Baseline count
    baseline_count = db.baselines.count_documents({})
    results[f"Baselines seeded (need 4680)"] = (
        f"✅ {baseline_count} documents"
        if baseline_count >= 4680
        else f"❌ Only {baseline_count} — re-run seed_baselines.py"
    )

    # 4. Baseline coverage — spot check
    spot = db.baselines.find_one({
        "region_id": "guangdong-cn", "syndrome": "ILI",
        "week_of_year": 46, "year": 2023
    })
    results["Baseline spot-check (guangdong ILI week46/2023)"] = (
        f"✅ expected={spot['expected_count']}, 3SD threshold={spot['alert_threshold_3']}"
        if spot else "❌ NOT FOUND — seed_baselines.py may have failed"
    )

    # 5. SARS demo signals
    sars_count = db.signals.count_documents({"demo_tag": "sars_replay"})
    sars_w1 = db.signals.count_documents({"demo_tag": "sars_replay", "demo_week": 1})
    sars_w4 = db.signals.count_documents({"demo_tag": "sars_replay", "demo_week": 4})
    sars_w8 = db.signals.count_documents({"demo_tag": "sars_replay", "demo_week": 8})
    results["SARS demo signals (W1/W4/W8)"] = (
        f"✅ {sars_count} total — W1:{sars_w1} W4:{sars_w4} W8:{sars_w8}"
        if sars_count >= 11
        else f"❌ Only {sars_count} — re-run load_sars_demo.py"
    )

    # 6. Scenario signals
    cholera_count = db.signals.count_documents({"demo_tag": "cholera_scenario"})
    dengue_count  = db.signals.count_documents({"demo_tag": "dengue_scenario"})
    results["Cholera scenario signals"] = (
        f"✅ {cholera_count}" if cholera_count >= 4 else f"❌ Only {cholera_count}"
    )
    results["Dengue scenario signals"] = (
        f"✅ {dengue_count}" if dengue_count >= 3 else f"❌ Only {dengue_count}"
    )

    # 7. Environmental snapshots
    env_count = db.environmental_snapshots.count_documents({})
    results["Environmental snapshots"] = (
        f"✅ {env_count}" if env_count >= 2 else f"❌ Only {env_count}"
    )

    # 8. Geospatial index on signals
    signal_indexes = {idx["name"] for idx in db.signals.list_indexes()}
    results["signals 2dsphere index"] = (
        "✅ Present" if "signals_location_2dsphere" in signal_indexes
        else "❌ MISSING — re-run setup_indexes.py"
    )

    # 9. Geospatial index on clusters
    cluster_indexes = {idx["name"] for idx in db.clusters.list_indexes()}
    results["clusters 2dsphere index"] = (
        "✅ Present" if "clusters_centroid_2dsphere" in cluster_indexes
        else "❌ MISSING"
    )

    # 10. Quick $geoNear test (the key query Geo-Cluster Agent uses)
    try:
        pipeline = [
            {
                "$geoNear": {
                    "near": {
                        "type": "Point",
                        "coordinates": [113.26, 23.13]
                    },
                    "distanceField": "distance_m",
                    "maxDistance": 100000,
                    "spherical": True,
                    "key": "location"
                }
            },
            {"$limit": 3}
        ]

        geo_results = list(db.signals.aggregate(pipeline))

        results["$geoNear aggregation test"] = (
            f"✅ Returned {len(geo_results)} nearby signals"
        )

    except Exception as e:
        results["$geoNear aggregation test"] = f"❌ {e}"

    # Print results
    print(f"\n  Database: {DB_NAME}\n")
    for check, result in results.items():
        if "❌" in result:
            all_ok = False
        print(f"  {result}")
        print(f"     └─ {check}")

    print("\n" + "=" * 50)
    if all_ok:
        print("✅ Phase 2 COMPLETE — all checks passed")
        print("   → Ready for Phase 3: Agent Pipeline Implementation")
    else:
        print("❌ Some checks failed — fix them before Phase 3")
    print("=" * 50 + "\n")
    client.close()
    return all_ok


if __name__ == "__main__":
    verify()