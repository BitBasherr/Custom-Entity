from __future__ import annotations

from homeassistant.helpers.selector import selector

DOMAIN = "custom_entity"

# ---------------- Core config keys (stored in entry.data) ----------------
CONF_PLATFORM = "platform"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_SOURCE_ENTITY = "source_entity"
CONF_DEVICE_CLASS = "device_class"
CONF_INHERIT_ATTRS = "inherit_attrs"

# ---------------- Optional features (stored in entry.options) ------------
CONF_BATTERY_ENTITY = "battery_entity"
CONF_ATTRIBUTE_SENSORS = "attribute_sensors"  # mapping: {friendly_name: entity_id}

# Combine (can be in options or data; entities read both for back-compat)
CONF_COMBINE = "combine"
CONF_COMBINE_ENTITY = "combine_entity"
CONF_COMBINE_ATTR_NAME = "combine_attr_name"
CONF_HYPHENATE_STATE = "hyphenate_state"

# Presence helper (device_tracker convenience)
CONF_PRESENCE_HELPER = "presence_helper"

# Precision controls (kept as strings in UI; parsed to int by entities)
CONF_COMBINE_LABEL_PRECISION = "combine_label_precision"  # hyphenated label decimals
CONF_COMBINE_ATTR_PRECISION = "combine_attr_precision"    # attribute decimals (non-hyphen)
CONF_COMBINE_PRECISION = "combine_precision"              # legacy single knob (back-compat)
DEFAULT_COMBINE_PRECISION = 1

# ---------------- Person Label sensor mode -------------------------------
CONF_SENSOR_MODE = "sensor_mode"
SENSOR_MODE_MIRROR = "mirror"
SENSOR_MODE_PERSON_LABEL = "person_label"

CONF_PERSON_ENTITY = "person_entity"
CONF_LABEL_ATTR = "label_attr"
DEFAULT_LABEL_ATTR = "address"   # attribute name to expose street+number

# NEW: Primary label selection (controls label_attr, and Person-Label sensor state)
CONF_LABEL_MODE = "label_mode"   # "line1" | "smart" | "place_name"
LABEL_MODE_OPTIONS = [
    {"label": "Line 1 (street/number)", "value": "line1"},
    {"label": "Smart label first",      "value": "smart"},
    {"label": "Place name first",       "value": "place_name"},
]
SELECT_LABEL_MODE = selector({
    "select": {"options": LABEL_MODE_OPTIONS, "mode": "list"}
})

# ---------------- Reverse geocode (stored in entry.data) -----------------
CONF_AUTO_ADDRESS = "auto_address"
CONF_ADDRESS_MIN_MOVE_MI = "address_min_move_mi"
CONF_ADDRESS_MIN_INTERVAL_MIN = "address_min_interval_min"
CONF_GEOCODE_PROVIDER = "geocode_provider"
CONF_GEOCODE_CONTACT = "geocode_contact"  # email or URL per Nominatim policy
DEFAULT_ADDRESS_MIN_MOVE_MI = 0.1        # miles
DEFAULT_ADDRESS_MIN_INTERVAL_MIN = 5     # minutes
DEFAULT_GEOCODE_PROVIDER = "nominatim"

# ---------------- Address fields selection -------------------------------
CONF_ADDRESS_FIELDS = "address_fields"

# Full list of structured address keys our geocoder can return (selectable)
# NOTE: 'line1' is injected into label_attr and is not separately selectable.
ADDRESS_FIELD_KEYS = [
    # canonical / common
    "city", "state", "postcode", "county", "country",
    # locality granularity
    "neighbourhood", "suburb", "city_district", "borough", "quarter",
    "township", "municipality", "town", "village", "hamlet",
    # OSM raw meta
    "osm_category", "osm_type_detail",
    # our classification layer
    "place_type", "place_label", "smart_place_label",
    # human name (OSM 'name' or first display component)
    "place_name",
    # convenience
    "full_address",
]

# Defaults — select **all** fields by default
DEFAULT_ADDRESS_FIELDS = list(ADDRESS_FIELD_KEYS)

