"""Options flow exposing all Config Flow capabilities + extras, with nice selectors & precision fix."""
from __future__ import annotations

from typing import Any, Dict, List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    # platform & capability tables
    SUPPORTED_PLATFORMS,
    PLATFORMS_WITH_DEVICE_CLASS,
    DEVICE_CLASSES,
    # data keys (entry.data)
    CONF_PLATFORM,
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    # options keys (entry.options)
    CONF_ATTRIBUTE_SENSORS,
    CONF_BATTERY_ENTITY,
    CONF_COMBINE,
    CONF_COMBINE_ATTR_NAME,
    CONF_COMBINE_ATTR_PRECISION,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_PRECISION,  # legacy (back-compat)
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,
    DEFAULT_COMBINE_PRECISION,
    # selectors
    SELECT_ANY_ENTITY,
    SELECT_PRECISION,
    # bridge markers (applied in __init__.py update listener)
    OPT_APPLY_DATA_UPDATE,
    DATA_MUTABLE_KEYS,
)


def _guess_device_class(hass, entity_id: str) -> str | None:
    st = hass.states.get(entity_id)
    if not st:
        return None
    dc = st.attributes.get("device_class")
    if isinstance(dc, str) and dc:
        return dc
    return None


class CustomEntityOptionsFlow(config_entries.OptionsFlow):
    """
    Options wizard with:
      • Core (platform, friendly name, source entity, device class, inherit attrs list)
      • Combine (toggle, entity, attr name, hyphenate, precisions)
      • Extras (battery, presence helper)
      • Attribute sensors add/remove

    Changing Core values is staged and written back to entry.data using an Options→Data bridge,
    then the entry is reloaded (handled in __init__.py). Unique IDs remain stable.
    """

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry
        self._opts: Dict[str, Any] = dict(entry.options or {})
        self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})
        self._pending_data: Dict[str, Any] = {}
        self._pending_attr_entity: str | None = None

        # Back-compat: migrate old single precision knob to new label precision (in-memory)
        if CONF_COMBINE_PRECISION in self._opts and CONF_COMBINE_LABEL_PRECISION not in self._opts:
            self._opts[CONF_COMBINE_LABEL_PRECISION] = self._opts.get(
                CONF_COMBINE_PRECISION, DEFAULT_COMBINE_PRECISION
            )

    # ========= Menu =========
    async def async_step_init(self, user_input=None):
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        if user_input is not None:
            choice = user_input.get("choice")
            if choice == "core":
                return await self.async_step_core()
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
                "attrs":       "Mirror attributes",
                "combine":     "Combine & precision",
                "extras":      "Extras",
                "attr_sensors":"Attribute sensors",
                "save":        "✅ Save & apply",
            })
        })
        return self.async_show_form(step_id="menu", data_schema=schema)

    # ========= Core (DATA) =========
    async def async_step_core(self, user_input=None):
        data_now = dict(self.entry.data or {})
        data_now.update(self._pending_data)  # show staged values

        platform_now = data_now.get(CONF_PLATFORM)
        name_now = data_now.get(CONF_FRIENDLY_NAME, "")
        source_now = data_now.get(CONF_SOURCE_ENTITY, "")
        device_class_now = data_now.get(CONF_DEVICE_CLASS)

        has_dc = platform_now in PLATFORMS_WITH_DEVICE_CLASS

        fields: Dict[Any, Any] = {
            vol.Required(CONF_PLATFORM, default=platform_now or SUPPORTED_PLATFORMS[0]): selector({
                "select": {"options": SUPPORTED_PLATFORMS, "mode": "dropdown"}
            }),
            vol.Required(CONF_FRIENDLY_NAME, default=name_now): str,
            vol.Required(CONF_SOURCE_ENTITY, default=source_now): SELECT_ANY_ENTITY,
        }

        if has_dc:
            suggestions: List[str] = DEVICE_CLASSES.get(platform_now, [])
            # Try to guess from the current source if empty
            default_dc = device_class_now or _guess_device_class(self.hass, source_now) or ""
            if suggestions:
                fields[vol.Optional(CONF_DEVICE_CLASS, default=default_dc or suggestions[0])] = selector({
                    "select": {"options": suggestions, "mode": "list"}
                })
            else:
                fields[vol.Optional(CONF_DEVICE_CLASS, default=default_dc)] = str

        schema = vol.Schema(fields)

        if user_input is not None:
            # Coerce and stage changes
            new_platform = str(user_input.get(CONF_PLATFORM, platform_now or "sensor"))
            new_name = str(user_input.get(CONF_FRIENDLY_NAME, name_now))
            new_source = str(user_input.get(CONF_SOURCE_ENTITY, source_now))

            staged = {
                CONF_PLATFORM: new_platform,
                CONF_FRIENDLY_NAME: new_name,
                CONF_SOURCE_ENTITY: new_source,
            }

            if new_platform in PLATFORMS_WITH_DEVICE_CLASS:
                dc_val = user_input.get(CONF_DEVICE_CLASS)
                if dc_val in (None, ""):
                    dc_val = _guess_device_class(self.hass, new_source)
                if dc_val:
                    staged[CONF_DEVICE_CLASS] = str(dc_val)
                else:
                    staged.pop(CONF_DEVICE_CLASS, None)
            else:
                staged.pop(CONF_DEVICE_CLASS, None)

            for k, v in staged.items():
                if k in DATA_MUTABLE_KEYS:
                    self._pending_data[k] = v

            return await self.async_step_menu()

        return self.async_show_form(step_id="core", data_schema=schema)

    # ========= Inherit attributes list (DATA) =========
    async def async_step_attrs(self, user_input=None):
        source = self._pending_data.get(CONF_SOURCE_ENTITY, self.entry.data.get(CONF_SOURCE_ENTITY))
        attrs = []
        st = self.hass.states.get(source) if source else None
        if st and isinstance(st.attributes, dict):
            attrs = sorted([str(k) for k in st.attributes.keys()])

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

        return self.async_show_form(
            step_id="attrs",
            data_schema=schema,
            description_placeholders={"current": ", ".join(current) or "none"},
        )

    # ========= Combine (OPTIONS) =========
    async def async_step_combine(self, user_input=None):
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
                # precision selectors return strings; store as strings for HA selector schema; base class parses to int
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

    # ========= Extras (OPTIONS) =========
    async def async_step_extras(self, user_input=None):
        o = self._opts

        schema = vol.Schema({
            vol.Optional(CONF_BATTERY_ENTITY, default=o.get(CONF_BATTERY_ENTITY, "")): SELECT_ANY_ENTITY,
            vol.Optional(CONF_PRESENCE_HELPER, default=o.get(CONF_PRESENCE_HELPER, "")): SELECT_ANY_ENTITY,
        })

        if user_input is not None:
            new_opts = dict(o)
            batt = user_input.get(CONF_BATTERY_ENTITY)
            pres = user_input.get(CONF_PRESENCE_HELPER)

            new_opts[CONF_BATTERY_ENTITY] = str(batt) if batt else ""
            new_opts[CONF_PRESENCE_HELPER] = str(pres) if pres else ""

            self._opts = new_opts
            return await self.async_step_menu()

        return self.async_show_form(step_id="extras", data_schema=schema)

    # ========= Attribute sensors (OPTIONS) =========
    async def async_step_attr_menu(self, user_input=None):
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
        return self.async_show_form(
            step_id="attr_pick_entity",
            data_schema=vol.Schema({"entity": SELECT_ANY_ENTITY}),
        )

    async def async_step_attr_pick_name(self, user_input=None):
        if user_input is not None:
            friendly = (user_input.get("name") or "").strip()
            if friendly and self._pending_attr_entity:
                self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})[friendly] = self._pending_attr_entity
            self._pending_attr_entity = None
            return await self.async_step_attr_menu()

        return self.async_show_form(
            step_id="attr_pick_name",
            data_schema=vol.Schema({vol.Required("name"): selector({"text": {}})}),
        )

    # ========= Finish =========
    async def _finish(self):
        if self._pending_data:
            clean_data = {k: self._pending_data[k] for k in self._pending_data if k in DATA_MUTABLE_KEYS}
            if clean_data:
                # Hand off to __init__.py to atomically write data and reload the entry
                self._opts[OPT_APPLY_DATA_UPDATE] = {"data": clean_data}
        return self.async_create_entry(title="", data=self._opts)

    @callback
    def async_get_result(self):
        return self._opts
