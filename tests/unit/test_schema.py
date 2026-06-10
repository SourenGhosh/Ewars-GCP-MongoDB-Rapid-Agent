"""
Unit tests for Pydantic schema validation.
Run with: pytest tests/unit/test_schema.py -v
"""

import os
import sys
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from mcp.schemas.signal import (
    AgeGroups,
    GeoPoint,
    SeverityDistribution,
    SignalDocument,
    SignalMetadata,
)
from mcp.schemas.threat_assessment import (
    ContributingFactor,
    ThreatAssessmentDocument,
    ThreatTier,
)


def make_signal(**overrides):
    defaults = dict(
        metadata=SignalMetadata(
            signal_type="clinic_visit",
            source_id="test-facility",
            region_id="guangdong-cn",
        ),
        timestamp=datetime(2002, 11, 16, tzinfo=timezone.utc),
        location=GeoPoint(coordinates=[113.13, 23.02]),
        syndrome_codes=["SARI"],
        case_count=8,
        severity_distribution=SeverityDistribution(mild=2, moderate=4, severe=2),
        age_groups=AgeGroups(**{"under5": 0, "5_17": 1, "18_60": 5, "over60": 2}),
        raw_text="Test signal",
        normalized_by_agent=True,
    )
    defaults.update(overrides)
    return SignalDocument(**defaults)


class TestSignalSchema:
    def test_valid_clinic_visit(self):
        doc = make_signal()
        assert doc.case_count == 8
        assert "SARI" in doc.syndrome_codes

    def test_all_valid_syndrome_codes(self):
        for code in ["ILI", "SARI", "AGE", "AFP", "UF", "HF", "NBI"]:
            doc = make_signal(syndrome_codes=[code])
            assert code in doc.syndrome_codes

    def test_invalid_signal_type_rejected(self):
        with pytest.raises(ValidationError):
            SignalMetadata(
                signal_type="bad_type", source_id="test", region_id="guangdong-cn"
            )

    def test_coordinates_lon_lat_order(self):
        point = GeoPoint(coordinates=[113.13, 23.02])
        lon, lat = point.coordinates
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90


class TestThreatAssessmentSchema:
    def test_valid_watch_assessment(self):
        doc = ThreatAssessmentDocument(
            assessment_id="test-uuid-001",
            cluster_id="cluster-001",
            assessed_at=datetime.now(timezone.utc),
            threat_tier=ThreatTier.WATCH,
            confidence=0.65,
            contributing_factors=[
                ContributingFactor(
                    factor="syndromic_elevation",
                    weight=0.4,
                    description="SARI 1.4 SD above baseline",
                )
            ],
            syndromic_score=38.0,
            geo_score=35.0,
            environmental_score=30.0,
            composite_score=35.5,
            recommended_actions=["District health officer review within 24h."],
            escalation_rationale="Single source anomaly below 2-SD threshold.",
            agent_session_id="EWARS-20021116-guangdong-cn",
        )
        assert doc.threat_tier == ThreatTier.WATCH
        assert 0.0 <= doc.confidence <= 1.0

    def test_confidence_above_1_rejected(self):
        with pytest.raises(ValidationError):
            ThreatAssessmentDocument(
                assessment_id="x",
                cluster_id="x",
                assessed_at=datetime.now(timezone.utc),
                threat_tier=ThreatTier.WATCH,
                confidence=1.5,
                contributing_factors=[],
                syndromic_score=30,
                geo_score=30,
                environmental_score=30,
                composite_score=30,
                recommended_actions=[],
                escalation_rationale="test",
                agent_session_id="test",
            )
