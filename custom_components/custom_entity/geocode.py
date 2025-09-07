from __future__ import annotations

from typing import Optional, Dict, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


# -------------------- helpers to pick common address bits --------------------

def _pick_city(addr: Dict[str, Any]) -> Optional[str]:
    """Prefer city-like levels in a sensible order."""
    for k in ("city", "town", "village", "hamlet", "municipality"):
        v = addr.get(k)
        if v:
            return v
    # fallback city-ish
    return addr.get("city_district") or addr.get("suburb")


def _pick_road(addr: Dict[str, Any]) -> Optional[str]:
    """Choose a useful road/street value even if OSM used a different key."""
    for k in (
        "road", "residential", "pedestrian", "footway", "path",
        "service", "track", "cycleway", "road_reference",
    ):
        v = addr.get(k)
        if v:
            return v
    return None


def _pick_neighbourhood(addr: Dict[str, Any]) -> Optional[str]:
    """Neighborhood-ish buckets; includes township for ‘local grouping’ names."""
    for key in ("neighbourhood", "suburb", "quarter", "borough", "city_district", "township"):
        v = addr.get(key)
        if v:
            return v
    return None


# -------------------- primary line and classification ------------------------

_BUILDING_HOUSE_TYPES = {
    "house", "apartments", "residential", "detached", "semidetached_house",
    "terrace", "hut", "cabin", "bungalow"
}
_BUILDING_TYPES = _BUILDING_HOUSE_TYPES | {
    "yes", "building", "barn", "shed", "retail", "industrial", "commercial",
    "warehouse", "office", "church", "school"
}
_POI_CATEGORIES = {
    "amenity", "shop", "office", "craft", "leisure", "tourism",
    "aeroway", "railway", "highway", "man_made", "natural",
    "sport", "healthcare", "public_transport", "place"
}

def _titleize(s: str) -> str:
    return s.replace("_", " ").title()


