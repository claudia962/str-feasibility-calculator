"""
Renovation ROI analyzer.

Uses comp set to find WITH/WITHOUT amenity pairs, estimates revenue uplift,
calculates payback period and ROI.
"""
from dataclasses import dataclass
from typing import Optional

from app.services.airdna_client import CompData

# Default renovation costs (AUD)
RENOVATION_COSTS = {
    "hot_tub": 8000,
    "pool": 40000,
    "kitchen_upgrade": 15000,
    "bathroom_upgrade": 8000,
    "extra_bedroom": 35000,
    "outdoor_area": 12000,
    "smart_home": 3500,
    "ev_charger": 2500,
}

# Keywords to detect amenity presence in listing name/amenities
AMENITY_KEYWORDS = {
    "hot_tub": ["hot tub", "spa", "jacuzzi", "hot-tub", "hottub"],
    "pool": ["pool", "swimming"],
    "kitchen_upgrade": ["modern kitchen", "gourmet kitchen", "renovated kitchen", "new kitchen"],
    "bathroom_upgrade": ["ensuite", "luxury bath", "renovated bathroom", "modern bath"],
    "extra_bedroom": [],  # uses bedrooms count
    "outdoor_area": ["balcony", "terrace", "deck", "courtyard", "garden", "rooftop"],
    "smart_home": ["smart home", "smart tv", "alexa", "google home", "keyless"],
    "ev_charger": ["ev charger", "electric vehicle", "tesla", "car charging"],
}


@dataclass
class RenovationResult:
    renovation_item: str
    estimated_cost: float
    with_amenity_count: int
    without_amenity_count: int
    adr_increase: float
    occupancy_increase_pct: float
    annual_revenue_increase: float
    payback_period_nights: int
    payback_period_months: int
    roi_1yr_pct: float
    recommendation: str
    reasoning: str
    confidence: str  # 'high', 'medium', 'low'

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


def _has_amenity(comp: CompData, item: str) -> bool:
    """Check if a comp listing has a given amenity."""
    if item == "extra_bedroom":
        return False  # handled separately via bedrooms count
    keywords = AMENITY_KEYWORDS.get(item, [])
    name_lower = (comp.name or "").lower()
    # Check name for keywords
    return any(kw in name_lower for kw in keywords)


def _recommendation(roi_1yr: float) -> str:
    if roi_1yr > 0.50:
        return "highly_recommended"
    elif roi_1yr > 0.25:
        return "recommended"
    elif roi_1yr > 0.10:
        return "marginal"
    return "not_recommended"


def analyze_renovation_roi(
    comp_set: list[CompData],
    avg_adr: float,
    avg_occupancy: float,
    items: Optional[list[str]] = None,
) -> list[RenovationResult]:
    """
    Analyze ROI for each renovation item using comp set WITH/WITHOUT pairs.
    Falls back to market-level estimates if insufficient comp pairs.
    """
    if items is None:
        items = list(RENOVATION_COSTS.keys())

    results = []
    for item in items:
        cost = RENOVATION_COSTS.get(item, 10000)
        keywords = AMENITY_KEYWORDS.get(item, [])

        if keywords and comp_set:
            with_comps = [c for c in comp_set if _has_amenity(c, item)]
            without_comps = [c for c in comp_set if not _has_amenity(c, item)]
        else:
            with_comps = []
            without_comps = comp_set

        confidence = "high" if len(with_comps) >= 3 and len(without_comps) >= 3 else "low"

        if len(with_comps) >= 2 and len(without_comps) >= 2:
            # Real comp pair analysis
            import statistics
            with_adr = statistics.median([c.avg_adr for c in with_comps])
            without_adr = statistics.median([c.avg_adr for c in without_comps])
            with_occ = statistics.median([c.occupancy_rate for c in with_comps])
            without_occ = statistics.median([c.occupancy_rate for c in without_comps])
            adr_increase = max(0, with_adr - without_adr)
            occ_increase = max(0, with_occ - without_occ)
            confidence = "medium" if len(with_comps) >= 2 else "low"
        else:
            # Market-level estimates when no comp pairs available
            estimates = {
                "hot_tub": (35, 0.03),      # $35 ADR uplift, 3% occ uplift
                "pool": (55, 0.04),
                "kitchen_upgrade": (20, 0.02),
                "bathroom_upgrade": (15, 0.02),
                "extra_bedroom": (40, 0.05),
                "outdoor_area": (18, 0.03),
                "smart_home": (8, 0.01),
                "ev_charger": (5, 0.01),
            }
            adr_increase, occ_increase = estimates.get(item, (15, 0.02))

        # Calculate revenue impact
        occupied_nights = avg_occupancy * 365
        new_occupied_nights = min(365, (avg_occupancy + occ_increase) * 365)
        annual_revenue_increase = (
            adr_increase * occupied_nights +
            avg_adr * (new_occupied_nights - occupied_nights)
        )
        annual_revenue_increase = max(0, annual_revenue_increase)

        payback_nights = int(cost / adr_increase) if adr_increase > 0 else 9999
        payback_months = int(cost / (annual_revenue_increase / 12)) if annual_revenue_increase > 0 else 999
        roi_1yr = annual_revenue_increase / cost if cost > 0 else 0

        rec = _recommendation(roi_1yr)
        n_with = len(with_comps)
        n_without = len(without_comps)

        if n_with >= 2:
            reasoning = (
                f"{item.replace('_', ' ').title()} costs ~${cost:,.0f}. "
                f"Comps WITH amenity (n={n_with}): +${adr_increase:.0f} ADR. "
                f"At {avg_occupancy:.0%} occupancy, adds ~${annual_revenue_increase:,.0f}/year. "
                f"Payback: {payback_months} months. ROI: {roi_1yr*100:.0f}%."
            )
        else:
            reasoning = (
                f"{item.replace('_', ' ').title()} costs ~${cost:,.0f}. "
                f"Market estimate: +${adr_increase:.0f} ADR, +{occ_increase*100:.0f}% occupancy. "
                f"Adds ~${annual_revenue_increase:,.0f}/year. "
                f"Payback: {payback_months} months. ROI: {roi_1yr*100:.0f}%. "
                f"(Low confidence — insufficient comp pairs in dataset)"
            )

        results.append(RenovationResult(
            renovation_item=item,
            estimated_cost=float(cost),
            with_amenity_count=n_with,
            without_amenity_count=n_without,
            adr_increase=round(float(adr_increase), 2),
            occupancy_increase_pct=round(float(occ_increase * 100), 2),
            annual_revenue_increase=round(float(annual_revenue_increase), 2),
            payback_period_nights=min(9999, payback_nights),
            payback_period_months=min(999, payback_months),
            roi_1yr_pct=round(float(roi_1yr * 100), 2),
            recommendation=rec,
            reasoning=reasoning,
            confidence=confidence,
        ))

    return sorted(results, key=lambda r: r.roi_1yr_pct, reverse=True)
