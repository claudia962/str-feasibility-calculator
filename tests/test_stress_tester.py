"""Tests for all 7 stress test scenarios."""
import pytest
from app.services.stress_tester import StressTester
from app.services.financial_engine import FinancialEngine, ProFormaInputs, MONTHS
from app.services.airdna_client import MELBOURNE_SEASONAL


def _get_tester():
    monthly_adr = {m: 220 * (1 + (MELBOURNE_SEASONAL[m] - 1) * 0.25) for m in MONTHS}
    monthly_occ = {m: min(0.97, 0.72 * MELBOURNE_SEASONAL[m]) for m in MONTHS}
    inputs = ProFormaInputs(
        purchase_price=750000, down_payment_pct=20,
        mortgage_rate_pct=6.5, mortgage_term_years=30,
        avg_adr=220, avg_occupancy=0.72,
        monthly_adr=monthly_adr, monthly_occupancy=monthly_occ,
    )
    engine = FinancialEngine()
    base = engine.calculate_full_proforma(inputs)
    return StressTester(inputs, base), base


def test_all_7_scenarios_run():
    tester, _ = _get_tester()
    results = tester.run_all()
    assert len(results) == 7
    types = {r.scenario_type for r in results}
    assert "regulation_cap" in types
    assert "demand_shock" in types
    assert "competition" in types
    assert "interest_rate" in types
    assert "recession" in types
    assert "platform_fee_increase" in types
    assert "event_cancellation" in types


def test_all_scenarios_have_adaptation_strategy():
    tester, _ = _get_tester()
    for result in tester.run_all():
        assert result.adaptation_strategy, f"Empty strategy for: {result.scenario_type}"
        assert len(result.adaptation_strategy) > 20


def test_regulation_cap_reduces_revenue():
    tester, base = _get_tester()
    result = tester.regulation_cap(90)
    assert result.impacted_revenue < base.gross_revenue
    assert result.revenue_impact_pct < 0


def test_demand_shock_reduces_revenue():
    tester, base = _get_tester()
    result = tester.demand_shock(0.25)
    assert abs(result.revenue_impact_pct + 0.25) < 0.05


def test_interest_rate_reduces_coc_not_noi():
    tester, base = _get_tester()
    result = tester.interest_rate(2.0)
    assert result.impacted_revenue == pytest.approx(base.gross_revenue, rel=0.01)
    assert result.new_cash_on_cash < base.cash_on_cash


def test_recession_combined_impact():
    tester, base = _get_tester()
    result = tester.recession()
    expected_factor = 0.75 * 0.85
    assert abs(result.revenue_impact_pct - (expected_factor - 1)) < 0.01


def test_adapted_noi_gt_impacted_noi():
    tester, base = _get_tester()
    for scenario in [tester.regulation_cap(90), tester.demand_shock(0.25), tester.competition(0.20)]:
        assert scenario.adapted_noi >= scenario.impacted_noi


def test_still_profitable_matches_adapted_noi():
    tester, _ = _get_tester()
    for result in tester.run_all():
        assert result.still_profitable == (result.adapted_noi > 0)
