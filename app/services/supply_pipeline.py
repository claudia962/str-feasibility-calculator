"""
Supply pipeline service — tracks new STR listings entering market.
Uses Inside Airbnb CSV when available, falls back to AirDNA mock estimates.
"""
from dataclasses import dataclass


@dataclass
class SupplyPipelineResult:
    new_listings_last_6mo: int
    new_listings_last_12mo: int
    total_in_radius: int
    supply_growth_pct_12mo: float
    new_listings_trend: str
    estimated_adr_pressure_pct: float
    estimated_occupancy_pressure_pct: float
    source: str

    def as_dict(self) -> dict:
        return {k: (round(v, 3) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


def analyze_supply_pipeline(lat: float, lng: float, radius_km: float = 5.0) -> SupplyPipelineResult:
    """
    Analyze supply pipeline for a location.
    Uses Inside Airbnb CSV when available, mock estimates otherwise.
    """
    try:
        from app.services.inside_airbnb import get_supply_stats
        stats = get_supply_stats(lat, lng, radius_km)
        if stats["total_in_radius"] > 0:
            growth_pct = stats["supply_growth_pct_12mo"]
            trend = "increasing" if stats["new_listings_last_6mo"] > stats["new_listings_last_12mo"] / 2 else "stable"
            return SupplyPipelineResult(
                new_listings_last_6mo=stats["new_listings_last_6mo"],
                new_listings_last_12mo=stats["new_listings_last_12mo"],
                total_in_radius=stats["total_in_radius"],
                supply_growth_pct_12mo=growth_pct,
                new_listings_trend=trend,
                estimated_adr_pressure_pct=stats["estimated_adr_pressure_pct"],
                estimated_occupancy_pressure_pct=stats["estimated_occupancy_pressure_pct"],
                source="inside_airbnb",
            )
    except Exception:
        pass

    # Mock fallback for Melbourne
    return SupplyPipelineResult(
        new_listings_last_6mo=45,
        new_listings_last_12mo=85,
        total_in_radius=320,
        supply_growth_pct_12mo=4.2,
        new_listings_trend="stable",
        estimated_adr_pressure_pct=-1.26,
        estimated_occupancy_pressure_pct=-0.84,
        source="mock",
    )
