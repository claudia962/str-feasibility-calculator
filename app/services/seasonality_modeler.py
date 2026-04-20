"""
Seasonality modeler: derives 12-month revenue/occupancy/ADR projections
from comp set, with quality differential adjustment and P25/P75 confidence bands.
"""
import calendar
import statistics
from dataclasses import dataclass

from app.services.airdna_client import CompData, MELBOURNE_SEASONAL

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
DAYS = {m: calendar.monthrange(2024, i + 1)[1] for i, m in enumerate(MONTHS)}


@dataclass
class MonthlyProjection:
    month: str
    days: int
    median_adr: float
    median_occupancy: float
    p25_adr: float
    p75_adr: float
    p25_occupancy: float
    p75_occupancy: float
    median_revenue: float
    p25_revenue: float
    p75_revenue: float


@dataclass
class SeasonalityResult:
    monthly: list[MonthlyProjection]
    annual_median_revenue: float
    annual_p25_revenue: float
    annual_p75_revenue: float
    peak_month: str
    low_month: str
    quality_adjustment_factor: float

    def as_dict(self) -> dict:
        return {
            "monthly": [m.__dict__ for m in self.monthly],
            "annual_median_revenue": self.annual_median_revenue,
            "annual_p25_revenue": self.annual_p25_revenue,
            "annual_p75_revenue": self.annual_p75_revenue,
            "peak_month": self.peak_month,
            "low_month": self.low_month,
            "quality_adjustment_factor": self.quality_adjustment_factor,
        }


def model_seasonality(
    comp_set: list[CompData],
    target_adr: float,
    target_occupancy: float,
) -> SeasonalityResult:
    """
    Derive 12-month seasonal projections from comp set.

    Quality differential: if target ADR > comp median ADR, scale up revenue
    proportionally (better property commands premium across all months).
    """
    # Quality adjustment factor
    comp_adrs = [c.avg_adr for c in comp_set if c.avg_adr and c.avg_adr > 0]
    comp_median_adr = statistics.median(comp_adrs) if comp_adrs else target_adr
    quality_factor = target_adr / comp_median_adr if comp_median_adr > 0 else 1.0
    quality_factor = max(0.5, min(2.0, quality_factor))  # cap at reasonable range

    monthly_projections = []
    total_median = total_p25 = total_p75 = 0.0

    for month in MONTHS:
        days = DAYS[month]

        # Collect monthly data from comp set
        month_adrs = [c.monthly_adr.get(month, c.avg_adr) for c in comp_set if c.monthly_adr]
        month_occs = [c.monthly_occupancy.get(month, c.occupancy_rate) for c in comp_set if c.monthly_occupancy]

        # Fall back to seasonal curve if no comp data
        if not month_adrs:
            factor = MELBOURNE_SEASONAL.get(month, 1.0)
            month_adrs = [target_adr * (1 + (factor - 1) * 0.25)]
            month_occs = [min(0.97, target_occupancy * factor)]

        # Apply quality adjustment to ADR
        adjusted_adrs = [a * quality_factor for a in month_adrs]

        def pct(lst, p): return sorted(lst)[int(len(lst) * p / 100)] if len(lst) > 2 else lst[0]

        med_adr = statistics.median(adjusted_adrs)
        p25_adr = pct(adjusted_adrs, 25)
        p75_adr = pct(adjusted_adrs, 75)

        med_occ = min(0.97, statistics.median(month_occs))
        p25_occ = min(0.97, pct(month_occs, 25))
        p75_occ = min(0.97, pct(month_occs, 75))

        med_rev = round(med_adr * med_occ * days, 2)
        p25_rev = round(p25_adr * p25_occ * days, 2)
        p75_rev = round(p75_adr * p75_occ * days, 2)

        total_median += med_rev
        total_p25 += p25_rev
        total_p75 += p75_rev

        monthly_projections.append(MonthlyProjection(
            month=month, days=days,
            median_adr=round(med_adr, 2), median_occupancy=round(med_occ, 3),
            p25_adr=round(p25_adr, 2), p75_adr=round(p75_adr, 2),
            p25_occupancy=round(p25_occ, 3), p75_occupancy=round(p75_occ, 3),
            median_revenue=med_rev, p25_revenue=p25_rev, p75_revenue=p75_rev,
        ))

    peak = max(monthly_projections, key=lambda m: m.median_revenue).month
    low = min(monthly_projections, key=lambda m: m.median_revenue).month

    return SeasonalityResult(
        monthly=monthly_projections,
        annual_median_revenue=round(total_median, 2),
        annual_p25_revenue=round(total_p25, 2),
        annual_p75_revenue=round(total_p75, 2),
        peak_month=peak,
        low_month=low,
        quality_adjustment_factor=round(quality_factor, 3),
    )
