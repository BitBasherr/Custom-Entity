"""Custom Sensor entity with Mirror mode, Person Label mode, optional Auto-address,
and explicit Combine unit override (auto / sec_to_min / hr_to_min / none)."""
from __future__ import annotations

import asyncio
from time import monotonic
from typing import Optional, Tuple

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
    # auto address
    CONF_AUTO_ADDRESS,
    CONF_ADDRESS_MIN_MOVE_MI,
    CONF_ADDRESS_MIN_INTERVAL_MIN,
    CONF_GEOCODE_PROVIDER,
    CONF_GEOCODE_CONTACT,
    DEFAULT_ADDRESS_MIN_MOVE_MI,
    DEFAULT_ADDRESS_MIN_INTERVAL_MIN,
)
from .geocode import async_reverse_geocode, haversine_miles


# ---------------- Local keys for the new zero-ambiguity override -------------
# (Kept local so you don't have to modify const.py immediately.)
_COMBINE_UNIT_MODE_KEY = "combine_unit_mode"   # "auto" | "sec_to_min" | "hr_to_min" | "none"
_COMBINE_SUFFIX_KEY    = "combine_suffix"      # e.g. " min"

_MODE_AUTO     = "auto"
_MODE_S_TO_MIN = "sec_to_min"
_MODE_H_TO_MIN = "hr_to_min"
_MODE_NONE     = "none"


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


def _normalize_unit(u: Optional[str]) -> str:
    u = (u or "").strip().lower()
    if u in ("m", "min", "minute", "minutes"):
        return "min"
    if u in ("s", "sec", "secs", "second", "seconds"):
        return "s"
    if u in ("h", "hr", "hrs", "hour", "hours"):
        return "h"
    return u  # unknown/empty → ""


def _looks_like_seconds_fallback(ent_id: str, device_class: Optional[str]) -> bool:
    # Very conservative: only when name hints secs AND device_class == duration
    if (device_class or "").lower() != "duration":
        return False
    low = ent_id.lower()
    return ("sec" in low) or ("second" in low)


