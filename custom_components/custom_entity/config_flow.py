"""Config flow for Custom Entity."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import selector
from homeassistant.const import Platform

from .const import DOMAIN, CONF_SOURCE_ENTITY, CONF_FRIENDLY_NAME, CONF_DEVICE_CLASS, CONF_INHERIT_ATTRS, CONF_PLATFORM

PLATFORM_OPTIONS = [
    "sensor", "binary_sensor", "switch", "number", "text", "light",
    "device_tracker", "select", "button", "climate"
]

DEVICE_CLASSES = {
    "sensor": ["temperature", "humidity", "energy", "voltage", "power", "battery", "timestamp"],
    "binary_sensor": ["motion", "occupancy", "opening", "smoke", "sound", "vibration"],
    "number": [],
    "switch": [],
    "device_tracker": [],
    "light": [],
    "climate": [],
    "select": [],
    "text": [],
    "button": [],
}


class CustomEntityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._data = {
                CONF_PLATFORM: user_input[CONF_PLATFORM],
                CONF_FRIENDLY_NAME: user_input[CONF_FRIENDLY_NAME],
                CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
            }
            return await self.async_step_device_class()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PLATFORM): selector({
                        "select": {
                            "options": PLATFORM_OPTIONS,
                            "mode": "dropdown"
                        }
                    }),
                    vol.Required(CONF_FRIENDLY_NAME): str,
                    vol.Required(CONF_SOURCE_ENTITY): selector({"entity": {}})
                }
            )
        )

    async def async_step_device_class(self, user_input=None):
        platform = self._data[CONF_PLATFORM]
        class_opts = DEVICE_CLASSES.get(platform, [])

        if user_input is not None:
            self._data[CONF_DEVICE_CLASS] = user_input.get(CONF_DEVICE_CLASS)
            return await self.async_step_inherit_attrs()

        schema = {}
        if class_opts:
            schema[vol.Optional(CONF_DEVICE_CLASS)] = selector({
                "select": {
                    "options": class_opts,
                    "mode": "dropdown"
                }
            })

        return self.async_show_form(
            step_id="device_class",
            data_schema=vol.Schema(schema) if schema else vol.Schema({}),
        )

    async def async_step_inherit_attrs(self, user_input=None):
        if user_input is not None:
            self._data[CONF_INHERIT_ATTRS] = user_input.get(CONF_INHERIT_ATTRS, [])
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        state = self.hass.states.get(self._data[CONF_SOURCE_ENTITY])
        attrs = list(state.attributes) if state else []

        return self.async_show_form(
            step_id="inherit_attrs",
            data_schema=vol.Schema({
                vol.Optional(CONF_INHERIT_ATTRS): selector({
                    "select": {
                        "options": attrs,
                        "mode": "dropdown",
                        "multiple": True
                    }
                })
            })
        )
