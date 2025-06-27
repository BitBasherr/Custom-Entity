"""Config flow for Custom Entity."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    CONF_SOURCE_ENTITY,
    CONF_PLATFORM,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
)

PLATFORM_OPTIONS = [
    "sensor", "binary_sensor", "switch", "number", "text", "light",
    "device_tracker", "select", "button", "climate"
]

DEVICE_CLASSES = {
    "sensor": ["temperature", "humidity", "energy", "voltage", "power", "battery", "timestamp"],
    "binary_sensor": ["motion", "occupancy", "opening", "smoke", "sound", "vibration"],
}

SELECT_ANY_ENTITY = selector({"entity": {}})
SELECT_SENSOR = selector({"entity": {"domain": "sensor"}})


class CustomEntityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wizard‐style config flow with optional combine."""

    VERSION = 1

    # ── STEP 1 ── platform • name • source
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._data = {
                CONF_PLATFORM:      user_input[CONF_PLATFORM],
                CONF_FRIENDLY_NAME: user_input[CONF_FRIENDLY_NAME],
                CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
            }
            return await self.async_step_device_class()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PLATFORM): selector({
                    "select": {"options": PLATFORM_OPTIONS, "mode": "dropdown"}
                }),
                vol.Required(CONF_FRIENDLY_NAME): str,
                vol.Required(CONF_SOURCE_ENTITY): SELECT_ANY_ENTITY,
            }),
        )

    # ── STEP 2 ── device class (if any)
    async def async_step_device_class(self, user_input=None):
        platform = self._data[CONF_PLATFORM]
        class_opts = DEVICE_CLASSES.get(platform, [])

        if user_input is not None:
            self._data[CONF_DEVICE_CLASS] = user_input.get(CONF_DEVICE_CLASS)
            return await self.async_step_inherit_attrs()

        if not class_opts:
            self._data[CONF_DEVICE_CLASS] = None
            return await self.async_step_inherit_attrs()

        return self.async_show_form(
            step_id="device_class",
            data_schema=vol.Schema({
                vol.Optional(CONF_DEVICE_CLASS): selector({
                    "select": {"options": class_opts, "mode": "dropdown"}
                })
            }),
        )

    # ── STEP 3 ── attributes to mirror
    async def async_step_inherit_attrs(self, user_input=None):
        if user_input is not None:
            self._data[CONF_INHERIT_ATTRS] = user_input.get(CONF_INHERIT_ATTRS, [])
            return await self.async_step_combine_toggle()

        state = self.hass.states.get(self._data[CONF_SOURCE_ENTITY])
        attrs = list(state.attributes) if state else []

        return self.async_show_form(
            step_id="inherit_attrs",
            data_schema=vol.Schema({
                vol.Optional(CONF_INHERIT_ATTRS): selector({
                    "select": {
                        "options": attrs,
                        "multiple": True,
                        "mode": "dropdown",
                    }
                })
            }),
        )

    # ── STEP 4 ── yes/no combine
    async def async_step_combine_toggle(self, user_input=None):
        if user_input is not None:
            if user_input.get(CONF_COMBINE):
                return await self.async_step_combine()
            self._data[CONF_COMBINE] = False
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        return self.async_show_form(
            step_id="combine_toggle",
            data_schema=vol.Schema({
                vol.Required(CONF_COMBINE, default=False): bool,
            }),
        )

    # ── STEP 5 ── combine details + hyphenate
    async def async_step_combine(self, user_input=None):
        if user_input is not None:
            self._data.update({
                CONF_COMBINE:           True,
                CONF_COMBINE_ENTITY:    user_input[CONF_COMBINE_ENTITY],
                CONF_COMBINE_ATTR_NAME: user_input[CONF_COMBINE_ATTR_NAME],
                CONF_HYPHENATE_STATE:   user_input.get(CONF_HYPHENATE_STATE, False),
            })
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        return self.async_show_form(
            step_id="combine",
            data_schema=vol.Schema({
                vol.Required(CONF_COMBINE_ENTITY): SELECT_SENSOR,
                vol.Required(CONF_COMBINE_ATTR_NAME): str,
                vol.Optional(CONF_HYPHENATE_STATE, default=False): bool,
            }),
        )

    # ── expose Options flow ──
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        from .options_flow import CustomEntityOptionsFlow
        return CustomEntityOptionsFlow(config_entry)
