"""
AirROI-first market data client with mock fallback.
Redis cache with 24h TTL — gracefully falls back to in-memory dict
if Redis is unreachable OR unconfigured.
"""
import json
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# In-memory fallback cache: key -> (data, expiry_ts)
_local_cache: dict[str, tuple[Any, float]] = {}

# Redis client — lazily initialised, None if unavailable
_redis_client: Any = None


def _get_redis() -> Optional[Any]:
    """Return a synchronous Redis client, or None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        r.ping()
        _redis_client = r
        return _redis_client
    except Exception:
        return None


def _cache_get(key: str) -> Optional[Any]:
    """Try Redis first, fall back to local cache."""
    r = _get_redis()
    if r:
        try:
            raw = r.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    entry = _local_cache.get(key)
    if entry and entry[1] > time.time():
        return entry[0]
    return None


def _cache_set(key: str, data: Any, ttl: int = 86400) -> None:
    """Try Redis first, fall back to local cache."""
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl, json.dumps(data))
            return
        except Exception:
            pass
    _local_cache[key] = (data, time.time() + ttl)


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]

# Melbourne seasonal multipliers: peak Dec/Jan/Mar, trough May-Aug
MELBOURNE_SEASONAL = {
    "jan": 1.22, "feb": 1.15, "mar": 1.10, "apr": 0.90,
    "may": 0.72, "jun": 0.68, "jul": 0.70, "aug": 0.75,
    "sep": 0.85, "oct": 0.93, "nov": 1.05, "dec": 1.18,
}


@dataclass
class MarketOverview:
    avg_adr: float
    avg_occupancy: float
    avg_annual_revenue: float
    active_listings: int
    p25_revenue: float
    p75_revenue: float
    p90_revenue: float
    peak_month: str
    low_month: str
    yoy_trend: float
    data_source: str = "mock"
    stale: bool = False


@dataclass
class CompData:
    listing_id: str
    name: str
    latitude: float
    longitude: float
    distance_km: float
    bedrooms: int
    property_type: str
    annual_revenue: float
    avg_adr: float
    occupancy_rate: float
    avg_review_score: float
    similarity_score: float
    monthly_revenue: dict[str, float]
    monthly_occupancy: dict[str, float]
    monthly_adr: dict[str, float]
    data_source: str = "mock"


@dataclass
class MonthlyData:
    occupancy: float
    adr: float
    revenue: float


def _melbourne_mock_market(lat: float, lng: float) -> MarketOverview:
    """
    Calibrated Melbourne market data based on AirDNA Rentalizer scrape results.
    West Melbourne 2BR: $185 ADR, 73% occupancy (from GUI agent Rentalizer data).
    ADR and occupancy adjusted by distance from CBD.
    """
    cbd_dist = math.sqrt((lat - (-37.8136)) ** 2 + (lng - 144.9631) ** 2) * 111
    # Calibrated baseline: West Melbourne (1-2km from CBD) = $185 ADR, 73% occ
    # Scale: closer to CBD = higher ADR, slightly lower occ (more competition)
    adr_base = max(140, 185 + (1.5 - cbd_dist) * 12)   # $185 at 1.5km, scales with distance
    occ_base = max(0.55, 0.73 - (cbd_dist - 1.5) * 0.008)  # 73% at 1.5km
    annual = adr_base * 365 * occ_base
    return MarketOverview(
        avg_adr=round(adr_base, 2),
        avg_occupancy=round(occ_base, 3),
        avg_annual_revenue=round(annual, 2),
        active_listings=random.randint(200, 800),
        p25_revenue=round(annual * 0.65, 2),
        p75_revenue=round(annual * 1.30, 2),
        p90_revenue=round(annual * 1.65, 2),
        peak_month="jan",
        low_month="jun",
        yoy_trend=round(random.uniform(0.02, 0.05), 3),
        data_source="mock_calibrated",
    )


def _mock_comps(lat: float, lng: float, bedrooms: int, property_type: str,
                market: MarketOverview, max_results: int) -> list[CompData]:
    rng = random.Random(int(abs(lat * 1000 + lng * 100)))
    comps = []
    for i in range(min(max_results, 12)):
        offset_lat = lat + rng.uniform(-0.025, 0.025)
        offset_lng = lng + rng.uniform(-0.025, 0.025)
        dist = math.sqrt((offset_lat - lat) ** 2 + (offset_lng - lng) ** 2) * 111
        br_offset = rng.choice([0, 0, 0, 1, -1])
        comp_br = max(1, bedrooms + br_offset)
        comp_adr = round(max(80, market.avg_adr * rng.gauss(1.0, 0.18)), 2)
        comp_occ = round(max(0.35, min(0.95, market.avg_occupancy * rng.gauss(1.0, 0.12))), 3)
        comp_rev = round(comp_adr * 365 * comp_occ, 2)
        monthly_rev, monthly_occ, monthly_adr = {}, {}, {}
        for m, factor in MELBOURNE_SEASONAL.items():
            mo = round(min(0.97, comp_occ * factor), 3)
            ma = round(comp_adr * (1 + (factor - 1) * 0.25), 2)
            monthly_occ[m] = mo
            monthly_adr[m] = ma
            monthly_rev[m] = round(ma * (365 / 12) * mo, 2)
        bed_sim = {0: 1.0, 1: 0.7, 2: 0.3}.get(abs(comp_br - bedrooms), 0.0)
        dist_sim = max(0, 1 - dist / settings.comp_search_radius_km)
        similarity = round(0.5 * bed_sim + 0.5 * dist_sim, 3)
        comps.append(CompData(
            listing_id=f"mock_{i:04d}",
            name=f"Melbourne Property {i + 1} — {comp_br}BR",
            latitude=round(offset_lat, 7), longitude=round(offset_lng, 7),
            distance_km=round(dist, 2), bedrooms=comp_br,
            property_type=rng.choice(["apartment", "house", "townhouse"]),
            annual_revenue=comp_rev, avg_adr=comp_adr, occupancy_rate=comp_occ,
            avg_review_score=round(rng.uniform(4.2, 5.0), 1),
            similarity_score=similarity,
            monthly_revenue=monthly_rev, monthly_occupancy=monthly_occ, monthly_adr=monthly_adr,
            data_source="mock",
        ))
    return sorted(comps, key=lambda c: c.similarity_score, reverse=True)


async def get_market_overview(lat: float, lng: float, radius_km: float = 5.0) -> MarketOverview:
    key = f"market:{lat:.3f}:{lng:.3f}:{radius_km}"
    cached = _cache_get(key)
    if cached:
        return MarketOverview(**cached)

    # Try Inside Airbnb first
    try:
        from app.services.inside_airbnb import get_market_stats
        real_stats = get_market_stats(lat, lng, radius_km)
        if real_stats:
            _cache_set(key, real_stats.__dict__, ttl=86400)
            logger.info("market_overview.inside_airbnb", lat=lat, lng=lng, listings=real_stats.active_listings)
            return real_stats
    except Exception as exc:
        logger.warning("market_overview.inside_airbnb_failed", error=str(exc))

    overview = _melbourne_mock_market(lat, lng)
    _cache_set(key, overview.__dict__, ttl=86400)
    logger.info("market_overview.mock", lat=lat, lng=lng, avg_adr=overview.avg_adr)
    return overview


async def search_comps(lat: float, lng: float, radius_km: float = 5.0,
                       bedrooms: int = 2, property_type: str = "apartment",
                       max_results: int = 20) -> list[CompData]:
    """
    Comp search fallback chain:
    1. Inside Airbnb CSV (if downloaded)
    2. Live Airbnb scrape
    3. Calibrated mock (guaranteed fallback)
    """
    # Option 1: Inside Airbnb CSV
    try:
        from app.services.inside_airbnb import search_comps_local
        real_comps = search_comps_local(lat, lng, radius_km, bedrooms, property_type, max_results)
        if real_comps and len(real_comps) >= 3:
            logger.info("search_comps.inside_airbnb", count=len(real_comps), bedrooms=bedrooms)
            return real_comps
    except Exception as exc:
        logger.warning("search_comps.inside_airbnb_failed", error=str(exc))

    # Option 2: Live Airbnb scrape
    try:
        from app.services.airbnb_scraper import scrape_airbnb_comps
        live_comps = await scrape_airbnb_comps(lat, lng, bedrooms=bedrooms, max_results=max_results)
        if live_comps and len(live_comps) >= 3:
            logger.info("search_comps.airbnb_live", count=len(live_comps), bedrooms=bedrooms)
            return live_comps
    except Exception as exc:
        logger.warning("search_comps.airbnb_live_failed", error=str(exc))

    # Option 3: Calibrated mock
    market = await get_market_overview(lat, lng, radius_km)
    comps = _mock_comps(lat, lng, bedrooms, property_type, market, max_results)
    logger.info("search_comps.mock_calibrated", count=len(comps), bedrooms=bedrooms)
    return comps


async def get_market_seasonality(lat: float, lng: float) -> dict[str, MonthlyData]:
    market = await get_market_overview(lat, lng)
    result = {}
    for month, factor in MELBOURNE_SEASONAL.items():
        occ = round(market.avg_occupancy * factor, 3)
        adr = round(market.avg_adr * (1 + (factor - 1) * 0.25), 2)
        result[month] = MonthlyData(occupancy=occ, adr=adr, revenue=round(adr * (365 / 12) * occ, 2))
    return result
