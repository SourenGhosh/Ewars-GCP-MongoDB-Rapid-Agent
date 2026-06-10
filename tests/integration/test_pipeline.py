import os

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("CLOUD_RUN_URL", "http://localhost:8080") + "/ewars"
TIMEOUT = 240.0


@pytest.fixture
def api():
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


class TestAPIEndpoints:
    def test_health_check(self, api):
        r = api.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_clusters_active(self, api):
        r = api.get("/clusters/active")
        assert r.status_code == 200
        assert "clusters" in r.json()

    def test_sitreps_list(self, api):
        r = api.get("/sitreps")
        assert r.status_code == 200
        assert "sitreps" in r.json()


class TestSARSReplay:
    def _run(self, api, week):
        r = api.post(
            "/run",
            json={
                "region_id": "guangdong-cn",
                "raw_data_feeds": {},
                "trigger_type": "demo",
                "demo_week": week,
            },
        )
        assert r.status_code == 200, f"Week {week} failed: {r.text[:300]}"
        return r.json()

    def test_week1_watch(self, api):
        data = self._run(api, 1)
        assert data["status"] == "completed"
        assert data["threat_tier"] == "WATCH", (
            f"Week 1 expected WATCH, got {data['threat_tier']}"
        )
        assert data.get("duration_seconds", 999) < 120

    def test_week4_alert(self, api):
        data = self._run(api, 4)
        assert data["status"] == "completed"
        assert data["threat_tier"] == "ALERT", (
            f"Week 4 expected ALERT, got {data['threat_tier']}"
        )

    def test_week8_emergency(self, api):
        data = self._run(api, 8)
        assert data["status"] == "completed"
        assert data["threat_tier"] == "EMERGENCY", (
            f"Week 8 expected EMERGENCY, got {data['threat_tier']}"
        )

    def test_tier_escalation_order(self, api):
        order = {"WATCH": 1, "ALERT": 2, "EMERGENCY": 3}
        w1 = self._run(api, 1)["threat_tier"]
        w4 = self._run(api, 4)["threat_tier"]
        w8 = self._run(api, 8)["threat_tier"]
        assert order[w1] < order[w4], f"Expected W1 < W4, got {w1} vs {w4}"
        assert order[w4] < order[w8], f"Expected W4 < W8, got {w4} vs {w8}"

    def test_week8_sitrep_has_disclaimer(self, api):
        self._run(api, 8)
        r = api.get("/sitreps?limit=5")
        sitreps = r.json()["sitreps"]
        emergency = [s for s in sitreps if s.get("threat_tier") == "EMERGENCY"]
        assert len(emergency) >= 1, "No EMERGENCY SitRep found"
        assert "epidemiologist" in str(emergency[0].get("report", "")).lower(), (
            "Disclaimer not found in SitRep"
        )
