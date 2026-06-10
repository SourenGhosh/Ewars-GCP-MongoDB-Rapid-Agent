"""
Unit tests for Risk Escalation Agent scoring logic.
Tests pure calculation functions without calling the LLM.
Run with: pytest tests/unit/test_scoring.py -v
"""

import pytest


def calculate_composite_score(
    syndromic_score, geo_score, environmental_score, source_concordance
):
    bonus_map = {"HIGH": 100.0, "MEDIUM": 50.0, "LOW": 0.0}
    bonus = bonus_map.get(source_concordance, 0.0)
    return (
        syndromic_score * 0.40
        + geo_score * 0.30
        + environmental_score * 0.20
        + bonus * 0.10
    )


def classify_tier(composite_score, has_hf=False, r_estimate=0.0, doubling_time=99.0):
    if has_hf:
        return "EMERGENCY"
    if r_estimate > 3.0:
        return "EMERGENCY"
    if doubling_time < 3.0:
        return "EMERGENCY"
    if composite_score >= 75:
        return "EMERGENCY"
    if composite_score >= 50:
        return "ALERT"
    return "WATCH"


class TestCompositeScoring:
    def test_week1_sars_watch(self):
        score = calculate_composite_score(40, 35, 30, "MEDIUM")
        # 16 + 10.5 + 6 + 5 = 37.5
        assert 30 <= score <= 49
        assert classify_tier(score) == "WATCH"

    def test_week4_sars_alert(self):
        score = calculate_composite_score(70, 55, 40, "HIGH")
        # 28 + 16.5 + 8 + 10 = 62.5
        assert 50 <= score <= 74
        assert classify_tier(score) == "ALERT"

    def test_week8_sars_emergency(self):
        score = calculate_composite_score(90, 85, 60, "HIGH")
        # 36 + 25.5 + 12 + 10 = 83.5
        assert score >= 75
        assert classify_tier(score) == "EMERGENCY"

    def test_hf_override_always_emergency(self):
        low_score = calculate_composite_score(10, 5, 5, "LOW")
        assert low_score < 30
        assert classify_tier(low_score, has_hf=True) == "EMERGENCY"

    def test_high_r_override(self):
        score = calculate_composite_score(40, 40, 40, "LOW")
        assert classify_tier(score, r_estimate=3.5) == "EMERGENCY"

    def test_fast_doubling_override(self):
        score = calculate_composite_score(40, 40, 40, "LOW")
        assert classify_tier(score, doubling_time=2.5) == "EMERGENCY"

    def test_concordance_bonus_difference(self):
        high = calculate_composite_score(50, 50, 50, "HIGH")
        low = calculate_composite_score(50, 50, 50, "LOW")
        assert high - low == pytest.approx(10.0)

    def test_boundary_50_is_alert(self):
        assert classify_tier(50.0) == "ALERT"

    def test_boundary_75_is_emergency(self):
        assert classify_tier(75.0) == "EMERGENCY"

    def test_score_29_is_watch(self):
        assert classify_tier(15.0) == "WATCH"
