"""Tests for the Monte Carlo simulation engine."""
import pytest
from app.services.monte_carlo import MonteCarloEngine, MCResult
from app.services.financial_engine import ProFormaInputs, MONTHS
from app.services.airdna_client import CompData, MELBOURNE_SEASONAL


def _make_inputs():
    monthly_adr = {m: 220 * (1 + (MELBOURNE_SEASONAL[m] - 1) * 0.25) for m in MONTHS}
    monthly_occ = {m: min(0.97, 0.72 * MELBOURNE_SEASONAL[m]) for m in MONTHS}
    return ProFormaInputs(
        purchase_price=750000, down_payment_pct=20,
        mortgage_rate_pct=6.5, mortgage_term_years=30,
        avg_adr=220, avg_occupancy=0.72,
        monthly_adr=monthly_adr, monthly_occupancy=monthly_occ,
    )


def _make_comps(n=10):
    import random
    rng = random.Random(42)
    comps = []
    for i in range(n):
        monthly_rev = {m: 220 * 0.72 * 30 * MELBOURNE_SEASONAL[m] for m in MONTHS}
        monthly_occ = {m: 0.72 * MELBOURNE_SEASONAL[m] for m in MONTHS}
        monthly_adr_d = {m: 220.0 for m in MONTHS}
        comps.append(CompData(
            listing_id=f"test_{i}", name=f"Comp {i}",
            latitude=-37.82 + rng.uniform(-0.02, 0.02),
            longitude=144.96 + rng.uniform(-0.02, 0.02),
            distance_km=rng.uniform(0.5, 4.5),
            bedrooms=2, property_type="apartment",
            annual_revenue=rng.uniform(45000, 85000),
            avg_adr=rng.uniform(170, 280),
            occupancy_rate=rng.uniform(0.55, 0.85),
            avg_review_score=rng.uniform(4.2, 5.0),
            similarity_score=rng.uniform(0.6, 0.95),
            monthly_revenue=monthly_rev,
            monthly_occupancy=monthly_occ,
            monthly_adr=monthly_adr_d,
        ))
    return comps


def test_percentile_ordering():
    engine = MonteCarloEngine()
    result = engine.run_simulation(_make_comps(), _make_inputs(), n_sims=500, seed=42)
    assert result.revenue_p10 < result.revenue_p25
    assert result.revenue_p25 < result.revenue_p50
    assert result.revenue_p50 < result.revenue_p75
    assert result.revenue_p75 < result.revenue_p90


def test_noi_percentile_ordering():
    engine = MonteCarloEngine()
    result = engine.run_simulation(_make_comps(), _make_inputs(), n_sims=500, seed=42)
    assert result.noi_p10 < result.noi_p50
    assert result.noi_p50 < result.noi_p90


def test_2000_simulations_run():
    engine = MonteCarloEngine()
    result = engine.run_simulation(_make_comps(), _make_inputs(), n_sims=2000, seed=1)
    assert result.n_simulations == 2000


def test_probability_of_loss_range():
    engine = MonteCarloEngine()
    result = engine.run_simulation(_make_comps(), _make_inputs(), n_sims=500, seed=42)
    assert 0.0 <= result.probability_of_loss <= 1.0


def test_histogram_bins_and_counts():
    engine = MonteCarloEngine()
    result = engine.run_simulation(_make_comps(), _make_inputs(), n_sims=500, seed=42)
    assert len(result.histogram_bins) == 20
    assert len(result.histogram_counts) == 20
    assert sum(result.histogram_counts) == 500


def test_all_revenues_positive():
    engine = MonteCarloEngine()
    result = engine.run_simulation(_make_comps(), _make_inputs(), n_sims=500, seed=42)
    assert result.revenue_p10 > 0


def test_no_comps_falls_back_gracefully():
    engine = MonteCarloEngine()
    result = engine.run_simulation([], _make_inputs(), n_sims=200, seed=42)
    assert result.n_simulations == 200
    assert result.revenue_p50 > 0
