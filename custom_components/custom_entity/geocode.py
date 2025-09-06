from __future__ import annotations

from typing import Optional, Dict, Any
from homeassistant.helpers.aiohttp_client import async_get_clientsession

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


def _friendly_place_label(cls: str | None, typ: str | None, addr: dict) -> str:
    """Map Nominatim class/type to a human-friendly label."""
    cls = (cls or "").lower()
    typ = (typ or "").lower()

    # High-confidence mappings
    table = {
        ("amenity", "fuel"): "gas station",
        ("amenity", "parking"): "parking",
        ("amenity", "school"): "school",
        ("amenity", "college"): "college",
        ("amenity", "university"): "university",
        ("amenity", "hospital"): "hospital",
        ("amenity", "doctors"): "clinic",
        ("amenity", "dentist"): "dentist",
        ("amenity", "bank"): "bank",
        ("amenity", "atm"): "ATM",
        ("amenity", "pharmacy"): "pharmacy",
        ("amenity", "police"): "police station",
        ("amenity", "fire_station"): "fire station",
        ("amenity", "post_office"): "post office",
        ("amenity", "bar"): "bar",
        ("amenity", "pub"): "pub",
        ("amenity", "cafe"): "café",
        ("amenity", "restaurant"): "restaurant",
        ("amenity", "fast_food"): "fast food",
        ("amenity", "place_of_worship"): "place of worship",
        ("shop", "supermarket"): "supermarket",
        ("shop", "convenience"): "convenience store",
        ("shop", "mall"): "mall",
        ("shop", "car_repair"): "auto repair",
        ("shop", "car_parts"): "auto parts",
        ("leisure", "park"): "park",
        ("tourism", "hotel"): "hotel",
        ("tourism", "motel"): "motel",
        ("aeroway", "aerodrome"): "airport",
        ("aeroway", "terminal"): "airport terminal",
        ("highway", "service"): "road",
        ("building", "residential"): "residence",
        ("building", "house"): "residence",
    }
    if (cls, typ) in table:
        return table[(cls, typ)]

    # Fallbacks
    if cls == "shop":
        return "shop"
    if cls in ("amenity", "tourism", "leisure"):
        return typ.replace("_", " ") or cls
    if cls == "building":
        return "building"
    if cls == "highway":
        return "road"
    if "house_number" in addr and "road" in addr:
        return "address"
    return "place"


async def async_reverse_geocode(
    hass,
    lat: float,
    lon: float,
    contact: Optional[str] = None,
    lang: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Reverse geocode via Nominatim.
    Returns None or a dict with fields:
      display_name, line1, city, state, postcode, county, country,
      township, neighbourhood, poi_name, place_class, place_type, place_label
    """
    if lat is None or lon is None:
        return None

    params = {
        "format": "jsonv2",
        "lat": f"{lat}",
        "lon": f"{lon}",
        "zoom": "18",
        "addressdetails": "1",
        "namedetails": "1",
        "extratags": "1",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": f"HA-CustomEntity/1.0 ({contact})" if contact else "HA-CustomEntity/1.0",
    }
    if lang:
        headers["Accept-Language"] = lang

    session = async_get_clientsession(hass)
    try:
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=12) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

            addr = data.get("address") or {}
            name = data.get("name") or (data.get("namedetails") or {}).get("name")
            cls = data.get("class")
            typ = data.get("type")

            # First line like "680 North Shawnee Avenue"
            line1_parts = []
            if addr.get("house_number"):
                line1_parts.append(addr["house_number"])
            if addr.get("road"):
                if line1_parts:
                    line1_parts[-1] = f"{line1_parts[-1]} {addr['road']}"
                else:
                    line1_parts.append(addr["road"])
            line1 = " ".join(line1_parts).strip() or name or None

            place_label = _friendly_place_label(cls, typ, addr)

            return {
                "display_name": data.get("display_name"),
                "line1": line1,
                "city": addr.get("city") or addr.get("town") or addr.get("village"),
                "state": addr.get("state"),
                "postcode": addr.get("postcode"),
                "county": addr.get("county"),
                "country": addr.get("country"),
                "township": addr.get("township"),
                "neighbourhood": addr.get("neighbourhood"),
                "poi_name": name,
                "place_class": cls,
                "place_type": typ,
                "place_label": place_label,
            }
    except Exception:
        return None


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, sqrt, atan2
    R = 3958.7613
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c
