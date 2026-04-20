"""
Full financial engine: pro forma, key metrics, IRR, break-even, multi-scenario projections.
"""
import calendar
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]

DAYS_IN_MONTH = {m: calendar.monthrange(2024, i + 1)[1] for i, m in enumerate(MONTHS)}


@dataclass
class ProFormaInputs:
    purchase_price: float
    down_payment_pct: float           # e.g. 20.0 for 20%
    mortgage_rate_pct: float          # e.g. 6.5 for 6.5%
    mortgage_term_years: int          # e.g. 30
    avg_adr: float                    # from comp set
    avg_occupancy: float              # from comp set (0-1)
    monthly_adr: dict[str, float]     # 12-month ADR curve
    monthly_occupancy: dict[str, float]  # 12-month occ curve
    estimated_renovation: float = 0.0
    is_self_managed: bool = True
    # Expense overrides (None = use defaults)
    platform_fee_pct: Optional[float] = None
    cleaning_cost_per_turn: Optional[float] = None
    avg_los_nights: Optional[float] = None
    supplies_per_night: Optional[float] = None
    management_fee_pct: Optional[float] = None
    appreciation_rate_annual: float = 0.03


@dataclass
class ExpenseBreakdown:
    platform_fees: float
    cleaning: float
    supplies: float
    management: float
    utilities: float
    insurance: float
    maintenance_reserve: float
    property_tax: float
    mortgage_annual: float
    total_operating: float   # all except mortgage
    total_all: float         # including mortgage

    def as_dict(self) -> dict:
        return {k: round(v, 2) for k, v in self.__dict__.items()}


@dataclass
class MonthlyProjection:
    month: str
    adr: float
    occupancy: float
    days: int
    occupied_nights: float
    revenue: float
    expenses: float
    noi: float


@dataclass
class ProFormaResult:
    # Inputs echo
    purchase_price: float
    cash_invested: float

    # Revenue
    gross_revenue: float
    monthly_projections: list[MonthlyProjection]

    # Expenses
    expenses: ExpenseBreakdown

    # Key metrics
    noi: float
    cap_rate: float
    cash_on_cash: float
    irr_5yr: float
    break_even_occupancy: float
    payback_months: Optional[int]

    # 5-year projection
    year1_revenue: float
    year2_revenue: float
    year3_revenue: float
    year4_revenue: float
    year5_revenue: float

    projection_type: str = "base"


def _monthly_mortgage(principal: float, annual_rate: float, term_years: int) -> float:
    """Monthly P&I payment."""
    r = annual_rate / 12
    n = term_years * 12
    if r == 0 or n == 0:
        return principal / n if n > 0 else 0
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def _calculate_irr_5yr(
    cash_invested: float,
    annual_cash_flow: float,
    purchase_price: float,
    appreciation_rate: float,
    mortgage_balance_yr5: float,
) -> float:
    """Approximate 5-year IRR using Newton-Raphson on NPV = 0."""
    sale_price_yr5 = purchase_price * (1 + appreciation_rate) ** 5
    terminal_equity = sale_price_yr5 - mortgage_balance_yr5 - (sale_price_yr5 * 0.025)  # 2.5% selling costs
    cash_flows = [-cash_invested] + [annual_cash_flow] * 4 + [annual_cash_flow + terminal_equity]

    # Newton-Raphson
    rate = 0.10
    for _ in range(100):
        npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
        dnpv = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows))
        if abs(dnpv) < 1e-10:
            break
        rate -= npv / dnpv
        if rate < -0.99:
            rate = -0.99

    return round(rate, 4)


def _mortgage_balance_after_years(principal: float, annual_rate: float, term_years: int, years: int) -> float:
    """Remaining mortgage balance after N years of payments."""
    r = annual_rate / 12
    n = term_years * 12
    payments_made = years * 12
    if r == 0:
        return max(0, principal * (1 - payments_made / n))
    return principal * ((1 + r) ** n - (1 + r) ** payments_made) / ((1 + r) ** n - 1)


