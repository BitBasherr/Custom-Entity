"""Config flow for Custom Entity (sensor/device_tracker, address fields, smart labels)."""
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
    # data keys
    CONF_PLATFORM,
    CONF_FRIENDLY_NAME,
    CONF_SOURCE_ENTITY,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    # sensor/person-label
    CONF_SENSOR_MODE,
    SENSOR_MODE_MIRROR,
    SENSOR_MODE_PERSON_LABEL,
    CONF_PERSON_ENTITY,
    CONF_LABEL_ATTR,
    DEFAULT_LABEL_ATTR,
    # auto-address
    CONF_AUTO_ADDRESS,
    CONF_ADDRESS_MIN_MOVE_MI,
    CONF_ADDRESS_MIN_INTERVAL_MIN,
    CONF_GEOCODE_PROVIDER,
    CONF_GEOCODE_CONTACT,
    DEFAULT_ADDRESS_MIN_MOVE_MI,
    DEFAULT_ADDRESS_MIN_INTERVAL_MIN,
    DEFAULT_GEOCODE_PROVIDER,
    # address fields
    CONF_ADDRESS_FIELDS,
    SELECT_ADDRESS_FIELDS,
    ADDRESS_FIELD_OPTIONS,
    # selectors
    SELECT_ANY_ENTITY,
    SELECT_PERSON,
    SELECT_DEVICE_TRACKER,
    SELECT_MILES_SLIDER,
    SELECT_MINUTES_SLIDER,
    SELECT_PRECISION,
    # combine (stored in data here; options flow can refine later)
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_ATTR_PRECISION,
    DEFAULT_COMBINE_PRECISION,
    # optional presence helper (for device_tracker)
    CONF_PRESENCE_HELPER,
)

SENSOR_MODE_OPTIONS = [
    {"label": "Mirror (default)", "value": SENSOR_MODE_MIRROR},
    {"label": "Person Label (sensor)", "value": SENSOR_MODE_PERSON_LABEL},
]


def _guess_device_class(hass, entity_id: str) -> str | None:
    st = hass.states.get(entity_id)
    if not st:
        return None
    dc = st.attributes.get("device_class")
    if isinstance(dc, str) and dc:
        return dc
    return None


# ---------- Address fields helpers ----------
_ALLOWED_ADDR_VALUES = tuple(opt["value"] for opt in ADDRESS_FIELD_OPTIONS)


def _sanitize_address_list(value) -> list[str]:
    """Ensure list contains only allowed address field tokens; default to ALL if empty/invalid."""
    if isinstance(value, (tuple, set)):
        value = list(value)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        value = []
    cleaned = [v for v in value if v in _ALLOWED_ADDR_VALUES]
    if not cleaned:
        # Default to ALL available fields as requested
        cleaned = list(_ALLOWED_ADDR_VALUES)
    return cleaned


class CustomEntityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Top-level config flow."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """First step: platform + basics."""
        if user_input is not None:
            platform = str(user_input[CONF_PLATFORM])
            friendly = str(user_input[CONF_FRIENDLY_NAME])
            source = str(user_input.get(CONF_SOURCE_ENTITY) or "")
            presence = str(user_input.get(CONF_PRESENCE_HELPER)) if user_input.get(CONF_PRESENCE_HELPER) else None
            sensor_mode = user_input.get(CONF_SENSOR_MODE, SENSOR_MODE_MIRROR)
            person = user_input.get(CONF_PERSON_ENTITY)

            data = {
                CONF_PLATFORM: platform,
                CONF_FRIENDLY_NAME: friendly,
                CONF_SOURCE_ENTITY: source,
            }
            if presence:
                data[CONF_PRESENCE_HELPER] = presence
            if person:
                data[CONF_PERSON_ENTITY] = str(person)

            # Sensor-specific branching
            if platform == "sensor":
                data[CONF_SENSOR_MODE] = sensor_mode
                if sensor_mode == SENSOR_MODE_PERSON_LABEL:
                    self._data = data
                    return await self.async_step_person_label_details()

            # Tracker-specific branching
            if platform == "device_tracker":
                self._data = data
                return await self.async_step_tracker_details()

            # Optional device class suggestion
            if platform in PLATFORMS_WITH_DEVICE_CLASS:
                dc = _guess_device_class(self.hass, source)
                if dc:
                    data[CONF_DEVICE_CLASS] = dc

            self._data = data
            return await self.async_step_inherit_attrs()

        # Base entry form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PLATFORM): selector({"select": {
                    "options": SUPPORTED_PLATFORMS, "mode": "dropdown"}}),
                vol.Required(CONF_FRIENDLY_NAME): str,
                vol.Optional(CONF_SOURCE_ENTITY): SELECT_ANY_ENTITY,
                vol.Optional(CONF_PERSON_ENTITY): SELECT_PERSON,
                vol.Optional(CONF_PRESENCE_HELPER): SELECT_ANY_ENTITY,
                vol.Optional(CONF_SENSOR_MODE, default=SENSOR_MODE_MIRROR): selector({
                    "select": {"options": SENSOR_MODE_OPTIONS, "mode": "list"}
                }),
            }),
        )

    async def async_step_tracker_details(self, user_input=None):
        """device_tracker-only: reverse geocode knobs + address fields."""
        if user_input is not None:
            tracker = user_input.get("tracker_entity") or self._data.get(CONF_SOURCE_ENTITY)
            self._data[CONF_SOURCE_ENTITY] = str(tracker) if tracker else ""

            self._data[CONF_LABEL_ATTR] = str(user_input.get(CONF_LABEL_ATTR) or DEFAULT_LABEL_ATTR).strip()
            self._data[CONF_AUTO_ADDRESS] = bool(user_input.get(CONF_AUTO_ADDRESS, True))
            self._data[CONF_ADDRESS_MIN_MOVE_MI] = float(user_input.get(CONF_ADDRESS_MIN_MOVE_MI, DEFAULT_ADDRESS_MIN_MOVE_MI))
            self._data[CONF_ADDRESS_MIN_INTERVAL_MIN] = int(user_input.get(CONF_ADDRESS_MIN_INTERVAL_MIN, DEFAULT_ADDRESS_MIN_INTERVAL_MIN))
            self._data[CONF_GEOCODE_PROVIDER] = str(user_input.get(CONF_GEOCODE_PROVIDER, DEFAULT_GEOCODE_PROVIDER))
            contact = user_input.get(CONF_GEOCODE_CONTACT)
            if contact is not None:
                self._data[CONF_GEOCODE_CONTACT] = str(contact)

            fields = _sanitize_address_list(user_input.get(CONF_ADDRESS_FIELDS))
            self._data[CONF_ADDRESS_FIELDS] = fields

            return await self.async_step_inherit_attrs()

        # Defaults for the control (sanitize any existing data)
        default_fields = _sanitize_address_list(self._data.get(CONF_ADDRESS_FIELDS))

        schema = vol.Schema({
            vol.Optional("tracker_entity", default=self._data.get(CONF_SOURCE_ENTITY, "")): SELECT_DEVICE_TRACKER,
            vol.Optional(CONF_LABEL_ATTR, default=DEFAULT_LABEL_ATTR): str,
            vol.Optional(CONF_AUTO_ADDRESS, default=True): bool,
            vol.Optional(CONF_ADDRESS_MIN_MOVE_MI, default=DEFAULT_ADDRESS_MIN_MOVE_MI): SELECT_MILES_SLIDER,
            vol.Optional(CONF_ADDRESS_MIN_INTERVAL_MIN, default=DEFAULT_ADDRESS_MIN_INTERVAL_MIN): SELECT_MINUTES_SLIDER,
            vol.Optional(CONF_GEOCODE_PROVIDER, default=DEFAULT_GEOCODE_PROVIDER): selector({
                "select": {"options": [{"label": "OSM Nominatim (free)", "value": "nominatim"}], "mode": "list"}
            }),
            vol.Optional(CONF_GEOCODE_CONTACT): str,
            vol.Optional(CONF_ADDRESS_FIELDS, default=default_fields): SELECT_ADDRESS_FIELDS,
        })
        return self.async_show_form(step_id="tracker_details", data_schema=schema)

    async def async_step_person_label_details(self, user_input=None):
        """sensor-only when sensor_mode=person_label: person+tracker+address fields."""
        if user_input is not None:
            self._data[CONF_PERSON_ENTITY] = str(user_input[CONF_PERSON_ENTITY])
            self._data[CONF_SOURCE_ENTITY] = str(user_input.get(CONF_SOURCE_ENTITY) or user_input.get("tracker_entity") or "")
            self._data[CONF_LABEL_ATTR] = str(user_input.get(CONF_LABEL_ATTR) or DEFAULT_LABEL_ATTR).strip()

            self._data[CONF_AUTO_ADDRESS] = bool(user_input.get(CONF_AUTO_ADDRESS, True))
            self._data[CONF_ADDRESS_MIN_MOVE_MI] = float(user_input.get(CONF_ADDRESS_MIN_MOVE_MI, DEFAULT_ADDRESS_MIN_MOVE_MI))
            self._data[CONF_ADDRESS_MIN_INTERVAL_MIN] = int(user_input.get(CONF_ADDRESS_MIN_INTERVAL_MIN, DEFAULT_ADDRESS_MIN_INTERVAL_MIN))
            self._data[CONF_GEOCODE_PROVIDER] = str(user_input.get(CONF_GEOCODE_PROVIDER, DEFAULT_GEOCODE_PROVIDER))
            contact = user_input.get(CONF_GEOCODE_CONTACT)
            if contact:
                self._data[CONF_GEOCODE_CONTACT] = str(contact)

            fields = _sanitize_address_list(user_input.get(CONF_ADDRESS_FIELDS))
            self._data[CONF_ADDRESS_FIELDS] = fields

            return await self.async_step_inherit_attrs()

        default_fields = _sanitize_address_list(self._data.get(CONF_ADDRESS_FIELDS))

        schema = vol.Schema({
            vol.Required(CONF_PERSON_ENTITY): SELECT_PERSON,
            vol.Optional("tracker_entity", default=self._data.get(CONF_SOURCE_ENTITY, "")): SELECT_DEVICE_TRACKER,
            vol.Optional(CONF_SOURCE_ENTITY, default=self._data.get(CONF_SOURCE_ENTITY, "")): SELECT_ANY_ENTITY,
            vol.Optional(CONF_LABEL_ATTR, default=DEFAULT_LABEL_ATTR): str,
            vol.Optional(CONF_AUTO_ADDRESS, default=True): bool,
            vol.Optional(CONF_ADDRESS_MIN_MOVE_MI, default=DEFAULT_ADDRESS_MIN_MOVE_MI): SELECT_MILES_SLIDER,
            vol.Optional(CONF_ADDRESS_MIN_INTERVAL_MIN, default=DEFAULT_ADDRESS_MIN_INTERVAL_MIN): SELECT_MINUTES_SLIDER,
            vol.Optional(CONF_GEOCODE_PROVIDER, default=DEFAULT_GEOCODE_PROVIDER): selector({
                "select": {"options": [{"label": "OSM Nominatim (free)", "value": "nominatim"}], "mode": "list"}
            }),
            vol.Optional(CONF_GEOCODE_CONTACT): str,
            vol.Optional(CONF_ADDRESS_FIELDS, default=default_fields): SELECT_ADDRESS_FIELDS,
        })
        return self.async_show_form(step_id="person_label_details", data_schema=schema)

    async def async_step_inherit_attrs(self, user_input=None):
        """Pick which attributes to mirror from the source entity."""
        if user_input is not None:
            inherit = user_input.get(CONF_INHERIT_ATTRS, [])
            if not isinstance(inherit, list):
                inherit = []
            self._data[CONF_INHERIT_ATTRS] = inherit
            return await self.async_step_combine()

        attrs = []
        st = self.hass.states.get(self._data.get(CONF_SOURCE_ENTITY))
        if st and isinstance(st.attributes, dict):
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
        """Initial combine configuration (stored in data, options flow can refine later)."""
        if user_input is not None:
            combine_on = bool(user_input.get(CONF_COMBINE, False))
            self._data[CONF_COMBINE] = combine_on
            if combine_on:
                self._data[CONF_COMBINE_ENTITY] = str(user_input.get(CONF_COMBINE_ENTITY, ""))
                self._data[CONF_COMBINE_ATTR_NAME] = str(user_input.get(CONF_COMBINE_ATTR_NAME) or "combine")
                self._data[CONF_HYPHENATE_STATE] = bool(user_input.get(CONF_HYPHENATE_STATE, True))
                self._data[CONF_COMBINE_LABEL_PRECISION] = int(str(user_input.get(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION)))
                self._data[CONF_COMBINE_ATTR_PRECISION] = int(str(user_input.get(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION)))

            # If this platform supports device_class, offer it last
            if self._data[CONF_PLATFORM] in PLATFORMS_WITH_DEVICE_CLASS:
                return await self.async_step_device_class()
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

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
        """Optional final step: device_class for supported platforms."""
        platform = self._data[CONF_PLATFORM]
        if platform not in PLATFORMS_WITH_DEVICE_CLASS:
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        suggestions = DEVICE_CLASSES.get(platform, [])
        if user_input is not None:
            dc = user_input.get(CONF_DEVICE_CLASS)
            if dc:
                self._data[CONF_DEVICE_CLASS] = str(dc)
            return self.async_create_entry(title=self._data[CONF_FRIENDLY_NAME], data=self._data)

        guessed = self._data.get(CONF_DEVICE_CLASS)
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        from .options_flow import CustomEntityOptionsFlow
        return CustomEntityOptionsFlow(config_entry)
