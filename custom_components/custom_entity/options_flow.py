"""Options flow (core, attrs, combine, extras, reverse geocoder; applies data changes)."""
from __future__ import annotations

from typing import Any, Dict, List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    # platform & capability
    SUPPORTED_PLATFORMS,
    PLATFORMS_WITH_DEVICE_CLASS,
    DEVICE_CLASSES,
    # data keys (entry.data)
    CONF_PLATFORM,
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_PERSON_ENTITY,
    # sensor/person-label bits
    CONF_SENSOR_MODE,
    SENSOR_MODE_MIRROR,
    SENSOR_MODE_PERSON_LABEL,
    CONF_LABEL_ATTR,
    DEFAULT_LABEL_ATTR,
    # reverse geocode (data)
    CONF_AUTO_ADDRESS,
    CONF_ADDRESS_MIN_MOVE_MI,
    CONF_ADDRESS_MIN_INTERVAL_MIN,
    CONF_GEOCODE_PROVIDER,
    CONF_GEOCODE_CONTACT,
    DEFAULT_ADDRESS_MIN_MOVE_MI,
    DEFAULT_ADDRESS_MIN_INTERVAL_MIN,
    DEFAULT_GEOCODE_PROVIDER,
    # address fields (data)
    CONF_ADDRESS_FIELDS,
    SELECT_ADDRESS_FIELDS,
    ADDRESS_FIELD_OPTIONS,
    # options (entry.options)
    CONF_ATTRIBUTE_SENSORS,
    CONF_BATTERY_ENTITY,
    CONF_COMBINE,
    CONF_COMBINE_ATTR_NAME,
    CONF_COMBINE_ATTR_PRECISION,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_PRECISION,
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,
    DEFAULT_COMBINE_PRECISION,
    # selectors
    SELECT_ANY_ENTITY,
    SELECT_PERSON,
    SELECT_DEVICE_TRACKER,
    SELECT_PRECISION,
    SELECT_MILES_SLIDER,
    SELECT_MINUTES_SLIDER,
    # bridge markers
    OPT_APPLY_DATA_UPDATE,
    DATA_MUTABLE_KEYS,
)

# Keep this internal (requested: no change to consts)
K_SMART_APPEND_CITY = "smart_label_append_city"

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
        cleaned = list(_ALLOWED_ADDR_VALUES)  # default to ALL
    return cleaned


