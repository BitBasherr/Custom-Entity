from __future__ import annotations

from typing import Optional, Dict, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

# Simple taxonomy: (category, type) -> human label
_PLACE_MAP = {
    ("amenity", "restaurant"): "restaurant",
    ("amenity", "fast_food"): "restaurant",
    ("amenity", "cafe"): "cafe",
    ("amenity", "bar"): "bar",
    ("amenity", "pub"): "bar",
    ("amenity", "bank"): "bank",
    ("amenity", "atm"): "bank",
    ("amenity", "fuel"): "gas station",
    ("shop", "supermarket"): "grocery",
    ("shop", "convenience"): "convenience store",
    ("shop", "mall"): "mall",
    ("amenity", "school"): "school",
    ("amenity", "college"): "school",
    ("amenity", "hospital"): "hospital",
    ("amenity", "pharmacy"): "pharmacy",
    ("amenity", "parking"): "parking",
    ("highway", "rest_area"): "rest area",
    ("tourism", "hotel"): "hotel",
    ("tourism", "motel"): "hotel",
    ("leisure", "park"): "park",
    ("building", "residential"): "residential",
    ("building", "house"): "residential",
    ("building", "apartments"): "residential",
}

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

def _make_line1(addr: Dict[str, Any], display_name: str) -> str:
    house = addr.get("house_number")
    road = _pick_road(addr)
    if house and road:
        return f"{house} {road}"
    if road:
        return road
    return (display_name or "").split(",")[0].strip()

def _classify_place(category: Optional[str], typ: Optional[str]) -> Optional[str]:
    if not category or not typ:
        return None
    return _PLACE_MAP.get((category, typ)) or category  # fallback to category

async def async_reverse_geocode(
    hass,
    lat: float,
    lon: float,
    contact: Optional[str] = None,
    lang: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Minimal Nominatim reverse geocode with light place classification.
    Returns:
      line1, city, state, postcode, county, country, township, neighbourhood, display_name,
      poi_name?, place_class?, place_type?, place_label?
    """
    if lat is None or lon is None:
        return None

    params = {"format": "jsonv2", "lat": f"{lat}", "lon": f"{lon}", "addressdetails": 1}
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

    category = data.get("category")
    typ = data.get("type")
    poi_name = data.get("name")  # named POI if present
    place_label = _classify_place(category, typ)

    result = {
        "line1": _make_line1(addr, display),
        "city": _pick_city(addr),
        "state": addr.get("state"),
        "postcode": addr.get("postcode"),
        "county": addr.get("county"),
        "country": addr.get("country"),
        "township": addr.get("township"),
        "neighbourhood": addr.get("neighbourhood") or addr.get("suburb"),
        "display_name": display,
    }

    # optional classification fields
    if poi_name:
        result["poi_name"] = poi_name
    if category:
        result["place_class"] = category
    if typ:
        result["place_type"] = typ
    if place_label:
        result["place_label"] = place_label

    # strip empties
    return {k: v for k, v in result.items() if v}

def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, sqrt, atan2
    R = 3958.7613
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c
