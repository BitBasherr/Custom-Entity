from __future__ import annotations

from typing import Optional, Dict, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


def _pick_city(addr: Dict[str, Any]) -> Optional[str]:
    for k in ("city", "town", "village", "hamlet", "municipality"):
        v = addr.get(k)
        if v:
            return v
    return addr.get("city_district") or addr.get("suburb")


def _pick_road(addr: Dict[str, Any]) -> Optional[str]:
    for k in (
        "road", "residential", "pedestrian", "footway", "path",
        "service", "track", "cycleway", "road_reference"
    ):
        v = addr.get(k)
        if v:
            return v
    return None


def _pick_neighbourhood(addr: Dict[str, Any]) -> Optional[str]:
    for key in ("neighbourhood", "suburb", "quarter", "borough", "city_district", "township"):
        v = addr.get(key)
        if v:
            return v
    return None


def _make_line1(addr: Dict[str, Any], display_name: str) -> str:
    house = addr.get("house_number")
    road = _pick_road(addr)
    if house and road:
        return f"{house} {road}"
    if road:
        return road
    return (display_name or "").split(",")[0].strip()


def _classify_place(addr: Dict[str, Any], display_line1: str) -> tuple[str, str]:
    # Looks like a street address:
    if addr.get("house_number") or _pick_road(addr):
        return "address", display_line1

    # Neighborhood-ish:
    for k in ("neighbourhood", "suburb", "quarter", "borough", "city_district"):
        v = addr.get(k)
        if v:
            return "neighbourhood", v

    # Township-ish:
    for k in ("township", "municipality"):
        v = addr.get(k)
        if v:
            return "township", v

    # Town/city-level:
    for k in ("city", "town", "village", "hamlet"):
        v = addr.get(k)
        if v:
            return "locality", v

    if addr.get("country"):
        return "country", addr["country"]

    # Fallback to the first display line:
    return "place", display_line1 or "place"


async def async_reverse_geocode(
    hass,
    lat: float,
    lon: float,
    contact: Optional[str] = None,
    lang: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Minimal Nominatim reverse geocode with structured output + classification.
    Returns a dict with:
      line1, city, state, postcode, county, country, township, neighbourhood,
      suburb, city_district, borough, quarter, town, village, hamlet, municipality,
      osm_category, osm_type_detail, place_type, place_label, display_name
    or None on failure.
    """
    if lat is None or lon is None:
        return None

    params = {"format": "jsonv2", "lat": f"{lat}", "lon": f"{lon}"}
    headers = {
        "Accept": "application/json",
        "User-Agent": f"HA-CustomEntity/1.0 ({contact})" if contact else "HA-CustomEntity/1.0",
    }
    if lang:
        headers["Accept-Language"] = lang

    session = async_get_clientsession(hass)
    try:
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None

    display = data.get("display_name", "")
    addr = data.get("address") or {}
    if not isinstance(addr, dict):
        addr = {}

    line1 = _make_line1(addr, display)
    place_type, place_label = _classify_place(addr, line1)

    result: Dict[str, Any] = {
        "line1": line1,
        "city": _pick_city(addr),
        "state": addr.get("state"),
        "postcode": addr.get("postcode"),
        "county": addr.get("county"),
        "country": addr.get("country"),
        "township": addr.get("township"),
        "neighbourhood": _pick_neighbourhood(addr),
        "suburb": addr.get("suburb"),
        "city_district": addr.get("city_district"),
        "borough": addr.get("borough"),
        "quarter": addr.get("quarter"),
        "town": addr.get("town"),
        "village": addr.get("village"),
        "hamlet": addr.get("hamlet"),
        "municipality": addr.get("municipality"),
        "osm_category": data.get("category"),
        "osm_type_detail": data.get("type"),
        "place_type": place_type,
        "place_label": place_label,
        "display_name": display,
    }
    # Strip empties
    return {k: v for k, v in result.items() if v}


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    from math import radians, sin, cos, sqrt, atan2
    R = 3958.7613  # Earth radius in miles
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c