class CustomEntityOptionsFlow(config_entries.OptionsFlow):
    """Options flow to edit data/options and push selective data updates."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry
        self._opts: Dict[str, Any] = dict(entry.options or {})
        self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})
        self._pending_data: Dict[str, Any] = {}
        self._pending_attr_entity: str | None = None

        # Back-compat: migrate old single precision knob to new label precision (in-memory only)
        if CONF_COMBINE_PRECISION in self._opts and CONF_COMBINE_LABEL_PRECISION not in self._opts:
            self._opts[CONF_COMBINE_LABEL_PRECISION] = self._opts.get(CONF_COMBINE_PRECISION, DEFAULT_COMBINE_PRECISION)

    async def async_step_init(self, user_input=None):
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        if user_input is not None:
            choice = user_input.get("choice")
            if choice == "core":
                return await self.async_step_core()
            if choice == "geocoder":
                return await self.async_step_geocoder()
            if choice == "attrs":
                return await self.async_step_attrs()
            if choice == "combine":
                return await self.async_step_combine()
            if choice == "extras":
                return await self.async_step_extras()
            if choice == "attr_sensors":
                return await self.async_step_attr_menu()
            if choice == "save":
                return await self._finish()

        schema = vol.Schema({
            vol.Required("choice"): vol.In({
                "core":        "Core settings",
                "geocoder":    "Reverse geocoder",
                "attrs":       "Mirror attributes",
                "combine":     "Combine & precision",
                "extras":      "Extras",
                "attr_sensors":"Attribute sensors",
                "save":        "✅ Save & apply",
            })
        })
        return self.async_show_form(step_id="menu", data_schema=schema)

    async def async_step_core(self, user_input=None):
        """Core: platform/name/source (+sensor mode/person)."""
        data_now = dict(self.entry.data or {})
        data_now.update(self._pending_data)  # staged values take precedence

        platform_now = data_now.get(CONF_PLATFORM)
        name_now = data_now.get(CONF_FRIENDLY_NAME, "")
        source_now = data_now.get(CONF_SOURCE_ENTITY, "")
        device_class_now = data_now.get(CONF_DEVICE_CLASS)

        # Sensor-only fields
        mode_now = data_now.get(CONF_SENSOR_MODE, SENSOR_MODE_MIRROR)
        person_now = data_now.get(CONF_PERSON_ENTITY, "")
        label_attr_now = data_now.get(CONF_LABEL_ATTR, DEFAULT_LABEL_ATTR)

        has_dc = platform_now in PLATFORMS_WITH_DEVICE_CLASS

        fields: Dict[Any, Any] = {
            vol.Required(CONF_PLATFORM, default=platform_now or SUPPORTED_PLATFORMS[0]): selector({
                "select": {"options": SUPPORTED_PLATFORMS, "mode": "dropdown"}
            }),
            vol.Required(CONF_FRIENDLY_NAME, default=name_now): str,
            vol.Optional(CONF_SOURCE_ENTITY, default=source_now): SELECT_ANY_ENTITY,
        }

        if has_dc:
            suggestions: List[str] = DEVICE_CLASSES.get(platform_now, [])
            default_dc = device_class_now or _guess_device_class(self.hass, source_now) or ""
            if suggestions:
                fields[vol.Optional(CONF_DEVICE_CLASS, default=default_dc or suggestions[0])] = selector({
                    "select": {"options": suggestions, "mode": "list"}
                })
            else:
                fields[vol.Optional(CONF_DEVICE_CLASS, default=default_dc)] = str

        # Sensor-only bits (mode + person label details — person selection lives here)
        if (platform_now or "") == "sensor":
            fields[vol.Optional(CONF_SENSOR_MODE, default=mode_now)] = selector({
                "select": {"options": SENSOR_MODE_OPTIONS, "mode": "list"}
            })
            if mode_now == SENSOR_MODE_PERSON_LABEL:
                fields[vol.Required(CONF_PERSON_ENTITY, default=person_now)] = SELECT_PERSON
                fields[vol.Optional(CONF_LABEL_ATTR, default=label_attr_now)] = str

        schema = vol.Schema(fields)

        if user_input is not None:
            staged = {
                CONF_PLATFORM: str(user_input.get(CONF_PLATFORM, platform_now or "sensor")),
                CONF_FRIENDLY_NAME: str(user_input.get(CONF_FRIENDLY_NAME, name_now)),
            }
            if CONF_SOURCE_ENTITY in user_input:
                staged[CONF_SOURCE_ENTITY] = str(user_input.get(CONF_SOURCE_ENTITY) or "")

            # device_class handling
            if staged[CONF_PLATFORM] in PLATFORMS_WITH_DEVICE_CLASS:
                dc_val = user_input.get(CONF_DEVICE_CLASS)
                if dc_val in (None, ""):
                    dc_val = _guess_device_class(self.hass, staged.get(CONF_SOURCE_ENTITY, source_now))
                if dc_val:
                    staged[CONF_DEVICE_CLASS] = str(dc_val)
                else:
                    staged.pop(CONF_DEVICE_CLASS, None)
            else:
                staged.pop(CONF_DEVICE_CLASS, None)

            # Sensor-only staging
            if staged[CONF_PLATFORM] == "sensor":
                mode_val = user_input.get(CONF_SENSOR_MODE, mode_now)
                staged[CONF_SENSOR_MODE] = mode_val
                if mode_val == SENSOR_MODE_PERSON_LABEL:
                    if user_input.get(CONF_PERSON_ENTITY) or person_now:
                        staged[CONF_PERSON_ENTITY] = str(user_input.get(CONF_PERSON_ENTITY, person_now))
                    if CONF_LABEL_ATTR in user_input:
                        staged[CONF_LABEL_ATTR] = str(user_input.get(CONF_LABEL_ATTR) or DEFAULT_LABEL_ATTR)

            # Stage only allowed keys into pending data
            for k, v in staged.items():
                if k in DATA_MUTABLE_KEYS:
                    self._pending_data[k] = v

            return await self.async_step_menu()

        return self.async_show_form(step_id="core", data_schema=schema)

    async def async_step_geocoder(self, user_input=None):
        """Reverse Geocoder page: auto-address + throttles + provider + fields + city append toggle."""
        data_now = dict(self.entry.data or {})
        data_now.update(self._pending_data)

        auto_now = bool(data_now.get(CONF_AUTO_ADDRESS, True))
        min_move_now = float(data_now.get(CONF_ADDRESS_MIN_MOVE_MI, DEFAULT_ADDRESS_MIN_MOVE_MI))
        min_interval_now = int(data_now.get(CONF_ADDRESS_MIN_INTERVAL_MIN, DEFAULT_ADDRESS_MIN_INTERVAL_MIN))
        provider_now = data_now.get(CONF_GEOCODE_PROVIDER, DEFAULT_GEOCODE_PROVIDER)
        contact_now = data_now.get(CONF_GEOCODE_CONTACT, "")
        addr_fields_now = _sanitize_address_list(data_now.get(CONF_ADDRESS_FIELDS))

        append_city_now = bool(self._opts.get(K_SMART_APPEND_CITY, self.entry.data.get(K_SMART_APPEND_CITY, False)))

        schema = vol.Schema({
            vol.Optional(CONF_AUTO_ADDRESS, default=auto_now): bool,
            vol.Optional(CONF_ADDRESS_MIN_MOVE_MI, default=min_move_now): SELECT_MILES_SLIDER,
            vol.Optional(CONF_ADDRESS_MIN_INTERVAL_MIN, default=min_interval_now): SELECT_MINUTES_SLIDER,
            vol.Optional(CONF_GEOCODE_PROVIDER, default=provider_now): selector({
                "select": {"options": [{"label": "OSM Nominatim (free)", "value": "nominatim"}], "mode": "list"}
            }),
            vol.Optional(CONF_GEOCODE_CONTACT, default=contact_now): str,
            vol.Optional(CONF_ADDRESS_FIELDS, default=addr_fields_now): SELECT_ADDRESS_FIELDS,
            vol.Optional(K_SMART_APPEND_CITY, default=append_city_now): bool,
        })

        if user_input is not None:
            # Stage data (bridge-able keys)
            staged = {
                CONF_AUTO_ADDRESS: bool(user_input.get(CONF_AUTO_ADDRESS, auto_now)),
                CONF_ADDRESS_MIN_MOVE_MI: float(user_input.get(CONF_ADDRESS_MIN_MOVE_MI, min_move_now)),
                CONF_ADDRESS_MIN_INTERVAL_MIN: int(user_input.get(CONF_ADDRESS_MIN_INTERVAL_MIN, min_interval_now)),
                CONF_GEOCODE_PROVIDER: str(user_input.get(CONF_GEOCODE_PROVIDER, DEFAULT_GEOCODE_PROVIDER)),
            }
            if user_input.get(CONF_GEOCODE_CONTACT) is not None:
                staged[CONF_GEOCODE_CONTACT] = str(user_input.get(CONF_GEOCODE_CONTACT) or "")
            if user_input.get(CONF_ADDRESS_FIELDS) is not None:
                staged[CONF_ADDRESS_FIELDS] = _sanitize_address_list(user_input.get(CONF_ADDRESS_FIELDS))
            else:
                staged[CONF_ADDRESS_FIELDS] = _sanitize_address_list(addr_fields_now)

            for k, v in staged.items():
                if k in DATA_MUTABLE_KEYS:
                    self._pending_data[k] = v

            # Store the city-append toggle directly in options (no const change)
            self._opts[K_SMART_APPEND_CITY] = bool(user_input.get(K_SMART_APPEND_CITY, append_city_now))

            return await self.async_step_menu()

        return self.async_show_form(step_id="geocoder", data_schema=schema)

    async def async_step_attrs(self, user_input=None):
        """Mirror attributes selection."""
        source = self._pending_data.get(CONF_SOURCE_ENTITY, self.entry.data.get(CONF_SOURCE_ENTITY))
        attrs = []
        st = self.hass.states.get(source) if source else None
        if st and isinstance(st.attributes, dict):
            attrs = sorted([str(k) for k in st.attributes.keys())]

        current = self.entry.data.get(CONF_INHERIT_ATTRS, [])
        if isinstance(current, bool):
            current = []

        schema = vol.Schema({
            vol.Optional(CONF_INHERIT_ATTRS, default=current): selector({
                "select": {"options": attrs, "multiple": True, "mode": "list"}
            })
        })

        if user_input is not None:
            self._pending_data[CONF_INHERIT_ATTRS] = user_input.get(CONF_INHERIT_ATTRS, [])
            return await self.async_step_menu()

        return self.async_show_form(step_id="attrs", data_schema=schema)

    async def async_step_combine(self, user_input=None):
        """Combine (options)."""
        o = self._opts
        d = self.entry.data or {}

        defaults = {
            CONF_COMBINE: bool(o.get(CONF_COMBINE, d.get(CONF_COMBINE, False))),
            CONF_COMBINE_ENTITY: o.get(CONF_COMBINE_ENTITY, d.get(CONF_COMBINE_ENTITY, "")),
            CONF_COMBINE_ATTR_NAME: o.get(CONF_COMBINE_ATTR_NAME, d.get(CONF_COMBINE_ATTR_NAME, "combine")),
            CONF_HYPHENATE_STATE: bool(o.get(CONF_HYPHENATE_STATE, d.get(CONF_HYPHENATE_STATE, True))),
            CONF_COMBINE_LABEL_PRECISION: str(o.get(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION)),
            CONF_COMBINE_ATTR_PRECISION: str(o.get(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION)),
        }

        schema = vol.Schema({
            vol.Required(CONF_COMBINE, default=defaults[CONF_COMBINE]): bool,
            vol.Optional(CONF_COMBINE_ENTITY, default=defaults[CONF_COMBINE_ENTITY]): SELECT_ANY_ENTITY,
            vol.Optional(CONF_COMBINE_ATTR_NAME, default=defaults[CONF_COMBINE_ATTR_NAME]): str,
            vol.Optional(CONF_HYPHENATE_STATE, default=defaults[CONF_HYPHENATE_STATE]): bool,
            vol.Optional(CONF_COMBINE_LABEL_PRECISION, default=defaults[CONF_COMBINE_LABEL_PRECISION]): SELECT_PRECISION,
            vol.Optional(CONF_COMBINE_ATTR_PRECISION, default=defaults[CONF_COMBINE_ATTR_PRECISION]): SELECT_PRECISION,
        })

        if user_input is not None:
            combine_on = bool(user_input.get(CONF_COMBINE, False))
            new_opts = dict(o)
            if combine_on:
                new_opts[CONF_COMBINE] = True
                new_opts[CONF_COMBINE_ENTITY] = str(user_input.get(CONF_COMBINE_ENTITY, defaults[CONF_COMBINE_ENTITY]))
                new_opts[CONF_COMBINE_ATTR_NAME] = str(user_input.get(CONF_COMBINE_ATTR_NAME, "combine") or "combine")
                new_opts[CONF_HYPHENATE_STATE] = bool(user_input.get(CONF_HYPHENATE_STATE, defaults[CONF_HYPHENATE_STATE]))
                new_opts[CONF_COMBINE_LABEL_PRECISION] = str(user_input.get(CONF_COMBINE_LABEL_PRECISION, defaults[CONF_COMBINE_LABEL_PRECISION]))
                new_opts[CONF_COMBINE_ATTR_PRECISION] = str(user_input.get(CONF_COMBINE_ATTR_PRECISION, defaults[CONF_COMBINE_ATTR_PRECISION]))
            else:
                new_opts[CONF_COMBINE] = False
                for k in (
                    CONF_COMBINE_ENTITY,
                    CONF_COMBINE_ATTR_NAME,
                    CONF_HYPHENATE_STATE,
                    CONF_COMBINE_LABEL_PRECISION,
                    CONF_COMBINE_ATTR_PRECISION,
                ):
                    new_opts.pop(k, None)

            self._opts = new_opts
            return await self.async_step_menu()

        return self.async_show_form(step_id="combine", data_schema=schema)

    async def async_step_extras(self, user_input=None):
        """Battery + presence helper."""
        o = self._opts
        schema = vol.Schema({
            vol.Optional(CONF_BATTERY_ENTITY, default=o.get(CONF_BATTERY_ENTITY, "")): SELECT_ANY_ENTITY,
            vol.Optional(CONF_PRESENCE_HELPER, default=o.get(CONF_PRESENCE_HELPER, "")): SELECT_ANY_ENTITY,
        })

        if user_input is not None:
            new_opts = dict(o)
            batt = user_input.get(CONF_BATTERY_ENTITY)
            pres = user_input.get(CONF_PRESENCE_HELPER)

            if batt:
                new_opts[CONF_BATTERY_ENTITY] = str(batt)
            else:
                new_opts.pop(CONF_BATTERY_ENTITY, None)

            if pres:
                new_opts[CONF_PRESENCE_HELPER] = str(pres)
            else:
                new_opts.pop(CONF_PRESENCE_HELPER, None)

            self._opts = new_opts
            return await self.async_step_menu()

        return self.async_show_form(step_id="extras", data_schema=schema)

    async def async_step_attr_menu(self, user_input=None):
        """Add/remove dynamic attribute sensors (friendly -> entity_id mapping)."""
        if user_input is not None:
            action = user_input.get("choice")
            if not action or action == "done":
                return await self.async_step_menu()
            if action == "add":
                return await self.async_step_attr_pick_entity()
            if action.startswith("del__"):
                friendly = action[5:]
                self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {}).pop(friendly, None)

        buttons = {
            "done": "⬅ Back",
            "add": "➕ Add attribute",
            **{f"del__{k}": f"🗑 Remove “{k}”" for k in sorted(self._opts.get(CONF_ATTRIBUTE_SENSORS, {}))}
        }
        schema = vol.Schema({vol.Required("choice"): vol.In(buttons)})
        current = ", ".join(self._opts.get(CONF_ATTRIBUTE_SENSORS, {}).keys()) or "none"
        return self.async_show_form(
            step_id="attr_menu",
            data_schema=schema,
            description_placeholders={"current": current},
        )

    async def async_step_attr_pick_entity(self, user_input=None):
        if user_input is not None:
            self._pending_attr_entity = str(user_input["entity"])
            return await self.async_step_attr_pick_name()
        return self.async_show_form(step_id="attr_pick_entity", data_schema=vol.Schema({"entity": SELECT_ANY_ENTITY}))

    async def async_step_attr_pick_name(self, user_input=None):
        if user_input is not None:
            friendly = (user_input.get("name") or "").strip()
            if friendly and self._pending_attr_entity:
                self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})[friendly] = self._pending_attr_entity
            self._pending_attr_entity = None
            return await self.async_step_attr_menu()
        return self.async_show_form(step_id="attr_pick_name", data_schema=vol.Schema({vol.Required("name"): selector({"text": {}})}))

    async def _finish(self):
        """Write any pending data mutations (Options → Data bridge) and save options."""
        if self._pending_data:
            if CONF_ADDRESS_FIELDS in self._pending_data:
                self._pending_data[CONF_ADDRESS_FIELDS] = _sanitize_address_list(self._pending_data.get(CONF_ADDRESS_FIELDS))
            clean_data = {k: self._pending_data[k] for k in self._pending_data if k in DATA_MUTABLE_KEYS}
            if clean_data:
                self._opts[OPT_APPLY_DATA_UPDATE] = {"data": clean_data}
        return self.async_create_entry(title="", data=self._opts)

    @callback
    def async_get_result(self):
        return self._opts
