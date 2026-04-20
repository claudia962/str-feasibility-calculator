"""Tests for renovation ROI analysis."""
import pytest
from app.services.renovation_roi import analyze_renovation_roi, RENOVATION_COSTS, _recommendation
from app.services.airdna_client import CompData, MELBOURNE_SEASONAL


def _make_comps(n=8):
    import random
    rng = random.Random(42)
    comps = []
    monthly_adr = {m: 220.0 for m in MELBOURNE_SEASONAL}
    monthly_occ = {m: 0.72 for m in MELBOURNE_SEASONAL}
    monthly_rev = {m: 220 * 0.72 * 30 for m in MELBOURNE_SEASONAL}
    for i in range(n):
        comps.append(CompData(
            listing_id=f"t{i}", name=f"Property {i}",
            latitude=-37.82, longitude=144.96,
            distance_km=rng.uniform(0.5, 3),
            bedrooms=2, property_type="apartment",
            annual_revenue=rng.uniform(45000, 80000),
            avg_adr=rng.uniform(170, 280),
            occupancy_rate=rng.uniform(0.58, 0.85),
            avg_review_score=rng.uniform(4.2, 5.0),
            similarity_score=rng.uniform(0.6, 0.95),
            monthly_revenue=monthly_rev.copy(),
            monthly_occupancy=monthly_occ.copy(),
            monthly_adr=monthly_adr.copy(),
        ))
    return comps


def test_all_renovation_items_returned():
    results = analyze_renovation_roi([], avg_adr=220, avg_occupancy=0.72)
    items = {r.renovation_item for r in results}
    for expected in ["hot_tub", "pool", "kitchen_upgrade", "bathroom_upgrade",
                     "extra_bedroom", "outdoor_area", "smart_home", "ev_charger"]:
        assert expected in items


def test_payback_calculation():
    results = analyze_renovation_roi([], avg_adr=220, avg_occupancy=0.72, items=["hot_tub"])
    r = results[0]
    cost = RENOVATION_COSTS["hot_tub"]
    if r.annual_revenue_increase > 0:
        expected_months = int(cost / (r.annual_revenue_increase / 12))
        assert abs(r.payback_period_months - expected_months) <= 1


def test_recommendation_thresholds():
    assert _recommendation(0.55) == "highly_recommended"
    assert _recommendation(0.30) == "recommended"
    assert _recommendation(0.15) == "marginal"
    assert _recommendation(0.05) == "not_recommended"


def test_results_sorted_by_roi():
    results = analyze_renovation_roi([], avg_adr=220, avg_occupancy=0.72)
    rois = [r.roi_1yr_pct for r in results]
    assert rois == sorted(rois, reverse=True)


def test_annual_revenue_increase_non_negative():
    results = analyze_renovation_roi(_make_comps(), avg_adr=220, avg_occupancy=0.72)
    for r in results:
        assert r.annual_revenue_increase >= 0


def test_reasoning_contains_dollar_amounts():
    results = analyze_renovation_roi([], avg_adr=220, avg_occupancy=0.72)
    for r in results:
        assert "$" in r.reasoning, f"No $ in reasoning for {r.renovation_item}"
