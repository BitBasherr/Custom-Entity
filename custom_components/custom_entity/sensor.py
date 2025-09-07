"""Custom Sensor entity with Mirror mode, Person Label mode, optional Auto-address + combine conversion/suffix, and label mode."""
from __future__ import annotations

import asyncio
import re
from time import monotonic
from typing import Optional, Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity

from .const import (
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_ATTR_PRECISION,
    DEFAULT_COMBINE_PRECISION,
    # modes
    CONF_SENSOR_MODE,
    SENSOR_MODE_MIRROR,
    SENSOR_MODE_PERSON_LABEL,
    CONF_PERSON_ENTITY,
    CONF_LABEL_ATTR,
    DEFAULT_LABEL_ATTR,
    CONF_LABEL_MODE,
    # auto address + fields
    CONF_AUTO_ADDRESS,
    CONF_ADDRESS_MIN_MOVE_MI,
    CONF_ADDRESS_MIN_INTERVAL_MIN,
    CONF_GEOCODE_PROVIDER,
    CONF_GEOCODE_CONTACT,
    DEFAULT_ADDRESS_MIN_MOVE_MI,
    DEFAULT_ADDRESS_MIN_INTERVAL_MIN,
    CONF_ADDRESS_FIELDS,
    DEFAULT_ADDRESS_FIELDS,
    ADDRESS_FIELD_KEYS,
    # combine conversion
    CONF_COMBINE_UNIT_MODE,
    CONF_COMBINE_SUFFIX,
)
from .geocode import async_reverse_geocode, haversine_miles


def _to_int(x, fallback: int) -> int:
    try:
        return int(str(x))
    except Exception:
        return fallback


def _fmt_number(val, precision: int) -> str:
    try:
        f = float(val)
        return f"{f:.{precision}f}"
    except Exception:
        return str(val)


def _float_from_state(s) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        import re as _re
        m = _re.search(r"-?\d+(?:\.\d+)?", str(s))
        if m:
            try:
                return float(m.group(0))
            except Exception:
                return None
    return None


def _unit_hint(state_str: str, attrs: dict) -> Optional[str]:
    u = (attrs or {}).get("unit_of_measurement") or (attrs or {}).get("unit")
    if isinstance(u, str) and u:
        return u.lower()
    s = str(state_str).lower()
    if "sec" in s or " s" in s:
        return "s"
    if "hour" in s or " hr" in s or " h " in s:
        return "h"
    if "min" in s:
        return "min"
    return None


