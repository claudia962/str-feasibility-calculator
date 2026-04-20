"""Tests for exit strategy modeler."""
import pytest
from app.services.exit_strategy import model_exit_strategies


def test_all_three_paths_returned():
    result = model_exit_strategies(
        purchase_price=750000, annual_str_noi=35000,
        annual_mortgage=45000, cash_invested=150000,
    )
    types = {p.strategy_type for p in result.paths}
    assert "continue_str" in types
    assert "long_term_rental" in types
    assert "sell" in types


def test_recommended_strategy_is_valid():
    result = model_exit_strategies(
        purchase_price=750000, annual_str_noi=35000,
        annual_mortgage=45000, cash_invested=150000,
    )
    assert result.recommended_strategy in ["continue_str", "long_term_rental", "sell"]


def test_recommendation_reasoning_not_empty():
    result = model_exit_strategies(
        purchase_price=750000, annual_str_noi=35000,
        annual_mortgage=45000, cash_invested=150000,
    )
    assert len(result.recommendation_reasoning) > 20


def test_sell_path_estimated_value_reflects_appreciation():
    result = model_exit_strategies(
        purchase_price=750000, annual_str_noi=35000,
        annual_mortgage=45000, cash_invested=150000,
        appreciation_rate=0.03, hold_years=5,
    )
    sell = next(p for p in result.paths if p.strategy_type == "sell")
    expected_value = 750000 * (1.03 ** 5) * 0.975  # minus selling costs
    assert abs(sell.estimated_value - expected_value) < 5000


def test_str_outperforms_ltr_threshold():
    result = model_exit_strategies(
        purchase_price=750000, annual_str_noi=50000,
        annual_mortgage=40000, cash_invested=150000,
        avg_adr=250,
    )
    # STR NOI > LTR NOI should set a threshold
    if result.str_outperforms_ltr_above_occupancy is not None:
        assert 0.0 < result.str_outperforms_ltr_above_occupancy < 1.0


def test_paths_have_appreciation_rate():
    result = model_exit_strategies(
        purchase_price=750000, annual_str_noi=35000,
        annual_mortgage=45000, cash_invested=150000,
    )
    for path in result.paths:
        assert path.appreciation_estimate_annual_pct == pytest.approx(3.0, abs=0.1)


def test_minimum_hold_years_positive():
    result = model_exit_strategies(
        purchase_price=750000, annual_str_noi=35000,
        annual_mortgage=45000, cash_invested=150000,
    )
    assert result.recommended_minimum_hold_years >= 1