def _convert_value(
    value_str: str,
    uom_raw: Optional[str],
    ent_id: str,
    device_class: Optional[str],
    mode: str,
) -> Tuple[Optional[float], Optional[str], bool]:
    """
    Returns (numeric_value, target_unit, converted_flag).
    - target_unit is normalized: "min" / "s" / "h" / "" / None
    - converted_flag is True if we applied a unit conversion explicitly.
    """
    try:
        val = float(value_str)
    except Exception:
        return None, _normalize_unit(uom_raw), False

    uom = _normalize_unit(uom_raw)

    # Explicit override modes first (no ambiguity).
    if mode == _MODE_S_TO_MIN:
        return val / 60.0, "min", True
    if mode == _MODE_H_TO_MIN:
        return val * 60.0, "min", True
    if mode == _MODE_NONE:
        return val, uom or None, False

    # AUTO: infer from units; avoid guessing when unit is unknown.
    if uom == "min":
        return val, "min", False
    if uom == "s":
        return val / 60.0, "min", True
    if uom == "h":
        return val * 60.0, "min", True

    # No unit: conservative fallback for secs → min only if it really looks like seconds
    if not uom and _looks_like_seconds_fallback(ent_id, device_class):
        return val / 60.0, "min", True

    # Unknown units: leave as-is
    return val, uom or None, False


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

        self._device_class = d.get(CONF_DEVICE_CLASS)
        self._inherit_attrs = d.get(CONF_INHERIT_ATTRS, [])

        self._attr_name = d.get(CONF_FRIENDLY_NAME, "Custom Sensor")
        self._attr_unique_id = entry.entry_id
        if self._device_class:
            self._attr_device_class = self._device_class

        # combine options (from options and/or data for back-compat)
        self._combine = bool(o.get(CONF_COMBINE, d.get(CONF_COMBINE, False)))
        self._combine_entity = o.get(CONF_COMBINE_ENTITY, d.get(CONF_COMBINE_ENTITY))
        self._combine_attr_name = o.get(CONF_COMBINE_ATTR_NAME, d.get(CONF_COMBINE_ATTR_NAME, "combine"))
        self._hyphenate = bool(o.get(CONF_HYPHENATE_STATE, d.get(CONF_HYPHENATE_STATE, True)))
        self._label_prec = _to_int(o.get(CONF_COMBINE_LABEL_PRECISION, d.get(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION)), DEFAULT_COMBINE_PRECISION)
        self._attr_prec = _to_int(o.get(CONF_COMBINE_ATTR_PRECISION, d.get(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION)), DEFAULT_COMBINE_PRECISION)

        # NEW: zero-ambiguity override + label suffix (read from options, fallback to data)
        self._combine_unit_mode: str = (o.get(_COMBINE_UNIT_MODE_KEY) or d.get(_COMBINE_UNIT_MODE_KEY) or _MODE_AUTO).strip().lower()
        if self._combine_unit_mode not in (_MODE_AUTO, _MODE_S_TO_MIN, _MODE_H_TO_MIN, _MODE_NONE):
            self._combine_unit_mode = _MODE_AUTO
        self._combine_suffix: str = (o.get(_COMBINE_SUFFIX_KEY) or d.get(_COMBINE_SUFFIX_KEY) or "").strip()

        # auto-address controls
        self._auto_addr = bool(d.get(CONF_AUTO_ADDRESS, True))
        self._min_move_mi = float(d.get(CONF_ADDRESS_MIN_MOVE_MI, DEFAULT_ADDRESS_MIN_MOVE_MI))
        self._min_interval_min = int(d.get(CONF_ADDRESS_MIN_INTERVAL_MIN, DEFAULT_ADDRESS_MIN_INTERVAL_MIN))
        self._geocode_provider = d.get(CONF_GEOCODE_PROVIDER, "nominatim")
        self._geocode_contact = d.get(CONF_GEOCODE_CONTACT)  # optional

        self._state: Optional[str] = None
        self._extra_attrs: dict = {}

        # throttling state
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

    def _update(self):
        self._extra_attrs = {}

        # Mirror chosen attributes from source (both modes)
        if self._source_entity:
            src = self.hass.states.get(self._source_entity)
            if src and isinstance(src.attributes, dict):
                for k in self._inherit_attrs:
                    if k in src.attributes:
                        self._extra_attrs[k] = src.attributes[k]

        # Determine base state
        if self._mode == SENSOR_MODE_PERSON_LABEL:
            # Make it clear this is *not* a Person entity
            self._extra_attrs["entity_note"] = "Sensor-only label (not a Person)."

            label_val = None
            person = self.hass.states.get(self._person_entity) if self._person_entity else None
            if person:
                label_val = person.attributes.get(self._label_attr)

            if label_val is None and self._source_entity:
                src = self.hass.states.get(self._source_entity)
                if src:
                    label_val = src.attributes.get(self._label_attr)

            # If missing and auto-address is enabled, try reverse-geocoding from lat/lon
            if (label_val in (None, "")) and self._auto_addr:
                lat, lon = self._best_latlon()
                if lat is not None and lon is not None:
                    asyncio.create_task(self._maybe_reverse_geocode(lat, lon))

            self._state = "" if label_val in (None, "") else str(label_val)
        else:
            # Mirror mode — copy the source state verbatim
            src = self.hass.states.get(self._source_entity) if self._source_entity else None
            self._state = None if not src else src.state

        # Combine behavior (hyphenate vs attribute) with unit override
        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co:
                val, target_uom, _converted = _convert_value(
                    value_str=str(co.state),
                    uom_raw=co.attributes.get("unit_of_measurement"),
                    ent_id=co.entity_id,
                    device_class=co.attributes.get("device_class"),
                    mode=self._combine_unit_mode,
                )
                if val is not None:
                    if self._hyphenate:
                        disp = f"{val:.{self._label_prec}f}"
                        # If no custom suffix provided but we're in minutes, append " min" to be explicit.
                        suf = self._combine_suffix if self._combine_suffix else (" min" if target_uom == "min" else "")
                        base = "" if self._state in (None, "unknown", "unavailable") else str(self._state)
                        self._state = f"{base} - {disp}{suf}" if base else f"{disp}{suf}"
                    else:
                        key = self._combine_attr_name or "combine"
                        self._extra_attrs[key] = f"{val:.{self._attr_prec}f}"
                        if target_uom:
                            self._extra_attrs[f"{key}_uom"] = target_uom

    def _best_latlon(self):
        """Prefer person lat/lon, fallback to tracker."""
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
        """Throttle and reverse-geocode if moved enough and interval elapsed."""
        now = monotonic()
        # interval check
        if now - self._last_lookup_ts < self._min_interval_min * 60:
            return
        # distance check
        if self._last_lookup_lat is not None and self._last_lookup_lon is not None:
            moved = haversine_miles(self._last_lookup_lat, self._last_lookup_lon, lat, lon)
            if moved < self._min_move_mi:
                return

        address = None
        if self._geocode_provider == "nominatim":
            address = await async_reverse_geocode(self.hass, lat, lon, contact=self._geocode_contact)

        if address:
            # Set the label in state when we're in person-label mode; otherwise expose as attribute
            if self._mode == SENSOR_MODE_PERSON_LABEL:
                self._state = str(address)
            else:
                self._extra_attrs[self._label_attr] = str(address)
            # update throttle state
            self._last_lookup_ts = now
            self._last_lookup_lat = lat
            self._last_lookup_lon = lon
            self.async_write_ha_state()

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attrs
