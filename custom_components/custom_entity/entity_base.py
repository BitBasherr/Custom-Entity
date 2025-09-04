"""Shared logic for all Custom Entity types."""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_SENSORS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    # precision keys
    CONF_COMBINE_PRECISION,            # legacy single knob
    CONF_COMBINE_LABEL_PRECISION,      # new UI
    CONF_COMBINE_ATTR_PRECISION,       # new UI
    DEFAULT_COMBINE_PRECISION,
)


class CustomBaseEntity:
    """
    Mixin base for all Custom-Entity platform classes.

    NOTE: Subclasses must also inherit a Home Assistant Entity class
    (e.g. SensorEntity, BinarySensorEntity, etc.) so that async_write_ha_state()
    and _attr_* fields are recognized.
    """

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self._entry = entry  # used in listeners & options lookups

        data: Dict[str, Any] = entry.data or {}
        opts: Dict[str, Any] = entry.options or {}

        # Core / data
        self._source_entity: str = data[CONF_SOURCE_ENTITY]
        self._device_class: Optional[str] = data.get(CONF_DEVICE_CLASS)
        self._inherit_attrs: list[str] = data.get(CONF_INHERIT_ATTRS, []) or []

        # Options
        self._battery_entity: Optional[str] = opts.get(CONF_BATTERY_ENTITY) or None
        self._extra_map: Dict[str, str] = opts.get(CONF_ATTRIBUTE_SENSORS, {}) or {}

        # Combine behavior (stored primarily in entry.data for back-compat)
        self._combine: bool = bool(data.get(CONF_COMBINE, False))
        self._combine_entity: Optional[str] = data.get(CONF_COMBINE_ENTITY) or opts.get(CONF_COMBINE_ENTITY)
        self._combine_attr_name: Optional[str] = data.get(CONF_COMBINE_ATTR_NAME) or opts.get(CONF_COMBINE_ATTR_NAME)
        self._hyphenate: bool = bool(
            (self._entry.options or {}).get(CONF_HYPHENATE_STATE, data.get(CONF_HYPHENATE_STATE, False))
        )

        # Friendly name / identity
        self._attr_name = data.get(CONF_FRIENDLY_NAME, "Custom Entity")
        self._attr_unique_id = entry.entry_id
        if self._device_class and hasattr(self, "_attr_device_class"):
            # Only set if the subclass supports device_class
            self._attr_device_class = self._device_class  # type: ignore[attr-defined]

        # Internal state cache
        self._state: Optional[str] = None
        self._extra_attrs: Dict[str, Any] = {}

        # Device tracker lat/lon cache if subclass uses it
        self._lat: Optional[float] = None
        self._lon: Optional[float] = None

    # ----------------------- Precision helpers -----------------------

    def _label_precision(self) -> int:
        """
        Hyphenated LABEL precision (decimals). New keys take priority.
        Falls back to legacy single precision if present, else default.
        """
        opts = self._entry.options or {}
        if CONF_COMBINE_LABEL_PRECISION in opts:
            try:
                return int(opts[CONF_COMBINE_LABEL_PRECISION])
            except Exception:
                return DEFAULT_COMBINE_PRECISION
        if CONF_COMBINE_PRECISION in opts:  # legacy
            try:
                return int(opts[CONF_COMBINE_PRECISION])
            except Exception:
                return DEFAULT_COMBINE_PRECISION
        return DEFAULT_COMBINE_PRECISION

    def _attr_precision(self) -> int:
        """
        Attribute precision (decimals) used when NOT hyphenating.
        Defaults like label precision if not explicitly set.
        """
        opts = self._entry.options or {}
        if CONF_COMBINE_ATTR_PRECISION in opts:
            try:
                return int(opts[CONF_COMBINE_ATTR_PRECISION])
            except Exception:
                return DEFAULT_COMBINE_PRECISION
        # if not set, mirror label precision for a sane default
        return self._label_precision()

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            # Don’t coerce None/"unknown"/"unavailable"
            if value is None:
                return None
            s = str(value).strip().lower()
            if s in ("unknown", "unavailable", "none", ""):
                return None
            return float(s)
        except Exception:
            return None

    @staticmethod
    def _round_float(v: float, decimals: int) -> float:
        try:
            return round(float(v), int(decimals))
        except Exception:
            return v

    @staticmethod
    def _format_for_label(v: Any, decimals: int) -> str:
        """
        Make a human-friendly string for the label (hyphenated part).
        Non-numeric values return as-is; numeric values fixed to 'decimals'.
        """
        num = CustomBaseEntity._coerce_float(v)
        if num is None:
            return str(v)
        try:
            d = max(0, int(decimals))
            if d == 0:
                return f"{int(round(num, 0))}"
            return f"{num:.{d}f}"
        except Exception:
            return str(v)

    # ----------------------- HA hooks -----------------------

    async def async_added_to_hass(self) -> None:
        """Register listeners to keep state/attributes in sync."""
        track = async_track_state_change_event

        track(self.hass, [self._source_entity], self._update)

        if self._battery_entity:
            track(self.hass, [self._battery_entity], self._update)

        for ent in self._extra_map.values():
            track(self.hass, [ent], self._update)

        if self._combine and self._combine_entity:
            track(self.hass, [self._combine_entity], self._update)

        # Prime once
        self._update(None)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return self._extra_attrs

    # ----------------------- core update -----------------------

    @callback
    def _update(self, _event) -> None:
        """Mirror source entity; handle combine; build extra attrs; cache lat/lon; write once."""
        src = self.hass.states.get(self._source_entity)

        # Mirror primary state + selected attributes
        if src:
            self._state = src.state
            for attr in self._inherit_attrs:
                if attr in src.attributes:
                    self._extra_attrs[attr] = src.attributes[attr]

        # Battery
        if self._battery_entity:
            batt = self.hass.states.get(self._battery_entity)
            if batt is not None:
                self._extra_attrs["battery_level"] = batt.state

        # User-defined extra attributes (friendly -> entity.state)
        for friendly, ent in (self._extra_map or {}).items():
            st = self.hass.states.get(ent)
            if st is not None:
                self._extra_attrs[friendly] = st.state

        # Combine logic
        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co is not None:
                if self._hyphenate:
                    # Append to label text (use label precision)
                    part = self._format_for_label(co.state, self._label_precision())
                    base = "" if self._state in (None, "unknown", "unavailable") else str(self._state)
                    self._state = f"{base} - {part}".strip(" -")
                else:
                    # Add as attribute (use attribute precision)
                    key = (self._combine_attr_name or "combine").strip() or "combine"
                    num = self._coerce_float(co.state)
                    if num is None:
                        # non-numeric, store raw
                        self._extra_attrs[key] = co.state
                    else:
                        self._extra_attrs[key] = self._round_float(num, self._attr_precision())

        # Device tracker lat/lon cache (if subclass uses it)
        if hasattr(self, "_lat"):
            if src is not None:
                self._lat = src.attributes.get("latitude")
                self._lon = src.attributes.get("longitude")

        # Single write
        # (Requires subclass to also inherit a HA Entity base class.)
        self.async_write_ha_state()
