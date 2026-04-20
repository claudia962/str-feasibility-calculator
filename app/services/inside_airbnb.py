"""
Inside Airbnb local CSV data service — Melbourne Sep 2025 data.

CSV columns used: id, name, latitude, longitude, room_type, property_type,
bedrooms, accommodates, price, amenities, review_scores_rating, reviews_per_month,
estimated_occupancy_l365d, estimated_revenue_l365d, host_since, last_scraped,
availability_365, neighbourhood_cleansed
"""
import csv
import json
import math
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from app.services.airdna_client import CompData, MarketOverview, MELBOURNE_SEASONAL

logger = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CSV_PLAIN = DATA_DIR / "melbourne_listings.csv"

_listings: Optional[list[dict]] = None
_loaded: bool = False


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _load_listings() -> list[dict]:
    global _listings, _loaded
    if _loaded:
        return _listings or []
    _loaded = True
    if not CSV_PLAIN.exists():
        logger.warning("inside_airbnb.csv_not_found", path=str(CSV_PLAIN),
                       hint="Download from http://data.insideairbnb.com/australia/vic/melbourne/2024-12-26/data/listings.csv.gz")
        _listings = []
        return []
    try:
        rows = []
        with open(CSV_PLAIN, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        _listings = rows
        logger.info("inside_airbnb.loaded", count=len(rows))
        return rows
    except Exception as exc:
        logger.error("inside_airbnb.load_failed", error=str(exc))
        _listings = []
        return []


def _parse_price(s: str) -> Optional[float]:
    try:
        return float(re.sub(r'[^\d.]', '', s))
    except (ValueError, TypeError):
        return None


def _parse_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def _parse_int(s: str, default: int = 0) -> int:
    try:
        return int(float(s)) if s else default
    except (ValueError, TypeError):
        return default


def _bedroom_similarity(target: int, comp: int) -> float:
    diff = abs(target - comp)
    return {0: 1.0, 1: 0.7, 2: 0.3}.get(diff, 0.0)


def _type_similarity(target: str, comp: str) -> float:
    t, c = target.lower(), comp.lower()
    if "entire" in c:
        return 1.0
    if t in c or c in t:
        return 0.8
    return 0.3


def get_all_amenities(row: dict) -> list[str]:
    """Parse amenities JSON list from CSV row."""
    try:
        raw = row.get("amenities", "[]")
        items = json.loads(raw)
        return [str(a).lower() for a in items]
    except Exception:
        return []


def search_comps_local(
    lat: float, lng: float,
    radius_km: float = 5.0,
    bedrooms: int = 2,
    property_type: str = "apartment",
    max_results: int = 15,
) -> list[CompData]:
    """Search Inside Airbnb CSV for comparable listings."""
    listings = _load_listings()
    if not listings:
        return []

    results = []
    for row in listings:
        # Only entire home/apt
        if row.get("room_type", "") not in ("Entire home/apt", "Entire rental unit", "Entire home"):
            continue

        try:
            comp_lat = _parse_float(row.get("latitude", ""), 0)
            comp_lng = _parse_float(row.get("longitude", ""), 0)
            if comp_lat == 0 or comp_lng == 0:
                continue

            dist = _haversine_km(lat, lng, comp_lat, comp_lng)
            if dist > radius_km:
                continue

            comp_br = _parse_int(row.get("bedrooms", ""), 0)
            if comp_br == 0:
                # Fallback to accommodates / 2
                comp_br = max(1, _parse_int(row.get("accommodates", "2"), 2) // 2)

            bed_score = _bedroom_similarity(bedrooms, comp_br)
            if bed_score == 0.0:
                continue

            # Derive occupancy proxy from reviews_per_month
            # (Inside Airbnb summary CSV often lacks price; use market ADR + review proxy)
            reviews_pm = _parse_float(row.get("reviews_per_month", ""), 0)
            # Typical review rate ~30% of stays leave reviews; avg LOS ~3 nights
            # occ_proxy = reviews_pm * (1/0.30) * 3 / 30 = reviews_pm * 1/3
            occ_proxy = min(0.95, reviews_pm / 3.0) if reviews_pm > 0 else 0.65

            # Use estimated fields if available
            est_rev = _parse_float(row.get("estimated_revenue_l365d", ""), 0)
            est_occ = _parse_float(row.get("estimated_occupancy_l365d", ""), 0)
            price = _parse_price(row.get("price", ""))

            if est_rev > 0 and est_occ > 0:
                if est_occ > 1.5:
                    est_occ = est_occ / 365.0
                est_occ = min(0.97, max(0.1, est_occ))
                avg_adr = est_rev / (est_occ * 365) if est_occ > 0 else 180.0
            elif price and 30 < price < 2000:
                avg_adr = price
                est_occ = occ_proxy
                est_rev = avg_adr * 365 * est_occ
            else:
                # No price data — use market-based ADR estimate from CBD distance
                import math as _math
                cbd_dist = _math.sqrt((comp_lat - (-37.8136)) ** 2 + (comp_lng - 144.9631) ** 2) * 111
                avg_adr = max(120, 190 - cbd_dist * 8)  # calibrated to Rentalizer data
                est_occ = occ_proxy
                est_rev = avg_adr * 365 * est_occ

            review_score = _parse_float(row.get("review_scores_rating", ""), 4.5)
            if review_score > 5:
                review_score = review_score / 100 * 5  # normalise 0-100 to 0-5

            type_score = _type_similarity(property_type, row.get("room_type", ""))
            dist_score = max(0.0, 1.0 - dist / radius_km)
            quality_score = min(1.0, review_score / 5.0)

            similarity = (0.35 * bed_score + 0.25 * type_score +
                          0.20 * dist_score + 0.20 * quality_score)

            # Build monthly curves
            monthly_rev, monthly_occ, monthly_adr = {}, {}, {}
            for m, factor in MELBOURNE_SEASONAL.items():
                mo = round(min(0.97, est_occ * factor), 3)
                ma = round(avg_adr * (1 + (factor - 1) * 0.25), 2)
                monthly_occ[m] = mo
                monthly_adr[m] = ma
                monthly_rev[m] = round(ma * (365 / 12) * mo, 2)

            results.append(CompData(
                listing_id=str(row.get("id", "")),
                name=(row.get("name", "") or "")[:80],
                latitude=comp_lat,
                longitude=comp_lng,
                distance_km=round(dist, 2),
                bedrooms=comp_br,
                property_type=row.get("property_type", row.get("room_type", "")),
                annual_revenue=round(est_rev, 2),
                avg_adr=round(avg_adr, 2),
                occupancy_rate=round(est_occ, 3),
                avg_review_score=round(review_score, 1),
                similarity_score=round(similarity, 3),
                monthly_revenue=monthly_rev,
                monthly_occupancy=monthly_occ,
                monthly_adr=monthly_adr,
                data_source="inside_airbnb",
            ))
        except Exception:
            continue

    results.sort(key=lambda c: c.similarity_score, reverse=True)
    return results[:max_results]


def get_market_stats(lat: float, lng: float, radius_km: float = 5.0) -> Optional[MarketOverview]:
    """Derive market stats from Inside Airbnb CSV."""
    comps = search_comps_local(lat, lng, radius_km, bedrooms=2)
    if len(comps) < 3:
        return None

    adrs = [c.avg_adr for c in comps]
    occs = [c.occupancy_rate for c in comps]
    revenues = sorted([c.annual_revenue for c in comps])
    n = len(revenues)

    return MarketOverview(
        avg_adr=round(statistics.median(adrs), 2),
        avg_occupancy=round(statistics.median(occs), 3),
        avg_annual_revenue=round(statistics.median(revenues), 2),
        active_listings=len(comps),
        p25_revenue=round(revenues[int(n * 0.25)], 2),
        p75_revenue=round(revenues[min(n - 1, int(n * 0.75))], 2),
        p90_revenue=round(revenues[min(n - 1, int(n * 0.90))], 2),
        peak_month="jan",
        low_month="jun",
        yoy_trend=0.03,
        data_source="inside_airbnb",
    )


def get_supply_stats(lat: float, lng: float, radius_km: float = 5.0) -> dict:
    """Count new listings (host_since in last 6/12 months) for supply pipeline."""
    listings = _load_listings()
    if not listings:
        return {"new_listings_last_6mo": 0, "new_listings_last_12mo": 0, "total_in_radius": 0}

    now = datetime.now()
    total = new_6mo = new_12mo = 0

    for row in listings:
        if row.get("room_type", "") not in ("Entire home/apt", "Entire rental unit"):
            continue
        try:
            comp_lat = _parse_float(row.get("latitude", ""), 0)
            comp_lng = _parse_float(row.get("longitude", ""), 0)
            if comp_lat == 0:
                continue
            if _haversine_km(lat, lng, comp_lat, comp_lng) > radius_km:
                continue
            total += 1
            host_since_str = row.get("host_since", "")
            if host_since_str:
                host_since = datetime.strptime(host_since_str, "%Y-%m-%d")
                months_ago = (now - host_since).days / 30
                if months_ago <= 6:
                    new_6mo += 1
                if months_ago <= 12:
                    new_12mo += 1
        except Exception:
            continue

    supply_growth_pct = (new_12mo / max(total, 1)) * 100
    return {
        "new_listings_last_6mo": new_6mo,
        "new_listings_last_12mo": new_12mo,
        "total_in_radius": total,
        "supply_growth_pct_12mo": round(supply_growth_pct, 2),
        "estimated_adr_pressure_pct": round(-supply_growth_pct * 0.3, 2),
        "estimated_occupancy_pressure_pct": round(-supply_growth_pct * 0.2, 2),
    }