def _make_line1(addr: Dict[str, Any], display_name: str) -> str:
    """Line 1: '123 Main St' if available; else first display segment."""
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
    Classify into a broad place_type and a simple place_label.
    place_type may be: house | building | poi | neighbourhood | township | locality | country | address | place
    place_label is a readable label for the classification ("House", "Warehouse", "Neighbourhood", etc.)
    """
    cat = (top_category or "").lower() or None
    typ = (top_type or "").lower() or None

    # Building/house nuance first (avoid bucketing as generic address)
    if typ in _BUILDING_HOUSE_TYPES:
        return "house", "House"
    if (cat == "building" and typ in _BUILDING_TYPES):
        return "building", _titleize(typ)

    # Looks like a street address (but not a classified building)
    if addr.get("house_number") or _pick_road(addr):
        # If Nominatim still called it 'house', prefer House classification
        if typ == "house":
            return "house", "House"
        return "address", "Address"

    # Clear POI-type categories from Nominatim (shops, amenities, offices, etc.)
    if cat in _POI_CATEGORIES or typ:
        # "poi" with a friendly label
        label = _titleize(typ or cat or "poi")
        return "poi", label

    # Neighborhood-ish:
    for k in ("neighbourhood", "suburb", "quarter", "borough", "city_district"):
        v = addr.get(k)
        if v:
            return "neighbourhood", "Neighbourhood"

    # Township-ish:
    for k in ("township", "municipality"):
        v = addr.get(k)
        if v:
            return "township", "Township"

    # Town/city-level:
    for k in ("city", "town", "village", "hamlet"):
        v = addr.get(k)
        if v:
            return "locality", "Locality"

    # Country:
    if addr.get("country"):
        return "country", "Country"

    # Fallback:
    return "place", "Place"


# -------------------- “smart” human label for POIs and common types ----------

_SMART_LABEL_MAP = {
    # --- Transport / Parking ---
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

    # --- Education ---
    "school": "School",
    "kindergarten": "Kindergarten",
    "university": "University",
    "college": "College",
    "language_school": "Language School",
    "music_school": "Music School",

    # --- Health ---
    "hospital": "Hospital",
    "clinic": "Clinic",
    "doctors": "Clinic",
    "dentist": "Dentist",
    "pharmacy": "Pharmacy",
    "veterinary": "Veterinary",

    # --- Fuel / EV ---
    "fuel": "Fuel Station",
    "charging_station": "Charging Station",

    # --- Food / Drink ---
    "restaurant": "Restaurant",
    "fast_food": "Fast Food",
    "cafe": "Cafe",
    "bar": "Bar",
    "pub": "Pub",
    "ice_cream": "Ice Cream",

    # --- Shopping / Retail ---
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

    # --- Finance / Services ---
    "bank": "Bank",
    "atm": "ATM",
    "money_transfer": "Money Transfer",
    "post_office": "Post Office",
    "post_box": "Post Box",
    "courier": "Courier",
    "shipping": "Shipping",

    # --- Auto Services ---
    "car_wash": "Car Wash",
    "car_rental": "Car Rental",
    "car_repair": "Auto Repair",
    "tyres": "Tire Shop",

    # --- Public / Civic ---
    "library": "Library",
    "police": "Police",
    "fire_station": "Fire Station",
    "townhall": "Town Hall",
    "courthouse": "Courthouse",
    "embassy": "Embassy",
    "community_centre": "Community Centre",

    # --- Recreation / Culture ---
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

    # --- Lodging ---
    "hotel": "Hotel",
    "motel": "Motel",
    "guest_house": "Guest House",
    "hostel": "Hostel",
    "apartment": "Apartments",
    "camp_site": "Camp Site",

    # --- Worship / Memorials ---
    "place_of_worship": "Place of Worship",
    "cemetery": "Cemetery",
    "grave_yard": "Graveyard",
    "monument": "Monument",
    "memorial": "Memorial",

    # --- Industrial / Office / Warehouse ---
    "industrial": "Industrial Site",
    "factory": "Factory",
    "plant": "Plant",
    "warehouse": "Warehouse",
    "office": "Office",
    "construction": "Construction Site",
    "quarry": "Quarry",
}


def _smart_place_label(
    name: Optional[str],
    place_type: str,
    type_detail: Optional[str],
    base_line1: str,
    addr: Dict[str, Any],
) -> str:
    """
    Create a friendly synthesized label.
    Examples:
      - "Parking Lot at Walmart"
      - "Bank — Chase"
      - "Warehouse — Allied Midwest Merchandisers"
      - "House — 686 North Shawnee Avenue"
      - falls back to POI name, then base line1, then city, then 'place'
    """
    t = (type_detail or "").lower().strip()
    candidate_name = (name or "").strip()

    # Ignore purely numeric or trivial "names" (house numbers etc.)
    if candidate_name and candidate_name.isdigit():
        candidate_name = ""
    if candidate_name and candidate_name == base_line1:
        candidate_name = ""

    # Building/house phrasing
    if place_type == "house":
        label = "House"
        if candidate_name:
            return f"{label} — {candidate_name}"
        return f"{label} — {base_line1}" if base_line1 else label

    if place_type == "building":
        label = _titleize(t or "Building")
        if candidate_name:
            return f"{label} — {candidate_name}"
        return f"{label} — {base_line1}" if base_line1 else label

    # POIs & others
    if t in {"parking", "parking_entrance", "parking_space"}:
        at = candidate_name or base_line1 or _pick_city(addr) or ""
        return f"Parking Lot{(' at ' + at) if at else ''}"

    base = _SMART_LABEL_MAP.get(t)
    if base:
        return f"{base} — {candidate_name}" if candidate_name else base

    if candidate_name:
        return candidate_name

    if place_type in {"neighbourhood", "township", "locality"}:
        return _pick_neighbourhood(addr) or _pick_city(addr) or "Place"

    return base_line1 or _pick_city(addr) or "Place"


# -------------------- public API --------------------------------------------

async def async_reverse_geocode(
    hass,
    lat: float,
    lon: float,
    contact: Optional[str] = None,
    lang: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Nominatim reverse geocode with structured output + classification + smart label.
    Returns a dict with:
      - Fields you already expose via const.ADDRESS_FIELD_KEYS:
          city, state, postcode, county, country,
          neighbourhood, suburb, city_district, borough, quarter,
          township, municipality, town, village, hamlet,
          osm_category, osm_type_detail, place_type, place_label,
          place_name, smart_place_label,
          (and 'full_address' is derived from 'display_name' when writing attrs)
      - Plus:
          line1 (our primary address/label line)
          display_name (raw Nominatim human string)
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

    # Primary first line and top-level classification inputs
    line1 = _make_line1(addr, display)
    category = (data.get("category") or "") or None
    type_detail = (data.get("type") or "") or None

    # Classify
    place_type, place_label = _classify_place(addr, line1, category, type_detail)

    # Top-level POI name if present
    place_name = data.get("name")  # e.g., "Allied Midwest Merchandisers"

    # Smart readable label
    smart_label = _smart_place_label(place_name, place_type, type_detail, line1, addr)

    # Build structured response
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
