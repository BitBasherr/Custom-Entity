"""Config flow for Custom Entity (wizard-style, backward compatible)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    SUPPORTED_PLATFORMS,
    CONF_PLATFORM,
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,
    SELECT_ANY_ENTITY,
    SELECT_SENSOR,
)

# Optional curated device classes per platform (extend as you like).
DEVICE_CLASSES = {
    "sensor": [
        "temperature", "humidity", "energy", "voltage",
        "power", "battery", "timestamp"
    ],
    "binary_sensor": [
        "motion", "occupancy", "opening", "smoke",
        "sound", "vibration"
    ],
}


class CustomEntityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc]
    """Wizard‐style config flow with presence helper, inherit attrs, and combine."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    # ───────────────────────────── STEP 1 ─────────────────────────────
    # platform • friendly name • source entity • (optional) presence helper
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            platform = user_input[CONF_PLATFORM]
            friendly = (user_input.get(CONF_FRIENDLY_NAME) or "").strip()
            source = user_input[CONF_SOURCE_ENTITY]
            presence = user_input.get(CONF_PRESENCE_HELPER)

            self._data = {
                CONF_PLATFORM: platform,
                CONF_FRIENDLY_NAME: friendly,
                CONF_SOURCE_ENTITY: source,
            }
            if presence:
                self._data[CONF_PRESENCE_HELPER] = presence

            # Unique per (platform, source) to avoid dup entries
            await self.async_set_unique_id(f"{platform}:{source}")
            self._abort_if_unique_id_configured()

            return await self.async_step_device_class()

        platform_select = selector({
            "select": {"options": SUPPORTED_PLATFORMS, "mode": "dropdown"}
        })

        schema = vol.Schema({
            vol.Required(CONF_PLATFORM): platform_select,
            vol.Required(CONF_FRIENDLY_NAME): str,
            vol.Required(CONF_SOURCE_ENTITY): SELECT_ANY_ENTITY,
            vol.Optional(CONF_PRESENCE_HELPER): SELECT_ANY_ENTITY,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    # ───────────────────────────── STEP 2 ─────────────────────────────
    # device class (if applicable for the chosen platform)
    async def async_step_device_class(self, user_input=None):
        platform = self._data[CONF_PLATFORM]
        class_opts = DEVICE_CLASSES.get(platform, [])

        if user_input is not None:
            device_class = (user_input.get(CONF_DEVICE_CLASS) or "").strip()
            self._data[CONF_DEVICE_CLASS] = device_class or None
            return await self.async_step_inherit_attrs()

        if not class_opts:
            self._data[CONF_DEVICE_CLASS] = None
            return await self.async_step_inherit_attrs()

        schema = vol.Schema({
            vol.Optional(CONF_DEVICE_CLASS): selector({
                "select": {"options": class_opts, "mode": "dropdown"}
            })
        })
        return self.async_show_form(step_id="device_class", data_schema=schema)

    # ───────────────────────────── STEP 3 ─────────────────────────────
    # attributes to mirror (BACK-COMPAT: list-of-strings like you had before)
    async def async_step_inherit_attrs(self, user_input=None):
        if user_input is not None:
            self._data[CONF_INHERIT_ATTRS] = user_input.get(CONF_INHERIT_ATTRS, [])
            return await self.async_step_combine_toggle()

        attrs = []
        st = self.hass.states.get(self._data[CONF_SOURCE_ENTITY])
        if st and isinstance(st.attributes, dict):
            attrs = sorted([str(k) for k in st.attributes.keys()])

        schema = vol.Schema({
            vol.Optional(CONF_INHERIT_ATTRS): selector({
                "select": {
                    "options": attrs,
                    "multiple": True,
                    "mode": "dropdown"
                }
            })
        })
        return self.async_show_form(step_id="inherit_attrs", data_schema=schema)

    # ───────────────────────────── STEP 4 ─────────────────────────────
    # yes/no combine toggle (store in data for back-compat)
    async def async_step_combine_toggle(self, user_input=None):
        if user_input is not None:
            do_combine: bool = bool(user_input.get(CONF_COMBINE, False))
            if do_combine:
                return await self.async_step_combine()
            self._data[CONF_COMBINE] = False
            title = self._data.get(CONF_FRIENDLY_NAME) or f"{self._data[CONF_PLATFORM]} • {self._data[CONF_SOURCE_ENTITY]}"
            return self.async_create_entry(title=title, data=self._data)

        schema = vol.Schema({
            vol.Required(CONF_COMBINE, default=False): bool
        })
        return self.async_show_form(step_id="combine_toggle", data_schema=schema)

    # ───────────────────────────── STEP 5 ─────────────────────────────
    # combine details (entity, attr name) + hyphenate boolean (store in data)
    async def async_step_combine(self, user_input=None):
        if user_input is not None:
            combine_entity = user_input[CONF_COMBINE_ENTITY]
            combine_attr_name = (user_input.get(CONF_COMBINE_ATTR_NAME) or "").strip()
            hyphen = bool(user_input.get(CONF_HYPHENATE_STATE, False))

            self._data.update({
                CONF_COMBINE: True,
                CONF_COMBINE_ENTITY: combine_entity,
                CONF_COMBINE_ATTR_NAME: combine_attr_name,
                CONF_HYPHENATE_STATE: hyphen,
            })
            title = self._data.get(CONF_FRIENDLY_NAME) or f"{self._data[CONF_PLATFORM]} • {self._data[CONF_SOURCE_ENTITY]}"
            return self.async_create_entry(title=title, data=self._data)

        schema = vol.Schema({
            vol.Required(CONF_COMBINE_ENTITY): SELECT_SENSOR,
            vol.Required(CONF_COMBINE_ATTR_NAME): str,
            vol.Optional(CONF_HYPHENATE_STATE, default=False): bool,
        })
        return self.async_show_form(step_id="combine", data_schema=schema)

    # ───────────────────────── Options flow hook ───────────────────────
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        from .options_flow import CustomEntityOptionsFlow
        return CustomEntityOptionsFlow(config_entry)
