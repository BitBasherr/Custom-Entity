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

# Combine
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
DEFAULT_LABEL_ATTR = "address"   # default attribute name to expose as label

# Auto-address (reverse-geocode) config (stored in entry.data)
CONF_AUTO_ADDRESS = "auto_address"
CONF_ADDRESS_MIN_MOVE_MI = "address_min_move_mi"
CONF_ADDRESS_MIN_INTERVAL_MIN = "address_min_interval_min"
CONF_GEOCODE_PROVIDER = "geocode_provider"
CONF_GEOCODE_CONTACT = "geocode_contact"  # email or URL per Nominatim policy

DEFAULT_ADDRESS_MIN_MOVE_MI = 0.1        # miles
DEFAULT_ADDRESS_MIN_INTERVAL_MIN = 5     # minutes
DEFAULT_GEOCODE_PROVIDER = "nominatim"

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
    "light": [],     # free-text
    "climate": [],   # free-text
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
    "select": {
        "options": PRECISION_OPTIONS,
        "mode": "list"
    }
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
    CONF_AUTO_ADDRESS,
    CONF_ADDRESS_MIN_MOVE_MI,
    CONF_ADDRESS_MIN_INTERVAL_MIN,
    CONF_GEOCODE_PROVIDER,
    CONF_GEOCODE_CONTACT,
}
