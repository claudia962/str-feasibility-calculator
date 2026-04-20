"""
Property intelligence: geocoding, Walk Score, proximity calculations, neighbourhood scoring.
Google Geocoding API first, Nominatim fallback.
"""
import asyncio
import math
from dataclasses import dataclass, field
from typing import Optional

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class GeocodedAddress:
    latitude: float
    longitude: float
    formatted_address: str
    confidence: float = 1.0
    source: str = "nominatim"


@dataclass
class NeighborhoodScoreData:
    walk_score: Optional[int] = None
    transit_score: Optional[int] = None
    bike_score: Optional[int] = None
    nearest_airport_km: Optional[float] = None
    nearest_airport_name: Optional[str] = None
    nearest_beach_km: Optional[float] = None
    nearest_downtown_km: Optional[float] = None
    restaurants_within_1km: Optional[int] = None
    grocery_within_1km: Optional[int] = None
    neighborhood_score: float = 50.0
    best_for: list[str] = field(default_factory=list)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


_AU_AIRPORTS = [
    {"name": "Melbourne Airport (MEL)", "lat": -37.6690, "lng": 144.8410},
    {"name": "Avalon Airport (AVV)", "lat": -38.0394, "lng": 144.4693},
    {"name": "Sydney Airport (SYD)", "lat": -33.9399, "lng": 151.1753},
    {"name": "Brisbane Airport (BNE)", "lat": -27.3842, "lng": 153.1175},
]

_AU_BEACHES = [
    {"name": "St Kilda Beach", "lat": -37.8678, "lng": 144.9769},
    {"name": "Brighton Beach", "lat": -37.9213, "lng": 144.9944},
    {"name": "Bondi Beach", "lat": -33.8908, "lng": 151.2743},
    {"name": "Surfers Paradise", "lat": -27.9978, "lng": 153.4302},
]

_AU_CBDS = [
    {"name": "Melbourne CBD", "lat": -37.8136, "lng": 144.9631},
    {"name": "Sydney CBD", "lat": -33.8688, "lng": 151.2093},
    {"name": "Brisbane CBD", "lat": -27.4698, "lng": 153.0251},
]


def _strip_unit_prefix(address: str) -> str:
    """
    Strip apartment/unit number prefixes that confuse geocoders.
    e.g. '1302/58 Jeffcott Street' -> '58 Jeffcott Street'
         'Unit 4, 12 Main Street' -> '12 Main Street'
         'Apt 2B/45 King St' -> '45 King St'
    """
    import re
    # Pattern: digits/digits at start (e.g. "1302/58" -> "58")
    address = re.sub(r'^\d+\s*/\s*', '', address.strip())
    # Pattern: "Unit X, " or "Apt X, " prefix
    address = re.sub(r'^(?:unit|apt|apartment|flat|level|suite|shop)\s+\S+[,\s]+', '', address, flags=re.IGNORECASE)
    return address.strip()


async def geocode_address(address: str) -> Optional[GeocodedAddress]:
    """
    Geocode address — Google first, Nominatim fallback.
    Strips unit/apartment prefixes before geocoding.
    """
    clean_address = _strip_unit_prefix(address)
    if clean_address != address:
        logger.info("geocode.stripped_unit", original=address, clean=clean_address)

    if settings.google_geocoding_api_key:
        result = await _geocode_google(clean_address)
        if result:
            return result
    return await _geocode_nominatim(clean_address)


async def _geocode_google(address: str) -> Optional[GeocodedAddress]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": address, "key": settings.google_geocoding_api_key},
            )
            data = r.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        res = data["results"][0]
        loc = res["geometry"]["location"]
        return GeocodedAddress(
            latitude=loc["lat"], longitude=loc["lng"],
            formatted_address=res.get("formatted_address", address),
            confidence=1.0, source="google",
        )
    except Exception as exc:
        logger.warning("geocode.google.error", error=str(exc))
        return None


async def _geocode_nominatim(address: str) -> Optional[GeocodedAddress]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{settings.nominatim_url}/search",
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": "STR-Feasibility/1.0"},
            )
            data = r.json()
        if not data:
            return None
        item = data[0]
        return GeocodedAddress(
            latitude=float(item["lat"]), longitude=float(item["lon"]),
            formatted_address=item.get("display_name", address),
            confidence=float(item.get("importance", 0.5)),
            source="nominatim",
        )
    except Exception as exc:
        logger.warning("geocode.nominatim.error", error=str(exc))
        return None


