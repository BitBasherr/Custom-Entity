"""Constants and shared selectors for Custom Entity integration."""
from __future__ import annotations

from homeassistant.helpers.selector import selector

DOMAIN = "custom_entity"

# Core config keys (entry.data)
CONF_PLATFORM = "platform"  # sensor, binary_sensor, number, switch, device_tracker, light, climate, select, text, button
CONF_SOURCE_ENTITY = "source_entity"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_DEVICE_CLASS = "device_class"

# Back-compat: previously this could be a LIST of attribute names.
# We keep list semantics; newer builds may also store bool elsewhere, but we stick to list here for consistency.
CONF_INHERIT_ATTRS = "inherit_attributes"

# Options-flow keys (entry.options)
CONF_BATTERY_ENTITY = "battery_entity"
CONF_ATTRIBUTE_SENSORS = "attribute_sensors"  # {friendly -> entity_id}
CONF_COMBINE = "combine"
CONF_COMBINE_ENTITY = "combine_entity"
CONF_COMBINE_ATTR_NAME = "combine_attr_name"
CONF_HYPHENATE_STATE = "hyphenate_state"
CONF_PRESENCE_HELPER = "presence_helper"

# Precision controls (store as ints: 0,1,2,3)
# Legacy single knob (back-compat)
CONF_COMBINE_PRECISION = "combine_precision"
# New explicit keys
CONF_COMBINE_LABEL_PRECISION = "combine_label_precision"
CONF_COMBINE_ATTR_PRECISION = "combine_attribute_precision"
DEFAULT_COMBINE_PRECISION = 1  # default for both label and attribute

# Platform list we support
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

# Selectors used by config/option flows
SELECT_ANY_ENTITY = selector({"entity": {}})
SELECT_SENSOR = selector({"entity": {"domain": "sensor"}})
SELECT_TRACKER = selector({"entity": {"domain": "device_tracker"}})
SELECT_BOOLEANISH = selector({"entity": {"domain": ["input_boolean", "binary_sensor", "switch"]}})

# Visual, human-friendly precision selector: shows "0 (integer), 0.1, 0.01, 0.001" but returns 0/1/2/3.
PRECISION_OPTIONS = [
    {"value": 0, "label": "0 (integer)"},
    {"value": 1, "label": "0.1"},
    {"value": 2, "label": "0.01"},
    {"value": 3, "label": "0.001"},
]
SELECT_PRECISION = selector({"select": {"options": PRECISION_OPTIONS, "mode": "list"}})

# ───────── Internal (Options→Data bridge) ─────────
# The options flow can request core data updates (platform/source/etc.) by
# writing these markers into options; the update listener applies and cleans.
OPT_APPLY_DATA_UPDATE = "__apply_data_update__"
DATA_MUTABLE_KEYS = [
    CONF_PLATFORM,
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
]
