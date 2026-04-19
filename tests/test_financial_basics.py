"""Test basic financial calculations."""
import pytest


def test_gross_revenue_formula():
    """gross_revenue = avg_adr * avg_occupancy * 365"""
    avg_adr = 215.0
    avg_occupancy = 0.72
    gross = avg_adr * avg_occupancy * 365
    assert gross == pytest.approx(56_501.0, rel=0.005)


def test_noi_approximation():
    """NOI ≈ gross_revenue * 0.55 (45% expense ratio)"""
    gross = 56_538.0
    noi = gross * 0.55
    assert noi == pytest.approx(31_095.9, abs=1.0)


def test_cap_rate():
    """cap_rate = NOI / purchase_price"""
    noi = 31_095.9
    purchase_price = 750_000.0
    cap_rate = noi / purchase_price
    assert cap_rate == pytest.approx(0.0415, abs=0.001)


def test_monthly_mortgage_payment():
    """Verify P&I formula for standard mortgage."""
    from app.api.routes.analyze import _monthly_mortgage
    payment = _monthly_mortgage(principal=600_000, annual_rate=0.065, term_years=30)
    assert payment == pytest.approx(3792.0, abs=5.0)


def test_break_even_occupancy():
    """break_even = total_expenses / (avg_adr * 365)"""
    avg_adr = 215.0
    total_expenses = 45_000.0
    break_even = total_expenses / (avg_adr * 365)
    assert 0.0 < break_even < 1.0
    assert break_even == pytest.approx(0.573, abs=0.01)


def test_score_to_recommendation():
    """Score bands map to correct recommendations."""
    from app.api.routes.analyze import _score_to_rec
    assert _score_to_rec(80) == "strong_buy"
    assert _score_to_rec(65) == "buy"
    assert _score_to_rec(50) == "hold"
    assert _score_to_rec(35) == "avoid"
    assert _score_to_rec(20) == "strong_avoid"
