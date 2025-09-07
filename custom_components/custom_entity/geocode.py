from __future__ import annotations

from typing import Optional, Dict, Any
from homeassistant.helpers.aiohttp_client import async_get_clientsession

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


# -------------------- helpers to pick common address bits -------------------- #

def _pick_city(addr: Dict[str, Any]) -> Optional[str]:
    for k in ("city", "town", "village", "hamlet", "municipality"):
        v = addr.get(k)
        if v:
            return v
    return addr.get("city_district") or addr.get("suburb")


def _pick_road(addr: Dict[str, Any]) -> Optional[str]:
    for k in (
        "road", "residential", "pedestrian", "footway", "path",
        "service", "track", "cycleway", "road_reference",
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


def _is_house_numberish(s: Optional[str]) -> bool:
    """True if string looks like a bare house number like '686' or '12A'."""
    if not s:
        return False
    t = str(s).strip()
    if not t:
        return False
    if t.isdigit():
        return True
    import re
    return re.fullmatch(r"\d+\s*[-/]?\s*[A-Za-z]?", t) is not None


def _pick_place_name(data: Dict[str, Any], addr: Dict[str, Any], display_name: str) -> Optional[str]:
    """
    Robustly detect a POI/venue name.
    1) data["name"]
    2) address hints (building / house_name / house)
    3) first display_name token
    Skip values that are basically a house number.
    """
    name = data.get("name")
    if isinstance(name, str) and name.strip() and not _is_house_numberish(name):
        return name.strip()

    for k in ("building", "house_name", "house"):
        v = addr.get(k)
        if isinstance(v, str) and v.strip() and not _is_house_numberish(v):
            return v.strip()

    first = (display_name or "").split(",")[0].strip()
    if first and not _is_house_numberish(first):
        return first
    return None


# -------------------- primary line and classification ------------------------ #

def _make_line1(addr: Dict[str, Any], display_name: str) -> str:
    house = addr.get("house_number")
    road = _pick_road(addr)
    if house and road:
        return f"{house} {road}"
    if road:
        return road
    return (display_name or "").split(",")[0].strip()


def _classify_place(
    addr: Dict[str, Any],
    display_line1: str,
    top_category: Optional[str],
    top_type: Optional[str],
) -> tuple[str, str]:
    """
    place_type: address | poi | neighbourhood | township | locality | country | place
    place_label: readable label for the classification (NOT the smart label)
    """
    if addr.get("house_number") or _pick_road(addr):
        return "address", display_line1

    if top_category or top_type:
        label = (top_type or top_category or "place").replace("_", " ").title()
        return "poi", label

    for k in ("neighbourhood", "suburb", "quarter", "borough", "city_district"):
        v = addr.get(k)
        if v:
            return "neighbourhood", v

    for k in ("township", "municipality"):
        v = addr.get(k)
        if v:
            return "township", v

    for k in ("city", "town", "village", "hamlet"):
        v = addr.get(k)
        if v:
            return "locality", v

    if addr.get("country"):
        return "country", addr["country"]

    return "place", display_line1 or "place"


# -------------------- category labels (“smart_place_label”) ------------------ #

_SMART_POI_LABEL = {
    # Transport / Parking
    "parking": "Parking Lot",
    "parking_entrance": "Parking Entrance",
    "parking_space": "Parking Space",
    "car_sharing": "Car Sharing",
    "bicycle_parking": "Bicycle Parking",
    "bus_station": "Bus Station",
    "bus_stop": "Bus Stop",
    "tram_stop": "Tram Stop",
    "train_station": "Train Station",
    "subway_entrance": "Subway Entrance",
    "ferry_terminal": "Ferry Terminal",
    "aerodrome": "Airport",
    "helipad": "Helipad",
    # Education
    "school": "School",
    "kindergarten": "Kindergarten",
    "university": "University",
    "college": "College",
    "language_school": "Language School",
    "music_school": "Music School",
    # Health
    "hospital": "Hospital",
    "clinic": "Clinic",
    "doctors": "Clinic",
    "dentist": "Dentist",
    "pharmacy": "Pharmacy",
    "veterinary": "Veterinary",
    # Fuel / EV
    "fuel": "Fuel Station",
    "charging_station": "Charging Station",
    # Food / Drink
    "restaurant": "Restaurant",
    "fast_food": "Fast Food",
    "cafe": "Cafe",
    "bar": "Bar",
    "pub": "Pub",
    "ice_cream": "Ice Cream",
    # Shopping / Retail
    "supermarket": "Supermarket",
    "convenience": "Convenience Store",
    "mall": "Mall",
    "retail": "Retail",
    "department_store": "Department Store",
    "marketplace": "Marketplace",
    "bakery": "Bakery",
    "butcher": "Butcher",
    "greengrocer": "Greengrocer",
    "florist": "Florist",
    "beverages": "Beverages",
    "electronics": "Electronics Store",
    "mobile_phone": "Mobile Phone Store",
    "clothes": "Clothing Store",
    "shoes": "Shoe Store",
    "doityourself": "Hardware/DIY",
    "car": "Car Dealership",
    "car_parts": "Auto Parts",
    # Finance / Services
    "bank": "Bank",
    "atm": "ATM",
    "money_transfer": "Money Transfer",
    "post_office": "Post Office",
    "post_box": "Post Box",
    "courier": "Courier",
    "shipping": "Shipping",
    # Auto Services
    "car_wash": "Car Wash",
    "car_rental": "Car Rental",
    "car_repair": "Auto Repair",
    "tyres": "Tire Shop",
    # Public / Civic
    "library": "Library",
    "police": "Police",
    "fire_station": "Fire Station",
    "townhall": "Town Hall",
    "courthouse": "Courthouse",
    "embassy": "Embassy",
    "community_centre": "Community Centre",
    # Recreation / Culture
    "park": "Park",
    "playground": "Playground",
    "pitch": "Sports Field",
    "stadium": "Stadium",
    "sports_centre": "Sports Centre",
    "swimming_pool": "Swimming Pool",
    "cinema": "Cinema",
    "theatre": "Theatre",
    "arts_centre": "Arts Centre",
    "museum": "Museum",
    # Lodging
    "hotel": "Hotel",
    "motel": "Motel",
    "guest_house": "Guest House",
    "hostel": "Hostel",
    "apartment": "Apartments",
    "camp_site": "Camp Site",
    # Worship / Memorials
    "place_of_worship": "Place of Worship",
    "cemetery": "Cemetery",
    "grave_yard": "Graveyard",
    "monument": "Monument",
    "memorial": "Memorial",
    # Industrial / Office / Warehouse
    "industrial": "Industrial Site",
    "factory": "Factory",
    "plant": "Plant",
    "warehouse": "Warehouse",
    "office": "Office",
    "construction": "Construction Site",
    "quarry": "Quarry",
}

_SMART_TYPE_LABEL = {
    "address": "Address",
    "neighbourhood": "Neighborhood",
    "township": "Township",
    "locality": "Locality",
    "country": "Country",
    "place": "Place",
}


def _smart_category_label(place_type: str, type_detail: Optional[str], category: Optional[str]) -> str:
    """Category word only (no names/addresses)."""
    if place_type == "poi":
        t = (type_detail or "").lower().strip()
        if t in _SMART_POI_LABEL:
            return _SMART_POI_LABEL[t]
        raw = (t or (category or "Place")).replace("_", " ").strip()
        return raw.title() if raw else "Place"
    return _SMART_TYPE_LABEL.get(place_type, "Place")


def _smart_display_label(
    place_type: str,
    type_detail: Optional[str],
    category: Optional[str],
    place_name: Optional[str],
    line1: str,
    addr: Dict[str, Any],
    place_label: str,
    include_city_in_parking: bool,
) -> str:
    """
    Build the final human-readable phrase for smart_place_label.
    - Parking: "Parking Lot at {name/line1[/city?]}"
      (city appended only if include_city_in_parking is True and needed)
    - Other POI: "{TypeLabel} — {PlaceName}" (if name), else "{TypeLabel}"
    - Address: "Address — {line1}"
    - Neighbourhood/Township/Locality/Country: "{BucketLabel} — {place_label}"
    """
    cat = _smart_category_label(place_type, type_detail, category)

    if place_type == "poi":
        t = (type_detail or "").lower().strip()
        if t in {"parking", "parking_entrance", "parking_space"}:
            best = place_name or line1 or (include_city_in_parking and _pick_city(addr)) or ""
            return f"{cat}{(' at ' + best) if best else ''}"
        if place_name:
            return f"{cat} — {place_name}"
        return cat

    if place_type == "address":
        return f"{cat} — {line1}"

    if place_type in {"neighbourhood", "township", "locality", "country"}:
        return f"{cat} — {place_label}" if place_label else cat

    return cat


# -------------------- public API -------------------------------------------- #

async def async_reverse_geocode(
    hass,
    lat: float,
    lon: float,
    contact: Optional[str] = None,
    lang: Optional[str] = None,
    *,
    include_city_in_parking: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Nominatim reverse geocode with structured output + classification.
    Returns a dict with:
      city, state, postcode, county, country,
      neighbourhood, suburb, city_district, borough, quarter,
      township, municipality, town, village, hamlet,
      osm_category, osm_type_detail, place_type, place_label,
      place_name, smart_place_label,
      line1, display_name
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

    display = data.get("display_name", "") or ""
    addr = data.get("address") or {}
    if not isinstance(addr, dict):
        addr = {}

    line1 = _make_line1(addr, display)
    category = (data.get("category") or "") or None
    type_detail = (data.get("type") or "") or None

    place_type, place_label = _classify_place(addr, line1, category, type_detail)
    place_name = _pick_place_name(data, addr, display)
    smart_label = _smart_display_label(
        place_type, type_detail, category, place_name, line1, addr, place_label, include_city_in_parking
    )

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
        "osm_category": category,
        "osm_type_detail": type_detail,
        "place_type": place_type,
        "place_label": place_label,
        "place_name": place_name,
        "smart_place_label": smart_label,
        "display_name": display,
    }
    return {k: v for k, v in result.items() if v}


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, sqrt, atan2
    R = 3958.7613
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c
