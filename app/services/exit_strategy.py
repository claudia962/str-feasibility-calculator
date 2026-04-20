"""
Exit strategy modeler — three paths: continue STR, long-term rental, sell.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExitPath:
    strategy_type: str
    estimated_value: float
    estimated_monthly_income: float
    estimated_annual_return: float
    optimal_hold_period_years: int
    liquidity_score: float     # 0-100 (100 = most liquid)
    market_trend: str
    appreciation_estimate_annual_pct: float
    notes: str

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


@dataclass
class ExitStrategyResult:
    paths: list[ExitPath]
    recommended_strategy: str
    recommendation_reasoning: str
    str_outperforms_ltr_above_occupancy: Optional[float]
    recommended_minimum_hold_years: int

    def as_dict(self) -> dict:
        return {
            "paths": [p.as_dict() for p in self.paths],
            "recommended_strategy": self.recommended_strategy,
            "recommendation_reasoning": self.recommendation_reasoning,
            "str_outperforms_ltr_above_occupancy": self.str_outperforms_ltr_above_occupancy,
            "recommended_minimum_hold_years": self.recommended_minimum_hold_years,
        }


def model_exit_strategies(
    purchase_price: float,
    annual_str_noi: float,
    annual_mortgage: float,
    cash_invested: float,
    avg_adr: float = 200.0,
    appreciation_rate: float = 0.03,
    hold_years: int = 5,
    ltr_weekly_rent: Optional[float] = None,
) -> ExitStrategyResult:
    """
    Model all three exit paths and generate a comparison recommendation.
    """
    # --- Path 1: Continue STR ---
    str_annual_cashflow = annual_str_noi - annual_mortgage
    str_cumulative_5yr = str_annual_cashflow * hold_years
    sale_price_at_hold = purchase_price * (1 + appreciation_rate) ** hold_years
    str_total_return = str_cumulative_5yr + (sale_price_at_hold - purchase_price)
    str_annual_return = (str_total_return / cash_invested / hold_years) if cash_invested > 0 else 0

    str_path = ExitPath(
        strategy_type="continue_str",
        estimated_value=round(sale_price_at_hold, 2),
        estimated_monthly_income=round(str_annual_cashflow / 12, 2),
        estimated_annual_return=round(str_annual_return, 4),
        optimal_hold_period_years=hold_years,
        liquidity_score=60.0,
        market_trend="stable",
        appreciation_estimate_annual_pct=round(appreciation_rate * 100, 2),
        notes=(
            f"STR generates ${annual_str_noi:,.0f} NOI/year before mortgage. "
            f"After ${annual_mortgage:,.0f} mortgage: ${str_annual_cashflow:,.0f}/year cashflow. "
            f"Property appreciates to ~${sale_price_at_hold:,.0f} at {hold_years} years."
        ),
    )

    # --- Path 2: Long-term rental ---
    if ltr_weekly_rent is None:
        # Melbourne 2BR estimate: $700-900/week inner suburbs
        ltr_weekly_rent = max(600, min(1200, avg_adr * 0.15 * 52 / 52))
        # Simpler: $700/week as baseline for Melbourne 2BR
        ltr_weekly_rent = 700.0

    ltr_annual_gross = ltr_weekly_rent * 52
    ltr_expenses = ltr_annual_gross * 0.25  # management + maintenance + insurance
    ltr_noi = ltr_annual_gross - ltr_expenses
    ltr_cashflow = ltr_noi - annual_mortgage
    ltr_annual_return = ((ltr_cashflow * hold_years + (sale_price_at_hold - purchase_price)) / cash_invested / hold_years) if cash_invested > 0 else 0

    ltr_path = ExitPath(
        strategy_type="long_term_rental",
        estimated_value=round(sale_price_at_hold, 2),
        estimated_monthly_income=round(ltr_cashflow / 12, 2),
        estimated_annual_return=round(ltr_annual_return, 4),
        optimal_hold_period_years=hold_years,
        liquidity_score=55.0,
        market_trend="stable",
        appreciation_estimate_annual_pct=round(appreciation_rate * 100, 2),
        notes=(
            f"LTR at ${ltr_weekly_rent:,.0f}/week = ${ltr_annual_gross:,.0f}/year gross. "
            f"After expenses: ${ltr_noi:,.0f} NOI, ${ltr_cashflow:,.0f}/year cashflow. "
            f"Stable, low-management fallback. Covers {ltr_annual_gross/annual_mortgage*100:.0f}% of mortgage."
        ),
    )

    # --- Path 3: Sell ---
    selling_costs = sale_price_at_hold * 0.025
    equity_at_sale = sale_price_at_hold - selling_costs
    str_cumulative = str_annual_cashflow * hold_years
    total_sell_return = str_cumulative + (equity_at_sale - purchase_price)
    sell_annual_return = (total_sell_return / cash_invested / hold_years) if cash_invested > 0 else 0

    sell_path = ExitPath(
        strategy_type="sell",
        estimated_value=round(equity_at_sale, 2),
        estimated_monthly_income=0.0,
        estimated_annual_return=round(sell_annual_return, 4),
        optimal_hold_period_years=hold_years,
        liquidity_score=90.0,
        market_trend="appreciating",
        appreciation_estimate_annual_pct=round(appreciation_rate * 100, 2),
        notes=(
            f"Sell after {hold_years} years at estimated ${sale_price_at_hold:,.0f} "
            f"(less ${selling_costs:,.0f} selling costs). "
            f"Net equity: ${equity_at_sale:,.0f}. "
            f"Total return including STR cashflow: ${total_sell_return:,.0f}."
        ),
    )

    # --- Recommendation ---
    str_monthly = str_annual_cashflow / 12
    ltr_monthly = ltr_cashflow / 12
    str_outperforms_above = None

    if annual_str_noi > ltr_noi:
        diff = annual_str_noi - ltr_noi
        # Find occupancy where STR NOI equals LTR NOI
        # STR NOI = adr * occ * 365 * 0.55, LTR NOI = fixed
        # adr * occ * 365 * 0.55 = ltr_noi => occ = ltr_noi / (adr * 365 * 0.55)
        str_outperforms_above = round(ltr_noi / (avg_adr * 365 * 0.55), 3) if avg_adr > 0 else None

    if str_monthly > 0 and str_monthly > ltr_monthly:
        rec = "continue_str"
        reasoning = (
            f"STR outperforms LTR by ${(str_monthly - ltr_monthly)*12:,.0f}/year. "
            f"STR NOI ${annual_str_noi:,.0f} vs LTR NOI ${ltr_noi:,.0f}. "
        )
        if str_outperforms_above:
            reasoning += f"STR advantage holds above {str_outperforms_above:.0%} occupancy. "
        reasoning += f"Recommend minimum {hold_years}-year hold for appreciation benefit (IRR improves significantly)."
    elif ltr_monthly > 0:
        rec = "long_term_rental"
        reasoning = (
            f"LTR provides more reliable cashflow than current STR projections. "
            f"LTR at ${ltr_weekly_rent:,.0f}/week covers {ltr_annual_gross/annual_mortgage*100:.0f}% of mortgage. "
            f"Recommended as STR performance improves or regulations change."
        )
    else:
        rec = "sell"
        reasoning = (
            f"Both rental strategies are cash-flow negative at current projections. "
            f"Sell after {hold_years} years captures ${sale_price_at_hold - purchase_price:,.0f} appreciation. "
            f"Minimum hold {hold_years} years recommended to maximise capital gains."
        )

    return ExitStrategyResult(
        paths=[str_path, ltr_path, sell_path],
        recommended_strategy=rec,
        recommendation_reasoning=reasoning,
        str_outperforms_ltr_above_occupancy=str_outperforms_above,
        recommended_minimum_hold_years=hold_years,
    )
