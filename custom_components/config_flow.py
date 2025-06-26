"""Config flow for Custom Entity – now asks device-class and attributes."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    CONF_FRIENDLY_NAME,
    CONF_SOURCE_ENTITY,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
)

# ---------------- Helper: device-class lists --------------------------
_SENSOR_DEVICE_CLASSES = [
    "temperature", "humidity", "power", "energy", "voltage", "current",
    "pressure", "carbon_dioxide", "carbon_monoxide", "pm25", "signal_strength",
    "battery", "timestamp", "duration",
]

_BINARY_DEVICE_CLASSES = [
    "battery", "cold", "connectivity", "door", "garage_door", "heat",
    "light", "lock", "moisture", "motion", "moving", "occupancy",
    "opening", "plug", "power", "presence", "problem", "running",
    "safety", "smoke", "sound", "vibration", "window",
]

_DEVICE_CLASS_MAP = {
    Platform.SENSOR: _SENSOR_DEVICE_CLASSES,
    Platform.BINARY_SENSOR: _BINARY_DEVICE_CLASSES,
    # add more if you want
}


class CustomEntityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Three-step wizard."""

    VERSION = 2

    # ---------------- STEP 1 – pick source entity ---------------------
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._data = {
                CONF_FRIENDLY_NAME: user_input[CONF_FRIENDLY_NAME],
                CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
            }
            return await self.async_step_device_class()

        schema = vol.Schema(
            {
                vol.Required(CONF_FRIENDLY_NAME): str,
                vol.Required(CONF_SOURCE_ENTITY): selector({"entity": {}}),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    # ---------------- STEP 2 – choose device-class --------------------
    async def async_step_device_class(self, user_input=None):
        if user_input is not None:
            self._data[CONF_DEVICE_CLASS] = user_input[CONF_DEVICE_CLASS]
            return await self.async_step_inherit_attrs()

        src = self._data[CONF_SOURCE_ENTITY]
        domain = src.split(".")[0]
        platform = Platform(domain) if domain in Platform.__members__.values() else Platform.SENSOR
        class_options = _DEVICE_CLASS_MAP.get(platform, [])

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_CLASS): selector(
                    {
                        "select": {
                            "options": class_options or ["none"],
                            "mode": "dropdown",
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="device_class", data_schema=schema)

    # ---------------- STEP 3 – which attrs to inherit -----------------
    async def async_step_inherit_attrs(self, user_input=None):
        if user_input is not None:
            self._data[CONF_INHERIT_ATTRS] = user_input.get(CONF_INHERIT_ATTRS, [])
            return await self.async_step_combine_toggle()

        # Build multi-select of current attributes
        state = self.hass.states.get(self._data[CONF_SOURCE_ENTITY])
        attrs = list(state.attributes) if state else []

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_INHERIT_ATTRS,
                    default=[],
                ): selector(
                    {
                        "select": {
                            "options": attrs,
                            "mode": "dropdown",
                            "multiple": True,
                        }
                    }
                )
            }
        )
        return self.async_show_form(step_id="inherit_attrs", data_schema=schema)

    # ---------------- STEP 4 – combine toggle / details ---------------
    async def async_step_combine_toggle(self, user_input=None):
        if user_input is not None:
            if user_input.get(CONF_COMBINE):
                return await self.async_step_combine()
            self._data[CONF_COMBINE] = False
            return self.async_create_entry(
                title=self._data[CONF_FRIENDLY_NAME],
                data=self._data,
            )

        schema = vol.Schema(
            {vol.Required(CONF_COMBINE, default=False): bool}
        )
        return self.async_show_form(step_id="combine_toggle", data_schema=schema)

    async def async_step_combine(self, user_input=None):
        if user_input is not None:
            self._data.update(
                {
                    CONF_COMBINE: True,
                    CONF_COMBINE_ENTITY: user_input[CONF_COMBINE_ENTITY],
                    CONF_COMBINE_ATTR_NAME: user_input[CONF_COMBINE_ATTR_NAME],
                }
            )
            return self.async_create_entry(
                title=self._data[CONF_FRIENDLY_NAME],
                data=self._data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_COMBINE_ENTITY): selector({"entity": {"domain": "sensor"}}),
                vol.Required(CONF_COMBINE_ATTR_NAME): str,
            }
        )
        return self.async_show_form(step_id="combine", data_schema=schema)

    # ---------------- Handover to options flow ------------------------
    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry):
        from .options_flow import CustomEntityOptionsFlow  # local import to avoid cycle
        return CustomEntityOptionsFlow(config_entry)
