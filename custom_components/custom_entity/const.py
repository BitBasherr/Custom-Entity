"""Constants and shared selectors for Custom Entity integration."""
from __future__ import annotations

from homeassistant.helpers.selector import selector

DOMAIN = "custom_entity"

# Core config keys
CONF_SOURCE_ENTITY = "source_entity"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_DEVICE_CLASS = "device_class"
CONF_INHERIT_ATTRS = "inherit_attributes"
CONF_PLATFORM = "platform"

# Options-flow extras
CONF_BATTERY_ENTITY = "battery_entity"
CONF_ATTRIBUTE_SENSORS = "attribute_sensors"       # {friendly → entity_id}
CONF_COMBINE = "combine"
CONF_COMBINE_ENTITY = "combine_entity"
CONF_COMBINE_ATTR_NAME = "combine_attr_name"
CONF_HYPHENATE_STATE = "hyphenate_state"
# Optional: a boolean-ish helper that must be ON for tracker == home
CONF_PRESENCE_HELPER = "presence_helper"

# Precision controls
# Legacy (pre-precision-split) — still honored for label precision
CONF_COMBINE_PRECISION = "combine_precision"
# New explicit keys
CONF_COMBINE_LABEL_PRECISION = "combine_label_precision"
CONF_COMBINE_ATTR_PRECISION = "combine_attribute_precision"
DEFAULT_COMBINE_PRECISION = 1  # default for both label and attribute

# Shared selectors (centralized so both config_flow and options_flow can import)
SELECT_ANY_ENTITY = selector({"entity": {}})
SELECT_SENSOR = selector({"entity": {"domain": "sensor"}})
SELECT_BOOLEANISH = selector({"entity": {"domain": ["input_boolean", "binary_sensor", "switch"]}})

# FIX: use a number selector (0–3) instead of select-with-int-options
SELECT_PRECISION = selector(
    {
        "number": {
            "min": 0,
            "max": 3,
            "step": 1,
            "mode": "box"
        }
    }
)
