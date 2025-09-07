"""Custom device_tracker with mirror, presence helper, optional Combine (hyphenate),
Auto-address (structured + selectable fields), and Person picture sync (manual override + auto-detect)."""
from __future__ import annotations

import asyncio
import re
from time import monotonic
from typing import Optional, Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.zone import async_active_zone  # derive zone name from lat/lon

from .const import (
    # core
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_INHERIT_ATTRS,
    # extras
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_SENSORS,
    CONF_PRESENCE_HELPER,
    # combine
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_COMBINE_ATTR_PRECISION,
    CONF_COMBINE_LABEL_PRECISION,
    # auto-address + fields
    CONF_LABEL_ATTR,
    DEFAULT_LABEL_ATTR,
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
    # person link (manual override)
    CONF_PERSON_ENTITY,
)

from .geocode import async_reverse_geocode, haversine_miles


def _truthy(val) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in {"on", "home", "true", "yes", "1", "connected"}


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
        m = re.search(r"-?\d+(?:\.\d+)?", str(s))
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


def _convert_to_minutes_auto(val: float, unit_hint: Optional[str]) -> tuple[float, bool, str]:
    """
    Convert seconds/hours to minutes if we can infer it; return (value, converted?, eta_unit).
    eta_unit is "min" when converted or when the hint already indicated minutes; otherwise "".
    """
    if unit_hint in ("s", "sec", "second", "seconds"):
        return (val / 60.0, True, "min")
    if unit_hint in ("h", "hr", "hrs", "hour", "hours"):
        return (val * 60.0, True, "min")
    if unit_hint in ("m", "min", "mins", "minute", "minutes"):
        return (val, False, "min")
    return (val, False, "")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(TrackerEntity):
    """Mirror a source tracker’s lat/lon/attrs, presence helper override,
    Combine with optional hyphenation, reverse-geocoded structured address (selectable fields),
    and Person picture sync (manual override or auto-detect)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._entry = entry

        d = entry.data
        o = entry.options or {}

        self._attr_name = d.get(CONF_FRIENDLY_NAME, "Custom Tracker")
        self._attr_unique_id = entry.entry_id

        # source & mirrors
        self._source_entity: str = d.get(CONF_SOURCE_ENTITY, "")
        self._inherit_attrs: list[str] = d.get(CONF_INHERIT_ATTRS, [])

        # manual person override (may be None)
        self._person_entity: Optional[str] = d.get(CONF_PERSON_ENTITY)
        self._resolved_person: Optional[str] = None  # auto-detected at runtime if no manual override

        # extras
        self._battery_entity: Optional[str] = o.get(CONF_BATTERY_ENTITY)
        self._extra_map: dict[str, str] = o.get(CONF_ATTRIBUTE_SENSORS, {})

        # presence helper (can force "home")
        self._presence_helper: Optional[str] = o.get(CONF_PRESENCE_HELPER) or d.get(CONF_PRESENCE_HELPER)

        # combine
        self._combine: bool = bool(o.get(CONF_COMBINE, d.get(CONF_COMBINE, False)))
        self._combine_entity: Optional[str] = o.get(CONF_COMBINE_ENTITY, d.get(CONF_COMBINE_ENTITY))
        self._combine_attr_name: str = o.get(CONF_COMBINE_ATTR_NAME, d.get(CONF_COMBINE_ATTR_NAME, "combine"))
        self._hyphenate: bool = bool(o.get(CONF_HYPHENATE_STATE, d.get(CONF_HYPHENATE_STATE, False)))
        self._label_prec: int = _to_int(o.get(CONF_COMBINE_LABEL_PRECISION, d.get(CONF_COMBINE_LABEL_PRECISION, 1)), 1)
        self._attr_prec: int = _to_int(o.get(CONF_COMBINE_ATTR_PRECISION, d.get(CONF_COMBINE_ATTR_PRECISION, 1)), 1)

        # auto-address
        self._label_attr: str = d.get(CONF_LABEL_ATTR, DEFAULT_LABEL_ATTR) or DEFAULT_LABEL_ATTR  # usually "address"
        self._auto_addr: bool = bool(d.get(CONF_AUTO_ADDRESS, True))
        self._min_move_mi: float = float(d.get(CONF_ADDRESS_MIN_MOVE_MI, DEFAULT_ADDRESS_MIN_MOVE_MI))
        self._min_interval_min: int = int(d.get(CONF_ADDRESS_MIN_INTERVAL_MIN, DEFAULT_ADDRESS_MIN_INTERVAL_MIN))
        self._geocode_provider: str = d.get(CONF_GEOCODE_PROVIDER, "nominatim")
        self._geocode_contact: Optional[str] = d.get(CONF_GEOCODE_CONTACT)

        # which address parts to expose if present (non-sticky)
        self._addr_fields_list: list[str] = d.get(CONF_ADDRESS_FIELDS, DEFAULT_ADDRESS_FIELDS)
        if not isinstance(self._addr_fields_list, list):
            self._addr_fields_list = list(DEFAULT_ADDRESS_FIELDS)
        # keep as a set for speed, but we also know the keys universe to clean staleness
        self._addr_fields_set = set([k for k in self._addr_fields_list if k in ADDRESS_FIELD_KEYS])

        # dynamic state
        self._lat: Optional[float] = None
        self._lon: Optional[float] = None
        self._acc: Optional[float] = None
        self._address_cache: Optional[Dict[str, Any]] = None
        self._extra_attrs: dict = {}

        # geocode throttle
        self._last_lookup_ts = 0.0
        self._last_lookup_lat: Optional[float] = None
        self._last_lookup_lon: Optional[float] = None

        # picture cache
        self._attr_entity_picture: Optional[str] = None

    # ---------- TrackerEntity core ----------
    @property
    def source_type(self) -> SourceType | None:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self._lat

    @property
    def longitude(self) -> float | None:
        return self._lon

    @property
    def location_accuracy(self) -> float | None:
        return self._acc

    def _base_zone_name(self) -> Optional[str]:
        """Compute the base location label ('home', zone name, 'not_home', or None)."""
        # presence helper wins
        if self._presence_helper:
            ph = self.hass.states.get(self._presence_helper)
            if ph and _truthy(ph.state):
                return "home"

        if self._lat is None or self._lon is None:
            return None

        z = async_active_zone(self.hass, self._lat, self._lon, radius=self._acc)
        if z:
            return z.name
        return "not_home"

    @property
    def location_name(self) -> str | None:
        """
        Default: return None so HA derives zone from lat/lon.
        If hyphenate is enabled and combine is configured, build "base - value".
        If presence helper is truthy and NOT hyphenating, force "home".
        """
        if self._hyphenate and self._combine and self._combine_entity:
            base = self._base_zone_name() or "not_home"
            co = self.hass.states.get(self._combine_entity)
            if co is not None:
                num = _float_from_state(co.state)
                if num is not None:
                    minutes, converted, eta_unit = _convert_to_minutes_auto(num, _unit_hint(co.state, co.attributes or {}))
                    txt = _fmt_number(minutes if converted or eta_unit == "min" else num, self._label_prec)
                    suffix = " min" if converted or eta_unit == "min" else ""
                    return f"{base} - {txt}{suffix}"
                return f"{base} - {co.state}"
            return base

        if self._presence_helper:
            ph = self.hass.states.get(self._presence_helper)
            if ph and _truthy(ph.state):
                return "home"
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return self._extra_attrs

    # ---------- lifecycle ----------
    async def async_added_to_hass(self):
        track = async_track_state_change_event
        if self._source_entity:
            self.async_on_remove(track(self.hass, [self._source_entity], self._on_event))
        if self._battery_entity:
            self.async_on_remove(track(self.hass, [self._battery_entity], self._on_event))
        if self._presence_helper:
            self.async_on_remove(track(self.hass, [self._presence_helper], self._on_event))
        if self._combine and self._combine_entity:
            self.async_on_remove(track(self.hass, [self._combine_entity], self._on_event))
        for ent in self._extra_map.values():
            self.async_on_remove(track(self.hass, [ent], self._on_event))

        # Watch manual person or auto-detected person
        target_person = self._person_entity or self._find_linked_person()
        self._resolved_person = None if self._person_entity else target_person
        if target_person:
            self.async_on_remove(track(self.hass, [target_person], self._on_event))

        self._refresh()
        self.async_write_ha_state()

    async def _on_event(self, _):
        self._refresh()
        self.async_write_ha_state()

    # ---------- picture + person helpers ----------
    def _find_linked_person(self) -> Optional[str]:
        """Find a person.* whose 'source' equals this entity or our source tracker."""
        try:
            persons = [st for st in self.hass.states.async_all("person")]
        except Exception:
            return None
        for p in persons:
            src = p.attributes.get("source")
            if not src:
                continue
            if src == getattr(self, "entity_id", None) or src == self._source_entity:
                return p.entity_id
        return None

    def _update_picture(self):
        """Prefer Person picture; fall back to source tracker picture."""
        picture = None

        # Manual person overrides auto
        person_id = self._person_entity or self._resolved_person
        if person_id:
            st = self.hass.states.get(person_id)
            if st:
                picture = st.attributes.get("entity_picture") or st.attributes.get("entity_picture_local")

        if not picture and self._source_entity:
            st = self.hass.states.get(self._source_entity)
            if st:
                picture = st.attributes.get("entity_picture") or st.attributes.get("entity_picture_local")

        self._attr_entity_picture = picture or None

    # ---------- address attribute writer (non-sticky) ----------
    def _apply_address_to_attrs(self, info: Dict[str, Any]):
        """Write structured address with only the selected fields; remove stale keys first."""
        if not isinstance(info, dict):
            return

        # Remove any previous address-like keys we control, to avoid stickiness
        # (plus the primary address label_attr and 'full_address').
        to_clean = set(ADDRESS_FIELD_KEYS) | {"full_address", self._label_attr}
        for k in tuple(self._extra_attrs.keys()):
            if k in to_clean:
                self._extra_attrs.pop(k, None)

        # Primary address line (street + number or first display part)
        line1 = info.get("line1") or info.get("display_name")
        if line1:
            self._extra_attrs[self._label_attr] = line1

        # Optional selected fields (only add if present in fresh info)
        for key in ADDRESS_FIELD_KEYS:
            if key in self._addr_fields_set:
                val = info.get(key) if key != "full_address" else info.get("display_name")
                if val is not None and val != "":
                    self._extra_attrs[key] = val

    # ---------- update helpers ----------
    def _refresh(self):
        # Start fresh each update
        self._extra_attrs = {}

        # If no manual person, keep auto-detecting and start listening when it changes
        if not self._person_entity:
            new_person = self._find_linked_person()
            if new_person and new_person != self._resolved_person:
                self.async_on_remove(
                    async_track_state_change_event(self.hass, [new_person], self._on_event)
                )
                self._resolved_person = new_person

        # mirror from source tracker
        src = self.hass.states.get(self._source_entity) if self._source_entity else None
        if src:
            try:
                self._lat = float(src.attributes.get("latitude")) if src.attributes.get("latitude") is not None else None
                self._lon = float(src.attributes.get("longitude")) if src.attributes.get("longitude") is not None else None
            except Exception:
                self._lat = self._lon = None
            try:
                acc = src.attributes.get("gps_accuracy")
                self._acc = float(acc) if acc is not None else None
            except Exception:
                self._acc = None

            # mirrored attributes (do not step on reserved keys we control)
            reserved = {"location_zone", "eta_minutes", "eta_label", "eta_source_entity",
                        "eta_source_name", "eta_unit", "eta_raw", "eta_converted",
                        self._label_attr, *ADDRESS_FIELD_KEYS, "full_address"}
            for k in self._inherit_attrs:
                if k in src.attributes and k not in reserved:
                    self._extra_attrs[k] = src.attributes[k]

        # battery passthrough
        if self._battery_entity:
            batt = self.hass.states.get(self._battery_entity)
            if batt:
                self._extra_attrs["battery_level"] = batt.state

        # user-defined extra sensors
        for friendly, ent_id in self._extra_map.items():
            st = self.hass.states.get(ent_id)
            if st is not None:
                self._extra_attrs[friendly] = st.state

        # --- UI helper: always expose the base zone name ---
        base_zone = self._base_zone_name() or "not_home"
        self._extra_attrs["location_zone"] = base_zone  # renders as “Location zone”

        # --- Combine value (attribute when NOT hyphenating); always provide ETA helpers ---
        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co:
                # Always publish metadata about where ETA came from
                self._extra_attrs["eta_source_entity"] = self._combine_entity
                self._extra_attrs["eta_source_name"] = co.attributes.get("friendly_name") or self._combine_entity
                self._extra_attrs["eta_raw"] = co.state

                num = _float_from_state(co.state)
                if num is not None:
                    minutes, converted, eta_unit = _convert_to_minutes_auto(num, _unit_hint(co.state, co.attributes or {}))
                    # choose precision depending on hyphenation
                    use_prec = self._attr_prec if not self._hyphenate else self._label_prec
                    # numeric attribute for machine use
                    if not self._hyphenate:
                        self._extra_attrs[self._combine_attr_name or "combine"] = _fmt_number(minutes if (converted or eta_unit == "min") else num, use_prec)
                    # human label and helpers
                    val_txt = _fmt_number(minutes if (converted or eta_unit == "min") else num, use_prec)
                    self._extra_attrs["eta_minutes"] = float(val_txt)
                    self._extra_attrs["eta_label"] = f"{val_txt} min" if (converted or eta_unit == "min") else val_txt
                    self._extra_attrs["eta_converted"] = bool(converted or eta_unit == "min")
                    self._extra_attrs["eta_unit"] = "min" if (converted or eta_unit == "min") else (eta_unit or "")
                else:
                    # non-numeric source; keep metadata and plain text
                    if not self._hyphenate:
                        self._extra_attrs[self._combine_attr_name or "combine"] = str(co.state)
                    self._extra_attrs["eta_minutes"] = None
                    self._extra_attrs["eta_label"] = str(co.state)
                    self._extra_attrs["eta_converted"] = False
                    self._extra_attrs["eta_unit"] = ""

        # auto-address (write structured attributes)
        if self._auto_addr and self._lat is not None and self._lon is not None:
            asyncio.create_task(self._maybe_reverse_geocode(self._lat, self._lon))

        # persist last known structured address (non-sticky — but show if we have fresh cache)
        if self._address_cache:
            self._apply_address_to_attrs(self._address_cache)

        # update picture from person/source
        self._update_picture()

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
            self._apply_address_to_attrs(info)
            self.async_write_ha_state()