def _convert_to_minutes(val: float, mode: str, unit_hint: Optional[str]) -> tuple[float, bool]:
    mode = (mode or "auto").lower()
    if mode == "sec_to_min":
        return (val / 60.0, True)
    if mode == "hr_to_min":
        return (val * 60.0, True)
    if mode == "none":
        return (val, False)
    if unit_hint in ("s", "sec", "second", "seconds"):
        return (val / 60.0, True)
    if unit_hint in ("h", "hr", "hrs", "hour", "hours"):
        return (val * 60.0, True)
    return (val, False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([CustomSensorEntity(hass, entry)])


class CustomSensorEntity(SensorEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._entry = entry

        d = entry.data
        o = entry.options or {}

        self._mode = d.get(CONF_SENSOR_MODE, SENSOR_MODE_MIRROR)

        self._source_entity = d.get(CONF_SOURCE_ENTITY) or None
        self._person_entity = d.get(CONF_PERSON_ENTITY) or None
        self._label_attr = d.get(CONF_LABEL_ATTR, DEFAULT_LABEL_ATTR) or DEFAULT_LABEL_ATTR
        self._label_mode = d.get(CONF_LABEL_MODE, "line1")

        self._device_class = d.get(CONF_DEVICE_CLASS)
        self._inherit_attrs = d.get(CONF_INHERIT_ATTRS, [])

        self._attr_name = d.get(CONF_FRIENDLY_NAME, "Custom Sensor")
        self._attr_unique_id = entry.entry_id
        if self._device_class:
            self._attr_device_class = self._device_class

        # combine options
        self._combine = bool(o.get(CONF_COMBINE, d.get(CONF_COMBINE, False)))
        self._combine_entity = o.get(CONF_COMBINE_ENTITY, d.get(CONF_COMBINE_ENTITY))
        self._combine_attr_name = o.get(CONF_COMBINE_ATTR_NAME, d.get(CONF_COMBINE_ATTR_NAME, "combine"))
        self._hyphenate = bool(o.get(CONF_HYPHENATE_STATE, d.get(CONF_HYPHENATE_STATE, True)))
        self._label_prec = _to_int(o.get(CONF_COMBINE_LABEL_PRECISION, d.get(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION)), DEFAULT_COMBINE_PRECISION)
        self._attr_prec = _to_int(o.get(CONF_COMBINE_ATTR_PRECISION, d.get(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION)), DEFAULT_COMBINE_PRECISION)
        self._unit_mode = (o.get(CONF_COMBINE_UNIT_MODE, d.get(CONF_COMBINE_UNIT_MODE, "auto")) or "auto").lower()
        self._suffix = o.get(CONF_COMBINE_SUFFIX, d.get(CONF_COMBINE_SUFFIX, "")) or ""

        # auto-address controls
        self._auto_addr = bool(d.get(CONF_AUTO_ADDRESS, True))
        self._min_move_mi = float(d.get(CONF_ADDRESS_MIN_MOVE_MI, DEFAULT_ADDRESS_MIN_MOVE_MI))
        self._min_interval_min = int(d.get(CONF_ADDRESS_MIN_INTERVAL_MIN, DEFAULT_ADDRESS_MIN_INTERVAL_MIN))
        self._geocode_provider = d.get(CONF_GEOCODE_PROVIDER, "nominatim")
        self._geocode_contact = d.get(CONF_GEOCODE_CONTACT)

        self._addr_fields_list: list[str] = d.get(CONF_ADDRESS_FIELDS, DEFAULT_ADDRESS_FIELDS)
        if not isinstance(self._addr_fields_list, list):
            self._addr_fields_list = list(DEFAULT_ADDRESS_FIELDS)
        self._addr_fields_set = set([k for k in self._addr_fields_list if k in ADDRESS_FIELD_KEYS])

        self._state: Optional[str] = None
        self._extra_attrs: dict = {}
        self._address_cache: Optional[Dict[str, Any]] = None

        self._last_lookup_ts = 0.0
        self._last_lookup_lat = None
        self._last_lookup_lon = None

    async def async_added_to_hass(self):
        self._update()
        track = self.hass.helpers.event.async_track_state_change_event
        if self._source_entity:
            self.async_on_remove(track([self._source_entity], self._handle_event))
        if self._person_entity:
            self.async_on_remove(track([self._person_entity], self._handle_event))
        if self._combine and self._combine_entity:
            self.async_on_remove(track([self._combine_entity], self._handle_event))

    async def _handle_event(self, _event):
        self._update()
        self.async_write_ha_state()

    def _choose_primary_label(self, info: Dict[str, Any]) -> Optional[str]:
        mode = (self._label_mode or "line1").lower()
        line1 = info.get("line1") or info.get("display_name")
        if mode == "smart":
            return info.get("smart_place_label") or line1
        if mode == "place_name":
            return info.get("place_name") or line1
        return line1

    def _apply_address_to_attrs(self, info: Dict[str, Any]) -> Optional[str]:
        if not isinstance(info, dict):
            return None

        to_clean = set(ADDRESS_FIELD_KEYS) | {"full_address", self._label_attr}
        for k in tuple(self._extra_attrs.keys()):
            if k in to_clean:
                self._extra_attrs.pop(k, None)

        chosen = self._choose_primary_label(info)
        if chosen:
            self._extra_attrs[self._label_attr] = chosen

        for key in ADDRESS_FIELD_KEYS:
            if key in self._addr_fields_set:
                val = info.get(key) if key != "full_address" else info.get("display_name")
                if val is not None and val != "":
                    self._extra_attrs[key] = val

        return chosen

    def _update(self):
        self._extra_attrs = {}

        if self._source_entity:
            src = self.hass.states.get(self._source_entity)
            if src and isinstance(src.attributes, dict):
                reserved = {self._label_attr, *ADDRESS_FIELD_KEYS, "full_address"}
                for k in self._inherit_attrs:
                    if k in src.attributes and k not in reserved:
                        self._extra_attrs[k] = src.attributes[k]

        if self._mode == SENSOR_MODE_PERSON_LABEL:
            self._extra_attrs["entity_note"] = "Sensor-only label (not a Person)."

            label_val = None
            person = self.hass.states.get(self._person_entity) if self._person_entity else None
            if person:
                label_val = person.attributes.get(self._label_attr)

            if label_val is None and self._source_entity:
                src = self.hass.states.get(self._source_entity)
                if src:
                    label_val = src.attributes.get(self._label_attr)

            if (label_val in (None, "")) and self._auto_addr:
                lat, lon = self._best_latlon()
                if lat is not None and lon is not None:
                    asyncio.create_task(self._maybe_reverse_geocode(lat, lon))

            if self._address_cache:
                chosen = self._apply_address_to_attrs(self._address_cache)
                if chosen and not label_val:
                    label_val = chosen

            self._state = "" if label_val in (None, "") else str(label_val)
        else:
            src = self.hass.states.get(self._source_entity) if self._source_entity else None
            self._state = None if not src else src.state

            if self._address_cache:
                self._apply_address_to_attrs(self._address_cache)

        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co:
                num = _float_from_state(co.state)
                if num is not None:
                    minutes, applied = _convert_to_minutes(num, self._unit_mode, _unit_hint(co.state, co.attributes or {}))
                    if self._hyphenate:
                        txt = _fmt_number(minutes if applied else num, self._label_prec)
                        use_suffix = self._suffix
                        if not use_suffix and (applied or self._unit_mode in ("sec_to_min", "hr_to_min")):
                            use_suffix = " min"
                        base = "" if self._state in (None, "unknown", "unavailable") else str(self._state)
                        combined = f"{txt}{use_suffix}" if use_suffix else txt
                        self._state = f"{base} - {combined}" if base else combined
                    else:
                        val = minutes if applied else num
                        self._extra_attrs[self._combine_attr_name or "combine"] = _fmt_number(val, self._attr_prec)
                else:
                    if self._hyphenate:
                        base = "" if self._state in (None, "unknown", "unavailable") else str(self._state)
                        self._state = f"{base} - {co.state}" if base else str(co.state)
                    else:
                        self._extra_attrs[self._combine_attr_name or "combine"] = str(co.state)

    def _best_latlon(self):
        for ent_id in (self._person_entity, self._source_entity):
            st = self.hass.states.get(ent_id) if ent_id else None
            if not st:
                continue
            lat = st.attributes.get("latitude")
            lon = st.attributes.get("longitude")
            try:
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
            except Exception:
                continue
        return None, None

    async def _maybe_reverse_geocode(self, lat: float, lon: float):
        now = monotonic()
        if now - self._last_lookup_ts < self._min_interval_min * 60:
            return
        if self._last_lookup_lat is not None and self._last_lookup_lon is not None:
            moved = haversine_miles(self._last_lookup_lat, self._last_lookup_lon, lat, lon)
            if moved < self._min_move_mi:
                return

        info = None
        if self._geocode_provider == "nominatim":
            info = await async_reverse_geocode(self.hass, lat, lon, contact=self._geocode_contact)

        if info:
            self._address_cache = info
            self._last_lookup_ts = now
            self._last_lookup_lat = lat
            self._last_lookup_lon = lon

            chosen = self._apply_address_to_attrs(info)
            if self._mode == SENSOR_MODE_PERSON_LABEL and chosen:
                self._state = str(chosen)

            self.async_write_ha_state()

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attrs
