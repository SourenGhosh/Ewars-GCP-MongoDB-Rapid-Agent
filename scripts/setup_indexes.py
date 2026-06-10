"""
Creates all 6 EWARS collections with correct types and indexes.
Run once before seeding. Safe to re-run (skips existing collections).

Collections:
  signals               — time-series (MongoDB native)
  baselines             — historical epidemic thresholds
  clusters              — detected disease clusters (geospatial)
  environmental_snapshots — weather + vector risk snapshots
  threat_assessments    — Risk Escalation Agent outputs
  situation_reports     — Alert Synthesis Agent SitReps
  agent_sessions        — pipeline run audit trail
"""

from pymongo import MongoClient, GEOSPHERE, DESCENDING, ASCENDING, TEXT
from pymongo.errors import CollectionInvalid, OperationFailure
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "ewars_db"


def create_collection_safe(db, name: str, **kwargs):
    """Create collection if it doesn't exist. Skip if already present."""
    if name in db.list_collection_names():
        print(f"  ↩ '{name}' already exists — skipping creation")
        return db[name]
    try:
        coll = db.create_collection(name, **kwargs)
        print(f"  ✅ Created collection: {name}")
        return coll
    except CollectionInvalid:
        print(f"  ↩ '{name}' race-created — skipping")
        return db[name]


def setup_indexes(db):

    # ─────────────────────────────────────────────
    # 1. signals — MongoDB native time-series
    # ─────────────────────────────────────────────
    # NOTE: time-series collections require M10+ on Atlas.
    # timeField must be the top-level timestamp field.
    # metaField holds all metadata for efficient partitioning.
    create_collection_safe(
        db, "signals",
        timeseries={
            "timeField": "timestamp",
            "metaField": "metadata",
            "granularity": "hours",          # hour-level bucketing
        },
        # expireAfterSeconds=60 * 60 * 24 * 365  # auto-expire after 1 year
    )

    # Geospatial index — powers $geoNear in Geo-Cluster Agent
    try:
        db.signals.create_index([("location", GEOSPHERE)], name="signals_location_2dsphere")
        # Compound indexes for common query patterns
        db.signals.create_index(
            [("metadata.region_id", ASCENDING), ("timestamp", DESCENDING)],
            name="signals_region_time"
        )
        db.signals.create_index(
            [("metadata.signal_type", ASCENDING), ("timestamp", DESCENDING)],
            name="signals_type_time"
        )
        # db.signals.create_index(
        #     [("syndrome_codes", ASCENDING), ("timestamp", DESCENDING)],
        #     name="signals_syndrome_time"
        # )
        db.signals.create_index(
            [("metadata.source_id", ASCENDING), ("timestamp", DESCENDING)],
            name="signals_source_time"
        )
        print("  ✅ signals indexes created")
    except OperationFailure as e:
        print(f"  ⚠ signals index note: {e}")

    # ─────────────────────────────────────────────
    # 2. baselines — historical thresholds
    # ─────────────────────────────────────────────
    create_collection_safe(db, "baselines")
    db.baselines.create_index(
        [("region_id", ASCENDING), ("syndrome", ASCENDING),
         ("week_of_year", ASCENDING), ("year", DESCENDING)],
        name="baselines_lookup",
        unique=True     # one baseline doc per region+syndrome+week+year
    )
    print("  ✅ baselines indexes created")

    # ─────────────────────────────────────────────
    # 3. clusters — active disease clusters
    # ─────────────────────────────────────────────
    create_collection_safe(db, "clusters")
    db.clusters.create_index([("centroid", GEOSPHERE)], name="clusters_centroid_2dsphere")
    db.clusters.create_index(
        [("status", ASCENDING), ("detected_at", DESCENDING)],
        name="clusters_status_time"
    )
    db.clusters.create_index([("cluster_id", ASCENDING)], name="clusters_id", unique=True)
    print("  ✅ clusters indexes created")

    # ─────────────────────────────────────────────
    # 4. environmental_snapshots
    # ─────────────────────────────────────────────
    create_collection_safe(db, "environmental_snapshots")
    db.environmental_snapshots.create_index(
        [("location", GEOSPHERE)], name="env_location_2dsphere"
    )
    db.environmental_snapshots.create_index(
        [("region_id", ASCENDING), ("captured_at", DESCENDING)],
        name="env_region_time"
    )
    print("  ✅ environmental_snapshots indexes created")

    # ─────────────────────────────────────────────
    # 5. threat_assessments
    # ─────────────────────────────────────────────
    create_collection_safe(db, "threat_assessments")
    db.threat_assessments.create_index(
        [("cluster_id", ASCENDING), ("assessed_at", DESCENDING)],
        name="threat_cluster_time"
    )
    db.threat_assessments.create_index(
        [("threat_tier", ASCENDING), ("assessed_at", DESCENDING)],
        name="threat_tier_time"
    )
    print("  ✅ threat_assessments indexes created")

    # ─────────────────────────────────────────────
    # 6. situation_reports
    # ─────────────────────────────────────────────
    create_collection_safe(db, "situation_reports")
    db.situation_reports.create_index(
        [("cluster_id", ASCENDING), ("generated_at", DESCENDING)],
        name="sitrep_cluster_time"
    )
    db.situation_reports.create_index(
        [("status", ASCENDING), ("generated_at", DESCENDING)],
        name="sitrep_status_time"
    )
    db.situation_reports.create_index(
        [("threat_tier", ASCENDING)],
        name="sitrep_tier"
    )
    print("  ✅ situation_reports indexes created")

    # ─────────────────────────────────────────────
    # 7. agent_sessions — pipeline audit trail
    # ─────────────────────────────────────────────
    create_collection_safe(db, "agent_sessions")
    db.agent_sessions.create_index(
        [("region_id", ASCENDING), ("triggered_at", DESCENDING)],
        name="sessions_region_time"
    )
    db.agent_sessions.create_index(
        [("pipeline_status", ASCENDING)],
        name="sessions_status"
    )
    print("  ✅ agent_sessions indexes created")


def main():
    print("\n========== EWARS Phase 2 — Step 1: Collections + Indexes ==========")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    print(f"\n📦 Database: {DB_NAME}")
    print("Creating collections...\n")
    setup_indexes(db)

    # Confirm
    collections = db.list_collection_names()
    expected = ["signals", "baselines", "clusters", "environmental_snapshots",
                "threat_assessments", "situation_reports", "agent_sessions"]
    missing = [c for c in expected if c not in collections]

    print(f"\n📋 Collections present: {sorted(collections)}")
    if missing:
        print(f"❌ Missing: {missing}")
    else:
        print("✅ All 7 collections created successfully")

    client.close()
    print("====================================================================\n")


if __name__ == "__main__":
    main()