async def get_walk_scores(lat: float, lng: float, address: str) -> dict:
    """Walk Score API — graceful degradation if unavailable."""
    if not settings.walkscore_api_key:
        return {"walk_score": None, "transit_score": None, "bike_score": None}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.walkscore.com/score",
                params={
                    "format": "json", "address": address,
                    "lat": lat, "lon": lng,
                    "walk": 1, "transit": 1, "bike": 1,
                    "wsapikey": settings.walkscore_api_key,
                },
            )
            data = r.json()
        return {
            "walk_score": data.get("walkscore"),
            "transit_score": data.get("transit", {}).get("score"),
            "bike_score": data.get("bike", {}).get("score"),
        }
    except Exception as exc:
        logger.warning("walkscore.error", error=str(exc))
        return {"walk_score": None, "transit_score": None, "bike_score": None}


async def calculate_proximities(lat: float, lng: float) -> dict:
    """Calculate distances to nearest airport, beach, CBD, and amenity counts."""
    nearest_airport = min(_AU_AIRPORTS, key=lambda a: _haversine(lat, lng, a["lat"], a["lng"]))
    nearest_beach = min(_AU_BEACHES, key=lambda b: _haversine(lat, lng, b["lat"], b["lng"]))
    nearest_cbd = min(_AU_CBDS, key=lambda c: _haversine(lat, lng, c["lat"], c["lng"]))

    airports_km = _haversine(lat, lng, nearest_airport["lat"], nearest_airport["lng"])
    beach_km = _haversine(lat, lng, nearest_beach["lat"], nearest_beach["lng"])
    cbd_km = _haversine(lat, lng, nearest_cbd["lat"], nearest_cbd["lng"])

    restaurants, grocery = await _overpass_amenity_counts(lat, lng)

    return {
        "nearest_airport_km": round(airports_km, 2),
        "nearest_airport_name": nearest_airport["name"],
        "nearest_beach_km": round(beach_km, 2),
        "nearest_downtown_km": round(cbd_km, 2),
        "restaurants_within_1km": restaurants,
        "grocery_within_1km": grocery,
    }


async def _overpass_amenity_counts(lat: float, lng: float) -> tuple[Optional[int], Optional[int]]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r_rest = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": f'[out:json];(node["amenity"~"restaurant|cafe"](around:1000,{lat},{lng}););out count;'},
            )
            r_groc = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": f'[out:json];(node["shop"~"supermarket|convenience"](around:1000,{lat},{lng}););out count;'},
            )
        rest_count = int(r_rest.json().get("elements", [{}])[0].get("tags", {}).get("total", 0))
        groc_count = int(r_groc.json().get("elements", [{}])[0].get("tags", {}).get("total", 0))
        return rest_count, groc_count
    except Exception:
        return None, None


async def get_neighborhood_score(lat: float, lng: float, address: str) -> NeighborhoodScoreData:
    """Combine walk scores + proximities into composite neighbourhood score."""
    scores_task = get_walk_scores(lat, lng, address)
    proximity_task = calculate_proximities(lat, lng)
    walk_data, prox_data = await asyncio.gather(scores_task, proximity_task)

    score = 0.0
    best_for = []

    ws = walk_data.get("walk_score")
    if ws is not None:
        score += (ws / 100) * 30

    airport_km = prox_data.get("nearest_airport_km")
    if airport_km is not None:
        score += max(0, 1 - airport_km / 50) * 20
        if airport_km < 15:
            best_for.append("business")

    cbd_km = prox_data.get("nearest_downtown_km")
    if cbd_km is not None:
        score += max(0, 1 - cbd_km / 20) * 20
        if cbd_km < 3:
            best_for.append("couples")

    beach_km = prox_data.get("nearest_beach_km")
    if beach_km is not None and beach_km < 3:
        score += 10
        best_for.extend(["families", "couples"])

    rest = prox_data.get("restaurants_within_1km")
    if rest is not None:
        score += min(10, rest / 5)

    score = min(100.0, max(0.0, round(score, 1)))
    if not best_for:
        best_for = ["couples"]

    return NeighborhoodScoreData(
        walk_score=walk_data.get("walk_score"),
        transit_score=walk_data.get("transit_score"),
        bike_score=walk_data.get("bike_score"),
        nearest_airport_km=prox_data.get("nearest_airport_km"),
        nearest_airport_name=prox_data.get("nearest_airport_name"),
        nearest_beach_km=prox_data.get("nearest_beach_km"),
        nearest_downtown_km=prox_data.get("nearest_downtown_km"),
        restaurants_within_1km=prox_data.get("restaurants_within_1km"),
        grocery_within_1km=prox_data.get("grocery_within_1km"),
        neighborhood_score=score,
        best_for=list(set(best_for)),
    )
