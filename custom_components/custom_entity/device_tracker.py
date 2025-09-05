"""Custom device_tracker with mirror, presence helper, optional Combine (hyphenate), and Auto-address."""
from __future__ import annotations

import asyncio
from time import monotonic
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.helpers.zone import async_active_zone  # derive zone name from lat/lon

from .const import (
    # core
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_INHERIT_ATTRS,
    # extras
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_SENSORS,
    CONF_PRESENCE_HELPER,
    # combine (ALLOW hyphenating state again)
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_COMBINE_ATTR_PRECISION,
    CONF_COMBINE_LABEL_PRECISION,
    # auto-address
    CONF_LABEL_ATTR,
    DEFAULT_LABEL_ATTR,
    CONF_AUTO_ADDRESS,
    CONF_ADDRESS_MIN_MOVE_MI,
    CONF_ADDRESS_MIN_INTERVAL_MIN,
    CONF_GEOCODE_PROVIDER,
    CONF_GEOCODE_CONTACT,
    DEFAULT_ADDRESS_MIN_MOVE_MI,
    DEFAULT_ADDRESS_MIN_INTERVAL_MIN,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(TrackerEntity):
    """Mirror a source tracker’s lat/lon/attrs, presence helper override, Combine with optional hyphenation, and reverse-geocoded address."""

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

        # dynamic state
        self._lat: Optional[float] = None
        self._lon: Optional[float] = None
        self._acc: Optional[float] = None
        self._address_cache: Optional[str] = None
        self._extra_attrs: dict = {}

        # geocode throttle
        self._last_lookup_ts = 0.0
        self._last_lookup_lat: Optional[float] = None
        self._last_lookup_lon: Optional[float] = None

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

        z = async_active_zone(self.hass, self._lat, self._lon, self._acc)
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
        # Hyphenated state (requested): build base + " - " + combine_value
        if self._hyphenate and self._combine and self._combine_entity:
            base = self._base_zone_name() or "not_home"
            co = self.hass.states.get(self._combine_entity)
            if co is not None:
                combined = _fmt_number(co.state, self._label_prec)
                return f"{base} - {combined}"
            return base  # no combine available yet

        # Non-hyphenated: let HA compute the zone unless presence helper forces "home"
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

        self._refresh()
        self.async_write_ha_state()

    async def _on_event(self, _):
        self._refresh()
        self.async_write_ha_state()

    # ---------- update helpers ----------
    def _refresh(self):
        self._extra_attrs = {}

        # mirror from source tracker
        src = self.hass.states.get(self._source_entity) if self._source_entity else None
        if src:
            # lat/lon/accuracy
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

            # mirrored attributes
            for k in self._inherit_attrs:
                if k in src.attributes:
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

        # combine as attribute when NOT hyphenating
        if self._combine and self._combine_entity and not self._hyphenate:
            co = self.hass.states.get(self._combine_entity)
            if co:
                self._extra_attrs[self._combine_attr_name or "combine"] = _fmt_number(co.state, self._attr_prec)

        # auto-address (write to attribute)
        if self._auto_addr and self._lat is not None and self._lon is not None:
            asyncio.create_task(self._maybe_reverse_geocode(self._lat, self._lon))

        # persist last known address
        if self._address_cache:
            self._extra_attrs[self._label_attr] = self._address_cache

    async def _maybe_reverse_geocode(self, lat: float, lon: float):
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
            self._address_cache = str(address)
            self._last_lookup_ts = now
            self._last_lookup_lat = lat
            self._last_lookup_lon = lon
            self._extra_attrs[self._label_attr] = self._address_cache
            self.async_write_ha_state()
