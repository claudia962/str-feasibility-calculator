"""Tests for the full financial engine."""
import pytest
from app.services.financial_engine import FinancialEngine, ProFormaInputs, MONTHS, _monthly_mortgage
from app.services.airdna_client import MELBOURNE_SEASONAL


def _make_inputs(purchase_price=750000, avg_adr=220, avg_occ=0.72, down_pct=20, rate=6.5):
    monthly_adr = {m: avg_adr * (1 + (MELBOURNE_SEASONAL[m] - 1) * 0.25) for m in MONTHS}
    monthly_occ = {m: min(0.97, avg_occ * MELBOURNE_SEASONAL[m]) for m in MONTHS}
    return ProFormaInputs(
        purchase_price=purchase_price,
        down_payment_pct=down_pct,
        mortgage_rate_pct=rate,
        mortgage_term_years=30,
        avg_adr=avg_adr,
        avg_occupancy=avg_occ,
        monthly_adr=monthly_adr,
        monthly_occupancy=monthly_occ,
        is_self_managed=True,
    )


def test_noi_equals_revenue_minus_operating_expenses():
    inputs = _make_inputs()
    engine = FinancialEngine()
    result = engine.calculate_full_proforma(inputs)
    expected_noi = result.gross_revenue - result.expenses.total_operating
    assert abs(result.noi - expected_noi) < 0.01


def test_cap_rate_formula():
    inputs = _make_inputs(purchase_price=800000)
    engine = FinancialEngine()
    result = engine.calculate_full_proforma(inputs)
    expected_cap = result.noi / 800000
    assert abs(result.cap_rate - expected_cap) < 0.0001


def test_cash_on_cash_formula():
    inputs = _make_inputs()
    engine = FinancialEngine()
    result = engine.calculate_full_proforma(inputs)
    cash_invested = 750000 * 0.20  # 20% down, no reno
    annual_mortgage = _monthly_mortgage(750000 * 0.80, 6.5 / 100, 30) * 12
    expected_coc = (result.noi - annual_mortgage) / cash_invested
    assert abs(result.cash_on_cash - expected_coc) < 0.001


def test_break_even_occupancy_range():
    inputs = _make_inputs()
    engine = FinancialEngine()
    result = engine.calculate_full_proforma(inputs)
    # break_even is clamped to [0, 1] — may be 1.0 if property needs >100% occ to break even
    assert 0.0 <= result.break_even_occupancy <= 1.0


def test_monthly_projections_sum_to_annual():
    inputs = _make_inputs()
    engine = FinancialEngine()
    result = engine.calculate_full_proforma(inputs)
    monthly_sum = sum(mp.revenue for mp in result.monthly_projections)
    assert abs(monthly_sum - result.gross_revenue) < 1.0


def test_all_12_months_present():
    inputs = _make_inputs()
    engine = FinancialEngine()
    result = engine.calculate_full_proforma(inputs)
    months = [mp.month for mp in result.monthly_projections]
    assert set(months) == set(MONTHS)


def test_mortgage_payment_formula():
    payment = _monthly_mortgage(600000, 0.065, 30)
    assert 3700 < payment < 3900


def test_three_scenarios_ordering():
    inputs = _make_inputs()
    engine = FinancialEngine()
    import numpy as np
    adrs = list(np.random.default_rng(42).normal(220, 30, 12))
    occs = list(np.clip(np.random.default_rng(42).normal(0.72, 0.08, 12), 0.4, 0.95))
    scenarios = engine.generate_three_scenarios(inputs, adrs, occs)
    assert scenarios["pessimistic"].gross_revenue < scenarios["base"].gross_revenue
    assert scenarios["base"].gross_revenue < scenarios["optimistic"].gross_revenue


def test_all_expense_categories_present():
    inputs = _make_inputs()
    engine = FinancialEngine()
    result = engine.calculate_full_proforma(inputs)
    exp = result.expenses
    assert exp.platform_fees > 0
    assert exp.cleaning > 0
    assert exp.insurance > 0
    assert exp.maintenance_reserve > 0
    assert exp.property_tax > 0
    assert exp.mortgage_annual > 0
    assert exp.total_operating > 0
