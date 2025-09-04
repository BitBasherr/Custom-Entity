"""Constants and shared selectors for Custom Entity integration."""
from __future__ import annotations

from homeassistant.helpers.selector import selector

DOMAIN = "custom_entity"

# Core config keys (entry.data)
CONF_SOURCE_ENTITY = "source_entity"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_DEVICE_CLASS = "device_class"
CONF_INHERIT_ATTRS = "inherit_attributes"  # bool
CONF_PLATFORM = "platform"                  # one of the supported platforms

# Options-flow extras (entry.options)
CONF_BATTERY_ENTITY = "battery_entity"
CONF_ATTRIBUTE_SENSORS = "attribute_sensors"       # {friendly -> entity_id}
CONF_COMBINE = "combine"
CONF_COMBINE_ENTITY = "combine_entity"
CONF_COMBINE_ATTR_NAME = "combine_attr_name"
CONF_HYPHENATE_STATE = "hyphenate_state"
# Optional: boolean-ish helper that must be ON for tracker to report 'home'
CONF_PRESENCE_HELPER = "presence_helper"

# Precision controls
# Legacy single knob (back-compat) – still honored for label precision
CONF_COMBINE_PRECISION = "combine_precision"
# New explicit keys
CONF_COMBINE_LABEL_PRECISION = "combine_label_precision"
CONF_COMBINE_ATTR_PRECISION = "combine_attribute_precision"
DEFAULT_COMBINE_PRECISION = 1  # default for both label and attribute

# Platform list we support (must match available files)
SUPPORTED_PLATFORMS: list[str] = [
    "sensor",
    "binary_sensor",
    "number",
    "switch",
    "device_tracker",
    "light",
    "climate",
    "select",
    "text",
    "button",
]

# ───────────── Shared selectors (used by config_flow / options_flow) ─────────────
# Any entity selector (needed by Options for battery and attribute mapping)
SELECT_ANY_ENTITY = selector({"entity": {}})

# Specific helpers where we want to constrain domains
SELECT_SENSOR = selector({"entity": {"domain": "sensor"}})
SELECT_TRACKER = selector({"entity": {"domain": "device_tracker"}})
SELECT_BOOLEANISH = selector({"entity": {"domain": ["input_boolean", "binary_sensor", "switch"]}})

# Integer precision picker 0–3 (validated as integer, not strings)
SELECT_PRECISION = selector({"number": {"min": 0, "max": 3, "step": 1, "mode": "box"}})