# Selector for address fields (nice labels)
ADDRESS_FIELD_OPTIONS = [
    {"label": "City",               "value": "city"},
    {"label": "State",              "value": "state"},
    {"label": "Postcode",           "value": "postcode"},
    {"label": "County",             "value": "county"},
    {"label": "Country",            "value": "country"},
    {"label": "Neighborhood",       "value": "neighbourhood"},
    {"label": "Suburb",             "value": "suburb"},
    {"label": "City District",      "value": "city_district"},
    {"label": "Borough",            "value": "borough"},
    {"label": "Quarter",            "value": "quarter"},
    {"label": "Township",           "value": "township"},
    {"label": "Municipality",       "value": "municipality"},
    {"label": "Town",               "value": "town"},
    {"label": "Village",            "value": "village"},
    {"label": "Hamlet",             "value": "hamlet"},
    {"label": "OSM Category",       "value": "osm_category"},
    {"label": "OSM Type Detail",    "value": "osm_type_detail"},
    {"label": "Place Type (coarse)","value": "place_type"},
    {"label": "Place Label (coarse)","value": "place_label"},
    {"label": "Smart Place Label",  "value": "smart_place_label"},
    {"label": "Place Name",         "value": "place_name"},
    {"label": "Full Address",       "value": "full_address"},
]
SELECT_ADDRESS_FIELDS = selector({
    "select": {"options": ADDRESS_FIELD_OPTIONS, "multiple": True, "mode": "list"}
})

# --- Combine unit override + suffix (UI + storage; used by sensor) -------
CONF_COMBINE_UNIT_MODE = "combine_unit_mode"   # "auto" | "sec_to_min" | "hr_to_min" | "none"
CONF_COMBINE_SUFFIX    = "combine_suffix"      # e.g. " min"

COMBINE_UNIT_MODE_OPTIONS = [
    {"label": "Auto (use source unit)", "value": "auto"},
    {"label": "Seconds → Minutes",      "value": "sec_to_min"},
    {"label": "Hours → Minutes",        "value": "hr_to_min"},
    {"label": "No conversion",          "value": "none"},
]
SELECT_COMBINE_UNIT_MODE = selector({
    "select": {"options": COMBINE_UNIT_MODE_OPTIONS, "mode": "list"}
})

# ---------------- Supported platforms ------------------------------------
SUPPORTED_PLATFORMS = [
    "sensor",
    "binary_sensor",
    "switch",
    "number",
    "text",
    "light",
    "device_tracker",
    "select",
    "button",
    "climate",
]

# Only these platforms meaningfully support device_class
PLATFORMS_WITH_DEVICE_CLASS = {
    "sensor",
    "binary_sensor",
    "light",
    "climate",
}

# Suggestions for device_class (user can still free-type where lists are empty)
DEVICE_CLASSES = {
    "sensor": [
        "temperature", "humidity", "energy", "voltage",
        "power", "battery", "timestamp", "speed", "signal_strength",
    ],
    "binary_sensor": [
        "motion", "occupancy", "opening", "smoke", "sound", "vibration", "presence",
    ],
    "light": [],
    "climate": [],
}

# ---------------- Selectors (UI helpers) ---------------------------------
SELECT_ANY_ENTITY = selector({"entity": {}})
SELECT_SENSOR = selector({"entity": {"domain": "sensor"}})
SELECT_PERSON = selector({"entity": {"domain": "person"}})
SELECT_DEVICE_TRACKER = selector({"entity": {"domain": "device_tracker"}})

# Precision choices (string values satisfy HA's SelectSelector validation)
PRECISION_OPTIONS = [
    {"label": "0  (e.g., 12)",    "value": "0"},
    {"label": "1  (e.g., 12.3)",  "value": "1"},
    {"label": "2  (e.g., 12.34)", "value": "2"},
    {"label": "3  (e.g., 12.345)","value": "3"},
]
SELECT_PRECISION = selector({
    "select": {"options": PRECISION_OPTIONS, "mode": "list"}
})

# Sliders for distance/interval
SELECT_MILES_SLIDER = selector({
    "number": {"min": 0.01, "max": 5.0, "step": 0.01, "mode": "slider", "unit_of_measurement": "mi"}
})
SELECT_MINUTES_SLIDER = selector({
    "number": {"min": 1, "max": 180, "step": 1, "mode": "slider", "unit_of_measurement": "min"}
})

# ---------------- Options→Data bridge markers ----------------------------
OPT_APPLY_DATA_UPDATE = "apply_data_update"
DATA_MUTABLE_KEYS = {
    CONF_PLATFORM,
    CONF_FRIENDLY_NAME,
    CONF_SOURCE_ENTITY,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    # person-label + auto-address
    CONF_SENSOR_MODE,
    CONF_PERSON_ENTITY,
    CONF_LABEL_ATTR,
    CONF_LABEL_MODE,  # NEW
    CONF_AUTO_ADDRESS,
    CONF_ADDRESS_MIN_MOVE_MI,
    CONF_ADDRESS_MIN_INTERVAL_MIN,
    CONF_GEOCODE_PROVIDER,
    CONF_GEOCODE_CONTACT,
    CONF_ADDRESS_FIELDS,
}
