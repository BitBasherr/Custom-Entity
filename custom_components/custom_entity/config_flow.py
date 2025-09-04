"""Config flow for Custom Entity."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    SUPPORTED_PLATFORMS,
    PLATFORMS_WITH_DEVICE_CLASS,
    DEVICE_CLASSES,
    # keys
    CONF_PLATFORM,
    CONF_FRIENDLY_NAME,
    CONF_SOURCE_ENTITY,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,
    SELECT_PRECISION,
    SELECT_ANY_ENTITY,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_ATTR_PRECISION,
    DEFAULT_COMBINE_PRECISION,
)

def _guess_device_class(hass, entity_id: str) -> str | None:
    st = hass.states.get(entity_id)
    if not st:
        return None
    dc = st.attributes.get("device_class")
    if isinstance(dc, str) and dc:
        return dc
    return None


class CustomEntityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wizard style setup; mirrors Options flow fields."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Normalize to strings
            platform = str(user_input[CONF_PLATFORM])
            friendly = str(user_input[CONF_FRIENDLY_NAME])
            source = str(user_input[CONF_SOURCE_ENTITY])
            presence = user_input.get(CONF_PRESENCE_HELPER)
            presence = str(presence) if presence else None

            data = {
                CONF_PLATFORM: platform,
                CONF_FRIENDLY_NAME: friendly,
                CONF_SOURCE_ENTITY: source,
            }

            # Optional presence helper (meaningful mostly for device_tracker)
            if presence:
                data[CONF_PRESENCE_HELPER] = presence

            # Pre-fill device_class if that platform supports it
            if platform in PLATFORMS_WITH_DEVICE_CLASS:
                dc = _guess_device_class(self.hass, source)
                if dc:
                    data[CONF_DEVICE_CLASS] = dc

            self._data = data
            return await self.async_step_inherit_attrs()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PLATFORM): selector({"select": {
                    "options": SUPPORTED_PLATFORMS, "mode": "dropdown"}}),
                vol.Required(CONF_FRIENDLY_NAME): str,
                vol.Required(CONF_SOURCE_ENTITY): SELECT_ANY_ENTITY,
                vol.Optional(CONF_PRESENCE_HELPER): SELECT_ANY_ENTITY,
            }),
        )

    async def async_step_inherit_attrs(self, user_input=None):
        if user_input is not None:
            inherit = user_input.get(CONF_INHERIT_ATTRS, [])
            if not isinstance(inherit, list):
                inherit = []
            self._data[CONF_INHERIT_ATTRS] = inherit
            return await self.async_step_combine()

        attrs = []
        st = self.hass.states.get(self._data[CONF_SOURCE_ENTITY])
        if st:
            attrs = list(st.attributes.keys())

        return self.async_show_form(
            step_id="inherit_attrs",
            data_schema=vol.Schema({
                vol.Optional(CONF_INHERIT_ATTRS): selector({
                    "select": {"options": attrs, "multiple": True, "mode": "dropdown"}
                })
            }),
        )

    async def async_step_combine(self, user_input=None):
        if user_input is not None:
            combine_on = bool(user_input.get(CONF_COMBINE, False))
            if combine_on:
                combine_entity = str(user_input[CONF_COMBINE_ENTITY])
                label_prec = int(str(user_input.get(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION)))
                attr_prec = int(str(user_input.get(CONF_COMBINE_ATTR_PRECISION, label_prec)))
                hyphen = bool(user_input.get(CONF_HYPHENATE_STATE, False))

                self._data.update({
                    CONF_COMBINE: True,
                    CONF_COMBINE_ENTITY: combine_entity,
                    CONF_COMBINE_ATTR_NAME: str(user_input.get(CONF_COMBINE_ATTR_NAME) or "combine"),
                    CONF_HYPHENATE_STATE: hyphen,
                    CONF_COMBINE_LABEL_PRECISION: label_prec,
                    CONF_COMBINE_ATTR_PRECISION: attr_prec,
                })
            else:
                self._data[CONF_COMBINE] = False

            # If platform supports device_class but we never guessed it, let the user type/choose now.
            if self._data[CONF_PLATFORM] in PLATFORMS_WITH_DEVICE_CLASS:
                return await self.async_step_device_class()

            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        # combine UI
        return self.async_show_form(
            step_id="combine",
            data_schema=vol.Schema({
                vol.Required(CONF_COMBINE, default=False): bool,
                vol.Optional(CONF_COMBINE_ENTITY): SELECT_ANY_ENTITY,
                vol.Optional(CONF_COMBINE_ATTR_NAME, default="combine"): str,
                vol.Optional(CONF_HYPHENATE_STATE, default=True): bool,
                vol.Optional(CONF_COMBINE_LABEL_PRECISION, default=str(DEFAULT_COMBINE_PRECISION)): SELECT_PRECISION,
                vol.Optional(CONF_COMBINE_ATTR_PRECISION, default=str(DEFAULT_COMBINE_PRECISION)): SELECT_PRECISION,
            }),
        )

    async def async_step_device_class(self, user_input=None):
        platform = self._data[CONF_PLATFORM]
        if platform not in PLATFORMS_WITH_DEVICE_CLASS:
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        suggestions = DEVICE_CLASSES.get(platform, [])
        if user_input is not None:
            dc = user_input.get(CONF_DEVICE_CLASS)
            if dc:
                self._data[CONF_DEVICE_CLASS] = str(dc)
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        guessed = self._data.get(CONF_DEVICE_CLASS)  # maybe set earlier
        if suggestions:
            schema = vol.Schema({
                vol.Optional(CONF_DEVICE_CLASS, default=guessed or suggestions[0]): selector({
                    "select": {"options": suggestions, "mode": "list"}
                })
            })
        else:
            schema = vol.Schema({
                vol.Optional(CONF_DEVICE_CLASS, default=guessed or ""): str
            })

        return self.async_show_form(step_id="device_class", data_schema=schema)

    # Options flow hook
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        from .options_flow import CustomEntityOptionsFlow
        return CustomEntityOptionsFlow(config_entry)
