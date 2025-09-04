"""Options flow exposing all Config Flow capabilities + extras, with nice selectors & precision fix."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector  # ✅ FIX: import selector

from .const import (
    # data keys
    CONF_PLATFORM,
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    # options keys
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
    SELECT_ANY_ENTITY,
    SELECT_BOOLEANISH,
    SELECT_PRECISION,
    SELECT_SENSOR,
    SUPPORTED_PLATFORMS,
    # bridge markers
    OPT_APPLY_DATA_UPDATE,
    DATA_MUTABLE_KEYS,
)

_LOGGER = logging.getLogger(__name__)

# Curated device classes, same as in config_flow
DEVICE_CLASSES = {
    "sensor": [
        "temperature", "humidity", "energy", "voltage",
        "power", "battery", "timestamp",
    ],
    "binary_sensor": [
        "motion", "occupancy", "opening", "smoke",
        "sound", "vibration",
    ],
}


class CustomEntityOptionsFlow(config_entries.OptionsFlow):
    """
    Options wizard with:
      • Core (platform, friendly name, source entity, device class, inherit attrs list)
      • Combine (toggle, entity, attr name, hyphenate)
      • Precision (label & attribute) via visual decimal options
      • Extras (battery, presence helper)
      • Attribute sensors add/remove

    Changing Core values applies to entry.data via an internal Options→Data bridge,
    then reloads the entry. Unique IDs remain the same.
    """

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry
        self._opts: Dict[str, Any] = dict(entry.options or {})
        self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})
        self._pending_data: Dict[str, Any] = {}

        # Back-compat: migrate old single precision to new label precision (in-memory)
        if CONF_COMBINE_PRECISION in self._opts and CONF_COMBINE_LABEL_PRECISION not in self._opts:
            self._opts[CONF_COMBINE_LABEL_PRECISION] = self._opts.get(
                CONF_COMBINE_PRECISION, DEFAULT_COMBINE_PRECISION
            )

        self._pending_attr_entity: str | None = None

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
            if choice == "precision":
                return await self.async_step_precision()
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
                "combine":     "Combine settings",
                "precision":   "Precision",
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
        class_opts: List[str] = DEVICE_CLASSES.get(platform_now or "", [])

        schema = vol.Schema({
            vol.Required(CONF_PLATFORM, default=platform_now or SUPPORTED_PLATFORMS[0]): vol.In(SUPPORTED_PLATFORMS),
            vol.Required(CONF_FRIENDLY_NAME, default=data_now.get(CONF_FRIENDLY_NAME, "")): vol.Coerce(str),
            vol.Required(CONF_SOURCE_ENTITY, default=data_now.get(CONF_SOURCE_ENTITY, "")): SELECT_ANY_ENTITY,
            vol.Optional(CONF_DEVICE_CLASS, default=data_now.get(CONF_DEVICE_CLASS, "")): (
                selector({"select": {"options": class_opts, "mode": "list"}}) if class_opts
                else selector({"text": {}})
            ),
        })
        if user_input is not None:
            for key in (CONF_PLATFORM, CONF_FRIENDLY_NAME, CONF_SOURCE_ENTITY, CONF_DEVICE_CLASS):
                if key in user_input and key in DATA_MUTABLE_KEYS:
                    val = user_input[key]
                    if key == CONF_DEVICE_CLASS:
                        val = (val or "").strip() or None
                    self._pending_data[key] = val
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
        opts = self._opts
        schema = vol.Schema({
            vol.Required(CONF_COMBINE, default=bool(opts.get(CONF_COMBINE, False))): bool,
            vol.Optional(CONF_COMBINE_ENTITY, default=opts.get(CONF_COMBINE_ENTITY, "")): SELECT_SENSOR,
            vol.Optional(CONF_COMBINE_ATTR_NAME, default=opts.get(CONF_COMBINE_ATTR_NAME, "")): selector({"text": {}}),
            vol.Optional(CONF_HYPHENATE_STATE, default=bool(opts.get(CONF_HYPHENATE_STATE, False))): bool,
        })
        if user_input is not None:
            self._opts[CONF_COMBINE] = bool(user_input.get(CONF_COMBINE, False))
            if self._opts[CONF_COMBINE]:
                self._opts[CONF_COMBINE_ENTITY] = user_input.get(CONF_COMBINE_ENTITY, "")
                self._opts[CONF_COMBINE_ATTR_NAME] = (user_input.get(CONF_COMBINE_ATTR_NAME) or "").strip()
                self._opts[CONF_HYPHENATE_STATE] = bool(user_input.get(CONF_HYPHENATE_STATE, False))
            else:
                for k in (CONF_COMBINE_ENTITY, CONF_COMBINE_ATTR_NAME, CONF_HYPHENATE_STATE):
                    self._opts.pop(k, None)
            return await self.async_step_menu()

        return self.async_show_form(step_id="combine", data_schema=schema)

    # ========= Precision (OPTIONS) =========
    async def async_step_precision(self, user_input=None):
        opts = self._opts

        def _str_default(k: str, fallback: int) -> str:
            v = opts.get(k, fallback)
            try:
                return str(int(v))
            except Exception:
                return str(fallback)

        schema = vol.Schema({
            vol.Optional(CONF_COMBINE_LABEL_PRECISION, default=_str_default(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION)): SELECT_PRECISION,
            vol.Optional(CONF_COMBINE_ATTR_PRECISION, default=_str_default(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION)): SELECT_PRECISION,
        })
        if user_input is not None:
            lbl_str = user_input.get(CONF_COMBINE_LABEL_PRECISION, str(DEFAULT_COMBINE_PRECISION))
            attr_str = user_input.get(CONF_COMBINE_ATTR_PRECISION, str(DEFAULT_COMBINE_PRECISION))
            try:
                self._opts[CONF_COMBINE_LABEL_PRECISION] = int(lbl_str)
            except Exception:
                self._opts[CONF_COMBINE_LABEL_PRECISION] = DEFAULT_COMBINE_PRECISION
            try:
                self._opts[CONF_COMBINE_ATTR_PRECISION] = int(attr_str)
            except Exception:
                self._opts[CONF_COMBINE_ATTR_PRECISION] = DEFAULT_COMBINE_PRECISION
            return await self.async_step_menu()

        return self.async_show_form(step_id="precision", data_schema=schema)

    # ========= Extras (battery/presence) (OPTIONS) =========
    async def async_step_extras(self, user_input=None):
        opts = self._opts
        schema = vol.Schema({
            vol.Optional(CONF_BATTERY_ENTITY, default=opts.get(CONF_BATTERY_ENTITY, "")): SELECT_ANY_ENTITY,
            vol.Optional(CONF_PRESENCE_HELPER, default=opts.get(CONF_PRESENCE_HELPER, "")): SELECT_BOOLEANISH,
        })
        if user_input is not None:
            batt = (user_input.get(CONF_BATTERY_ENTITY) or "").strip()
            pres = (user_input.get(CONF_PRESENCE_HELPER) or "").strip()
            if batt:
                self._opts[CONF_BATTERY_ENTITY] = batt
            else:
                self._opts.pop(CONF_BATTERY_ENTITY, None)
            if pres:
                self._opts[CONF_PRESENCE_HELPER] = pres
            else:
                self._opts.pop(CONF_PRESENCE_HELPER, None)
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
            self._pending_attr_entity = user_input["entity"]
            return await self.async_step_attr_pick_name()
        return self.async_show_form(step_id="attr_pick_entity", data_schema=vol.Schema({"entity": SELECT_ANY_ENTITY}))

    async def async_step_attr_pick_name(self, user_input=None):
        if user_input is not None:
            friendly = (user_input.get("name") or "").strip()
            if friendly:
                self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})[friendly] = self._pending_attr_entity
            self._pending_attr_entity = None
            return await self.async_step_attr_menu()
        return self.async_show_form(step_id="attr_pick_name", data_schema=vol.Schema({vol.Required("name"): selector({"text": {}})}))

    # ========= Finish =========
    async def _finish(self):
        if self._pending_data:
            clean_data = {k: self._pending_data[k] for k in self._pending_data if k in DATA_MUTABLE_KEYS}
            if clean_data:
                self._opts[OPT_APPLY_DATA_UPDATE] = {"data": clean_data}
        return self.async_create_entry(title="", data=self._opts)

    @callback
    def async_get_result(self):
        return self._opts
