"""Tests for the report generator."""
import pytest
from app.services.report_generator import ReportGenerator, calculate_score


# ---------------------------------------------------------------------------
# Score calculation tests
# ---------------------------------------------------------------------------

def test_score_high_cap_rate():
    data = {"cap_rate": 0.07, "regulation_risk_score": 20, "avg_occupancy": 0.80,
            "supply_growth_pct_12mo": 2.0, "neighborhood_score": 75, "probability_of_loss": 0.05}
    score, rec = calculate_score(data)
    assert score >= 70
    assert rec in ("strong_buy", "buy")


def test_score_low_cap_rate():
    data = {"cap_rate": 0.005, "regulation_risk_score": 80, "avg_occupancy": 0.40,
            "supply_growth_pct_12mo": 15.0, "neighborhood_score": 30, "probability_of_loss": 0.60}
    score, rec = calculate_score(data)
    assert score < 40
    assert rec in ("avoid", "strong_avoid")


def test_score_bounds():
    # Score always between 0-100
    for cap in [-0.05, 0, 0.03, 0.10]:
        data = {"cap_rate": cap, "regulation_risk_score": 50, "avg_occupancy": 0.65,
                "supply_growth_pct_12mo": 4.0, "neighborhood_score": 50, "probability_of_loss": 0.25}
        score, _ = calculate_score(data)
        assert 0 <= score <= 100


def test_recommendation_tiers():
    scores_and_recs = [
        ({"cap_rate": 0.06, "regulation_risk_score": 15, "avg_occupancy": 0.82,
          "supply_growth_pct_12mo": 1.0, "neighborhood_score": 80, "probability_of_loss": 0.05}, "strong_buy"),
    ]
    for data, expected_rec in scores_and_recs:
        _, rec = calculate_score(data)
        assert rec == expected_rec, f"Expected {expected_rec}, got {rec}"


def test_regulation_risk_affects_score():
    base = {"cap_rate": 0.05, "avg_occupancy": 0.72, "supply_growth_pct_12mo": 4.0,
            "neighborhood_score": 60, "probability_of_loss": 0.20}
    low_risk = {**base, "regulation_risk_score": 10}
    high_risk = {**base, "regulation_risk_score": 90}
    score_low, _ = calculate_score(low_risk)
    score_high, _ = calculate_score(high_risk)
    assert score_low > score_high


# ---------------------------------------------------------------------------
# Markdown generation tests
# ---------------------------------------------------------------------------

def test_markdown_contains_address():
    gen = ReportGenerator()
    data = {"address": "58 Jeffcott Street, West Melbourne", "created_at": "2026-04-20",
            "cap_rate": 0.03, "noi": 15000, "gross_revenue": 45000, "avg_adr": 185,
            "avg_occupancy": 0.72, "break_even_occupancy": 0.85, "cash_on_cash_return": -0.05,
            "comps": [], "stress_tests": [], "renovations": [], "exit_strategies": [],
            "mc_revenue_p10": 30000, "mc_revenue_p50": 45000, "mc_revenue_p90": 60000,
            "probability_of_loss": 0.25, "regulation_risk_score": 25,
            "str_allowed": True, "neighborhood_score": 65, "walk_score": 85,
            "nearest_airport_km": 22, "nearest_downtown_km": 2.1, "best_for": ["couples"],
            "supply_growth_pct_12mo": 4.2, "new_listings_last_12mo": 85}
    md = gen.generate_markdown("test-id-123", data)
    assert "58 Jeffcott Street" in md


def test_markdown_contains_key_sections():
    gen = ReportGenerator()
    data = {"address": "Test Address", "created_at": "2026-04-20",
            "cap_rate": 0.04, "noi": 20000, "gross_revenue": 55000, "avg_adr": 200,
            "avg_occupancy": 0.70, "break_even_occupancy": 0.80, "cash_on_cash_return": -0.02,
            "comps": [], "stress_tests": [], "renovations": [], "exit_strategies": [],
            "mc_revenue_p10": 35000, "mc_revenue_p50": 50000, "mc_revenue_p90": 65000,
            "probability_of_loss": 0.20, "regulation_risk_score": 25,
            "str_allowed": True, "neighborhood_score": 60, "walk_score": "N/A",
            "nearest_airport_km": "N/A", "nearest_downtown_km": "N/A", "best_for": [],
            "supply_growth_pct_12mo": 4.0, "new_listings_last_12mo": 80}
    md = gen.generate_markdown("test-id", data)
    for section in ["Executive Summary", "Comparable Analysis", "Regulatory Risk",
                    "Financial Projections", "Monte Carlo", "Stress Test", "Exit Strategies"]:
        assert section in md, f"Section '{section}' missing from report"


def test_markdown_is_string():
    gen = ReportGenerator()
    data = {"address": "Test", "created_at": "2026-04-20", "cap_rate": 0.03,
            "noi": 10000, "gross_revenue": 40000, "avg_adr": 180, "avg_occupancy": 0.65,
            "break_even_occupancy": 0.90, "cash_on_cash_return": -0.10,
            "comps": [], "stress_tests": [], "renovations": [], "exit_strategies": [],
            "mc_revenue_p10": 0, "mc_revenue_p50": 0, "mc_revenue_p90": 0,
            "probability_of_loss": 0.4, "regulation_risk_score": 30, "str_allowed": True,
            "neighborhood_score": 50, "walk_score": "N/A", "nearest_airport_km": "N/A",
            "nearest_downtown_km": "N/A", "best_for": [], "supply_growth_pct_12mo": 5,
            "new_listings_last_12mo": 100}
    result = gen.generate_markdown("abc", data)
    assert isinstance(result, str)
    assert len(result) > 500


def test_score_component_object():
    gen = ReportGenerator()
    data = {"cap_rate": 0.045, "regulation_risk_score": 25, "avg_occupancy": 0.73,
            "supply_growth_pct_12mo": 4.0, "neighborhood_score": 68, "probability_of_loss": 0.18}
    score, rec = gen.generate_overall_score(data)
    assert isinstance(score, float)
    assert rec in ("strong_buy", "buy", "hold", "avoid", "strong_avoid")
