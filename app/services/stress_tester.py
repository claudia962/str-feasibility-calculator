"""
Stress test engine — all 7 pre-built scenarios with specific adaptation strategies.
"""
from dataclasses import dataclass
from app.services.financial_engine import FinancialEngine, ProFormaInputs, _monthly_mortgage


@dataclass
class StressResult:
    scenario_name: str
    scenario_type: str
    parameters: dict
    base_revenue: float
    impacted_revenue: float
    revenue_impact_pct: float
    base_noi: float
    impacted_noi: float
    noi_impact: float
    new_cash_on_cash: float
    still_profitable: bool
    adaptation_strategy: str
    adapted_revenue: float
    adapted_noi: float

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


class StressTester:
    """Run all 7 stress test scenarios against a base projection."""

    def __init__(self, inputs: ProFormaInputs, base_result) -> None:
        self.inputs = inputs
        self.base = base_result
        self.engine = FinancialEngine()
        self._annual_mortgage = base_result.expenses.mortgage_annual
        self._cash_invested = base_result.cash_invested

    def _coc(self, noi: float) -> float:
        return (noi - self._annual_mortgage) / self._cash_invested if self._cash_invested > 0 else 0

    def run_all(self) -> list[StressResult]:
        return [
            self.regulation_cap(90),
            self.demand_shock(0.25),
            self.competition(0.20),
            self.interest_rate(2.0),
            self.recession(),
            self.platform_fee_increase(0.10),
            self.event_cancellation(4200),
        ]

    def regulation_cap(self, max_nights: int = 90) -> StressResult:
        """STR night cap imposed."""
        projected_nights = self.inputs.avg_occupancy * 365
        capped_nights = min(max_nights, projected_nights)
        revenue_factor = capped_nights / projected_nights if projected_nights > 0 else 0
        impacted_rev = self.base.gross_revenue * revenue_factor
        impacted_noi = impacted_rev - (self.base.expenses.total_operating * revenue_factor)

        # Adaptation: convert remaining capacity to LTR
        ltr_monthly = 2800
        remaining_months = max(0, (365 - max_nights) / 30)
        ltr_revenue = ltr_monthly * remaining_months
        adapted_rev = impacted_rev + ltr_revenue
        adapted_noi = adapted_rev - (self.base.expenses.total_operating * 0.7)  # lower ops cost

        strategy = (
            f"Convert remaining {int(365 - max_nights)} non-STR days to 30-day+ stays at ~$2,800/month "
            f"(~${ltr_revenue:,.0f}/year). Total adapted revenue: ~${adapted_rev:,.0f}. "
            f"Reduce cleaning frequency to monthly saves ~$3,000/year."
        )
        return StressResult(
            scenario_name=f"Regulation Cap ({max_nights} nights/yr)",
            scenario_type="regulation_cap",
            parameters={"max_nights": max_nights},
            base_revenue=self.base.gross_revenue,
            impacted_revenue=round(impacted_rev, 2),
            revenue_impact_pct=round(revenue_factor - 1, 4),
            base_noi=self.base.noi,
            impacted_noi=round(impacted_noi, 2),
            noi_impact=round(impacted_noi - self.base.noi, 2),
            new_cash_on_cash=round(self._coc(impacted_noi), 4),
            still_profitable=adapted_noi > 0,
            adaptation_strategy=strategy,
            adapted_revenue=round(adapted_rev, 2),
            adapted_noi=round(adapted_noi, 2),
        )

    def demand_shock(self, drop_pct: float = 0.25) -> StressResult:
        """Occupancy drops by drop_pct."""
        new_occ = self.inputs.avg_occupancy * (1 - drop_pct)
        revenue_factor = 1 - drop_pct
        impacted_rev = self.base.gross_revenue * revenue_factor
        impacted_noi = impacted_rev - self.base.expenses.total_operating

        # Adaptation: reduce ADR 10% to recover occupancy
        adr_reduction = 0.10
        adapted_occ = min(0.97, new_occ / (1 - adr_reduction))
        adapted_rev = impacted_rev * (adapted_occ / new_occ) * (1 - adr_reduction)
        adapted_noi = adapted_rev - self.base.expenses.total_operating

        break_even_occ = (self.base.expenses.total_operating + self._annual_mortgage) / (self.base.gross_revenue / self.inputs.avg_occupancy) if self.inputs.avg_occupancy > 0 else 0
        strategy = (
            f"Reduce ADR by 10% to defend occupancy (from {self.inputs.avg_occupancy:.0%} to "
            f"target {adapted_occ:.0%}). Break-even occupancy at reduced ADR: {break_even_occ:.0%}. "
            f"Adapted revenue: ~${adapted_rev:,.0f}. If occupancy stays depressed >6 months, "
            f"consider mid-term rental ($2,400/month) to cover mortgage."
        )
        return StressResult(
            scenario_name=f"Demand Shock ({int(drop_pct*100)}% occupancy drop)",
            scenario_type="demand_shock",
            parameters={"demand_drop_pct": drop_pct},
            base_revenue=self.base.gross_revenue,
            impacted_revenue=round(impacted_rev, 2),
            revenue_impact_pct=round(revenue_factor - 1, 4),
            base_noi=self.base.noi,
            impacted_noi=round(impacted_noi, 2),
            noi_impact=round(impacted_noi - self.base.noi, 2),
            new_cash_on_cash=round(self._coc(impacted_noi), 4),
            still_profitable=adapted_noi > 0,
            adaptation_strategy=strategy,
            adapted_revenue=round(adapted_rev, 2),
            adapted_noi=round(adapted_noi, 2),
        )

    def competition(self, supply_increase_pct: float = 0.20) -> StressResult:
        """N% more listings enter market, applying ADR and occupancy pressure."""
        adr_factor = 1 - supply_increase_pct * 0.3
        occ_factor = 1 - supply_increase_pct * 0.2
        impacted_rev = self.base.gross_revenue * adr_factor * occ_factor
        impacted_noi = impacted_rev - self.base.expenses.total_operating
        # Adaptation: differentiation adds ~5% premium
        adapted_rev = impacted_rev * 1.05
        adapted_noi = adapted_rev - self.base.expenses.total_operating
        adr_pressure = supply_increase_pct * 0.3 * 100
        occ_pressure = supply_increase_pct * 0.2 * 100
        strategy = (
            f"{int(supply_increase_pct*100)}% supply increase drives ADR down ~{adr_pressure:.0f}% "
            f"and occupancy down ~{occ_pressure:.0f}%. Differentiation strategy: professional photography "
            f"upgrade ($800, +$15/night ADR), direct booking channel (saves 15.5% platform fee on 20% of bookings), "
            f"amenity addition. Recovers ~5% of lost revenue. Adapted NOI: ~${adapted_noi:,.0f}."
        )
        return StressResult(
            scenario_name=f"Competition (+{int(supply_increase_pct*100)}% supply)",
            scenario_type="competition",
            parameters={"supply_increase_pct": supply_increase_pct},
            base_revenue=self.base.gross_revenue,
            impacted_revenue=round(impacted_rev, 2),
            revenue_impact_pct=round(adr_factor * occ_factor - 1, 4),
            base_noi=self.base.noi,
            impacted_noi=round(impacted_noi, 2),
            noi_impact=round(impacted_noi - self.base.noi, 2),
            new_cash_on_cash=round(self._coc(impacted_noi), 4),
            still_profitable=adapted_noi > 0,
            adaptation_strategy=strategy,
            adapted_revenue=round(adapted_rev, 2),
            adapted_noi=round(adapted_noi, 2),
        )

    def interest_rate(self, increase_pct: float = 2.0) -> StressResult:
        """Mortgage rate rises by increase_pct percentage points."""
        new_rate = self.inputs.mortgage_rate_pct + increase_pct
        loan_amount = self.inputs.purchase_price * (1 - self.inputs.down_payment_pct / 100)
        new_monthly = _monthly_mortgage(loan_amount, new_rate / 100, self.inputs.mortgage_term_years)
        new_annual_mortgage = new_monthly * 12
        extra_annual = new_annual_mortgage - self._annual_mortgage
        impacted_noi = self.base.noi  # Revenue unchanged, but cash flow drops
        new_coc = (impacted_noi - new_annual_mortgage) / self._cash_invested if self._cash_invested > 0 else 0
        adapted_noi = impacted_noi * 1.02  # Optimise pricing +2%
        savings_if_fixed = extra_annual  # Already on higher rate
        strategy = (
            f"Rate rise of {increase_pct}% adds ~${extra_annual:,.0f}/year to mortgage cost "
            f"(new monthly: ${new_monthly:,.0f}). Revenue unchanged. "
            f"If variable rate: lock in fixed rate now. "
            f"Accelerate revenue optimisation (dynamic pricing) to offset extra cost."
        )
        return StressResult(
            scenario_name=f"Interest Rate Rise (+{increase_pct}%)",
            scenario_type="interest_rate",
            parameters={"rate_increase_pct": increase_pct},
            base_revenue=self.base.gross_revenue,
            impacted_revenue=self.base.gross_revenue,
            revenue_impact_pct=0.0,
            base_noi=self.base.noi,
            impacted_noi=round(impacted_noi, 2),
            noi_impact=0.0,
            new_cash_on_cash=round(new_coc, 4),
            still_profitable=adapted_noi > 0,
            adaptation_strategy=strategy,
            adapted_revenue=round(self.base.gross_revenue * 1.02, 2),
            adapted_noi=round(adapted_noi, 2),
        )

    def recession(self) -> StressResult:
        """Combined: occupancy × 0.75, ADR × 0.85."""
        impacted_rev = self.base.gross_revenue * 0.75 * 0.85
        impacted_noi = impacted_rev - self.base.expenses.total_operating
        # Adaptation: longer stays reduce cleaning cost ~30%
        adapted_cleaning_saving = self.base.expenses.cleaning * 0.30
        adapted_noi = impacted_noi + adapted_cleaning_saving
        new_be_occ = (self.base.expenses.total_operating - adapted_cleaning_saving + self._annual_mortgage) / (self.base.gross_revenue * 0.85 / self.inputs.avg_occupancy) if self.inputs.avg_occupancy > 0 else 0
        strategy = (
            f"Recession scenario: occupancy -25%, ADR -15%. "
            f"Shift to 7-night minimum stays reduces turnovers, saving ~${adapted_cleaning_saving:,.0f}/year in cleaning. "
            f"Break-even occupancy at recession ADR: {new_be_occ:.0%}. "
            f"If sustained >12 months, convert to medium-term rental at $2,200/month."
        )
        return StressResult(
            scenario_name="Recession (occ -25%, ADR -15%)",
            scenario_type="recession",
            parameters={"demand_drop_pct": 0.25, "adr_drop_pct": 0.15},
            base_revenue=self.base.gross_revenue,
            impacted_revenue=round(impacted_rev, 2),
            revenue_impact_pct=round(0.75 * 0.85 - 1, 4),
            base_noi=self.base.noi,
            impacted_noi=round(impacted_noi, 2),
            noi_impact=round(impacted_noi - self.base.noi, 2),
            new_cash_on_cash=round(self._coc(impacted_noi), 4),
            still_profitable=adapted_noi > 0,
            adaptation_strategy=strategy,
            adapted_revenue=round(impacted_rev, 2),
            adapted_noi=round(adapted_noi, 2),
        )

    def platform_fee_increase(self, increase_pct: float = 0.10) -> StressResult:
        """OTA commission rises by increase_pct (as fraction of current fees)."""
        extra_fees = self.base.expenses.platform_fees * increase_pct
        impacted_noi = self.base.noi - extra_fees
        # Adaptation: 20% direct bookings saves fees
        direct_booking_saving = self.base.expenses.platform_fees * 0.20 * 0.155
        adapted_noi = impacted_noi + direct_booking_saving
        strategy = (
            f"Platform fee increase of {int(increase_pct*100)}% adds ~${extra_fees:,.0f}/year. "
            f"Develop direct booking channel (website + repeat guest programme). "
            f"Target 20% direct bookings saves ~${direct_booking_saving:,.0f}/year in fees "
            f"(net impact: ~${(direct_booking_saving - extra_fees):+,.0f}/year)."
        )
        return StressResult(
            scenario_name=f"Platform Fee Increase (+{int(increase_pct*100)}%)",
            scenario_type="platform_fee_increase",
            parameters={"fee_increase_pct": increase_pct},
            base_revenue=self.base.gross_revenue,
            impacted_revenue=self.base.gross_revenue,
            revenue_impact_pct=0.0,
            base_noi=self.base.noi,
            impacted_noi=round(impacted_noi, 2),
            noi_impact=round(-extra_fees, 2),
            new_cash_on_cash=round(self._coc(impacted_noi), 4),
            still_profitable=adapted_noi > 0,
            adaptation_strategy=strategy,
            adapted_revenue=self.base.gross_revenue,
            adapted_noi=round(adapted_noi, 2),
        )

    def event_cancellation(self, revenue_lost: float = 4200) -> StressResult:
        """Key events cancelled, losing estimated revenue."""
        impacted_rev = max(0, self.base.gross_revenue - revenue_lost)
        impacted_noi = self.base.noi - revenue_lost
        adapted_noi = impacted_noi + revenue_lost * 0.6  # Corporate/extended stays fill gap
        strategy = (
            f"Event cancellation removes ~${revenue_lost:,.0f} in annual revenue. "
            f"Fill event-night gaps with corporate (7-night+) bookings at base ADR, "
            f"recovering ~60% of lost revenue (~${revenue_lost*0.6:,.0f}). "
            f"List on extended-stay platforms (Furnished Finder, Homelike) for high-occupancy periods."
        )
        return StressResult(
            scenario_name=f"Event Cancellation (${revenue_lost:,.0f} revenue lost)",
            scenario_type="event_cancellation",
            parameters={"revenue_lost": revenue_lost},
            base_revenue=self.base.gross_revenue,
            impacted_revenue=round(impacted_rev, 2),
            revenue_impact_pct=round(-revenue_lost / self.base.gross_revenue, 4) if self.base.gross_revenue > 0 else 0,
            base_noi=self.base.noi,
            impacted_noi=round(impacted_noi, 2),
            noi_impact=round(-revenue_lost, 2),
            new_cash_on_cash=round(self._coc(impacted_noi), 4),
            still_profitable=adapted_noi > 0,
            adaptation_strategy=strategy,
            adapted_revenue=round(impacted_rev + revenue_lost * 0.6, 2),
            adapted_noi=round(adapted_noi, 2),
        )