class FinancialEngine:
    """Full financial pro forma calculator."""

    def calculate_full_proforma(self, inputs: ProFormaInputs, projection_type: str = "base") -> ProFormaResult:
        """
        Calculate complete pro forma with all expense line items and key metrics.

        Args:
            inputs: ProFormaInputs with property and comp data
            projection_type: 'base', 'optimistic', or 'pessimistic'
        """
        # --- Defaults ---
        platform_fee_pct = inputs.platform_fee_pct or 0.155
        cleaning_cost = inputs.cleaning_cost_per_turn or 85.0
        avg_los = inputs.avg_los_nights or 2.5
        supplies_pnt = inputs.supplies_per_night or 8.0
        mgmt_pct = 0.0 if inputs.is_self_managed else (inputs.management_fee_pct or 0.20)

        # --- Mortgage ---
        loan_amount = inputs.purchase_price * (1 - inputs.down_payment_pct / 100)
        monthly_mortgage_payment = _monthly_mortgage(loan_amount, inputs.mortgage_rate_pct / 100, inputs.mortgage_term_years)
        annual_mortgage = monthly_mortgage_payment * 12
        cash_invested = inputs.purchase_price * (inputs.down_payment_pct / 100) + inputs.estimated_renovation

        # --- Monthly revenue ---
        monthly_projections = []
        total_gross = 0.0
        total_occupied_nights = 0.0

        for month in MONTHS:
            days = DAYS_IN_MONTH[month]
            adr = inputs.monthly_adr.get(month, inputs.avg_adr)
            occ = inputs.monthly_occupancy.get(month, inputs.avg_occupancy)
            occupied = days * occ
            revenue = adr * occupied
            total_gross += revenue
            total_occupied_nights += occupied
            monthly_projections.append(MonthlyProjection(
                month=month, adr=adr, occupancy=occ, days=days,
                occupied_nights=round(occupied, 1),
                revenue=round(revenue, 2),
                expenses=0.0, noi=0.0,  # filled below
            ))

        # --- Annual expenses ---
        estimated_turnovers = total_occupied_nights / avg_los
        platform_fees = total_gross * platform_fee_pct
        cleaning = estimated_turnovers * cleaning_cost
        supplies = total_occupied_nights * supplies_pnt
        management = total_gross * mgmt_pct
        utilities = (200 * 12) + (total_occupied_nights * 2)
        insurance = inputs.purchase_price * 0.005
        maintenance_reserve = inputs.purchase_price * 0.01
        property_tax = inputs.purchase_price * 0.0035

        total_operating = (platform_fees + cleaning + supplies + management +
                           utilities + insurance + maintenance_reserve + property_tax)
        total_all = total_operating + annual_mortgage

        expenses = ExpenseBreakdown(
            platform_fees=round(platform_fees, 2),
            cleaning=round(cleaning, 2),
            supplies=round(supplies, 2),
            management=round(management, 2),
            utilities=round(utilities, 2),
            insurance=round(insurance, 2),
            maintenance_reserve=round(maintenance_reserve, 2),
            property_tax=round(property_tax, 2),
            mortgage_annual=round(annual_mortgage, 2),
            total_operating=round(total_operating, 2),
            total_all=round(total_all, 2),
        )

        # --- Key metrics ---
        noi = total_gross - total_operating
        cap_rate = noi / inputs.purchase_price if inputs.purchase_price > 0 else 0
        annual_cash_flow = noi - annual_mortgage
        cash_on_cash = annual_cash_flow / cash_invested if cash_invested > 0 else 0

        # Break-even occupancy: solve for occ where revenue * occ_factor = total_fixed + variable_occ * occ_factor
        # Simplified: gross_at_100pct * break_even_occ = total_fixed_expenses + variable_per_occ_night * 365 * break_even_occ
        gross_at_full = inputs.avg_adr * 365
        variable_per_night = (platform_fee_pct * inputs.avg_adr) + supplies_pnt + (cleaning_cost / avg_los) + 2
        fixed_expenses = insurance + maintenance_reserve + property_tax + (200 * 12) + annual_mortgage
        if (gross_at_full - variable_per_night * 365) > 0:
            break_even_occ = fixed_expenses / (gross_at_full - variable_per_night * 365)
        else:
            break_even_occ = 1.0
        break_even_occ = min(1.0, max(0.0, break_even_occ))

        # Payback months
        payback_months = None
        if annual_cash_flow > 0:
            payback_months = int(cash_invested / (annual_cash_flow / 12))

        # IRR 5yr
        mortgage_balance_yr5 = _mortgage_balance_after_years(
            loan_amount, inputs.mortgage_rate_pct / 100, inputs.mortgage_term_years, 5
        )
        irr_5yr = _calculate_irr_5yr(
            cash_invested, annual_cash_flow, inputs.purchase_price,
            inputs.appreciation_rate_annual, mortgage_balance_yr5,
        )

        # 5-year revenue projection (with 3% growth)
        yr1 = total_gross
        yr2 = yr1 * (1 + inputs.appreciation_rate_annual)
        yr3 = yr2 * (1 + inputs.appreciation_rate_annual)
        yr4 = yr3 * (1 + inputs.appreciation_rate_annual)
        yr5 = yr4 * (1 + inputs.appreciation_rate_annual)

        return ProFormaResult(
            purchase_price=inputs.purchase_price,
            cash_invested=round(cash_invested, 2),
            gross_revenue=round(total_gross, 2),
            monthly_projections=monthly_projections,
            expenses=expenses,
            noi=round(noi, 2),
            cap_rate=round(cap_rate, 4),
            cash_on_cash=round(cash_on_cash, 4),
            irr_5yr=irr_5yr,
            break_even_occupancy=round(break_even_occ, 4),
            payback_months=payback_months,
            year1_revenue=round(yr1, 2),
            year2_revenue=round(yr2, 2),
            year3_revenue=round(yr3, 2),
            year4_revenue=round(yr4, 2),
            year5_revenue=round(yr5, 2),
            projection_type=projection_type,
        )

    def generate_three_scenarios(
        self,
        inputs: ProFormaInputs,
        comp_adrs: list[float],
        comp_occs: list[float],
    ) -> dict[str, ProFormaResult]:
        """Generate base (median), optimistic (P75), pessimistic (P25) scenarios."""
        p25_adr = float(np.percentile(comp_adrs, 25)) if comp_adrs else inputs.avg_adr * 0.85
        p50_adr = float(np.percentile(comp_adrs, 50)) if comp_adrs else inputs.avg_adr
        p75_adr = float(np.percentile(comp_adrs, 75)) if comp_adrs else inputs.avg_adr * 1.15

        p25_occ = float(np.percentile(comp_occs, 25)) if comp_occs else inputs.avg_occupancy * 0.85
        p50_occ = float(np.percentile(comp_occs, 50)) if comp_occs else inputs.avg_occupancy
        p75_occ = float(np.percentile(comp_occs, 75)) if comp_occs else inputs.avg_occupancy * 1.10

        results = {}
        for label, adr, occ in [("base", p50_adr, p50_occ),
                                  ("optimistic", p75_adr, p75_occ),
                                  ("pessimistic", p25_adr, p25_occ)]:
            scenario_inputs = ProFormaInputs(
                purchase_price=inputs.purchase_price,
                down_payment_pct=inputs.down_payment_pct,
                mortgage_rate_pct=inputs.mortgage_rate_pct,
                mortgage_term_years=inputs.mortgage_term_years,
                avg_adr=adr,
                avg_occupancy=occ,
                monthly_adr={m: inputs.monthly_adr.get(m, inputs.avg_adr) * (adr / inputs.avg_adr)
                             for m in MONTHS},
                monthly_occupancy={m: min(0.97, inputs.monthly_occupancy.get(m, inputs.avg_occupancy) * (occ / inputs.avg_occupancy))
                                   for m in MONTHS},
                estimated_renovation=inputs.estimated_renovation,
                is_self_managed=inputs.is_self_managed,
                appreciation_rate_annual=inputs.appreciation_rate_annual,
            )
            results[label] = self.calculate_full_proforma(scenario_inputs, projection_type=label)

        return results
