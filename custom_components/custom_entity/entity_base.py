"""Shared logic for all Custom Entity types (backward compatible)."""
from __future__ import annotations

from typing import Any, Dict, Iterable

from homeassistant.core import HomeAssistant, callback, State
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
    CONF_PRESENCE_HELPER,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_ATTR_PRECISION,
    CONF_COMBINE_PRECISION,       # legacy single knob (back-compat)
    DEFAULT_COMBINE_PRECISION,
)


class CustomBaseEntity:
    """Mixin with shared wiring/state/updates for all platforms."""

    _attr_name: str | None = None
    _attr_device_class: str | None = None

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry  # keep consistent across platforms

        # Core (from config flow)
        data = entry.data or {}
        self._source_entity: str = data.get(CONF_SOURCE_ENTITY)
        self._attr_name = data.get(CONF_FRIENDLY_NAME) or "Custom Entity"
        self._attr_device_class = data.get(CONF_DEVICE_CLASS)

        # BACK-COMPAT: inherit_attributes may be a LIST (old) or BOOL (new)
        _inherit = data.get(CONF_INHERIT_ATTRS, True)
        self._inherit_attrs_bool: bool = bool(_inherit) if isinstance(_inherit, bool) else False
        self._inherit_attrs_list: Iterable[str] = _inherit if isinstance(_inherit, (list, tuple)) else ()

        # Options (preferred)
        opts = dict(entry.options or {})
        # Also read from data (old storage) if missing in options
        def opt_or_data(key: str, default=None):
            return opts.get(key, data.get(key, default))

        self._battery_entity: str | None = opt_or_data(CONF_BATTERY_ENTITY)
        self._extra_map: dict[str, str] = dict(opt_or_data(CONF_ATTRIBUTE_SENSORS, {}) or {})
        self._combine: bool = bool(opt_or_data(CONF_COMBINE, False))
        self._combine_entity: str | None = opt_or_data(CONF_COMBINE_ENTITY)
        self._combine_attr_name: str | None = opt_or_data(CONF_COMBINE_ATTR_NAME)
        self._hyphenate: bool = bool(opt_or_data(CONF_HYPHENATE_STATE, False))
        self._presence_helper: str | None = opt_or_data(CONF_PRESENCE_HELPER)

        # Precision (label + attribute). Keep legacy single knob for label.
        self._label_precision: int = int(
            opt_or_data(CONF_COMBINE_LABEL_PRECISION, opt_or_data(CONF_COMBINE_PRECISION, DEFAULT_COMBINE_PRECISION))
        )
        self._attr_precision: int = int(opt_or_data(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION))

        # runtime
        self._state: Any = None
        self._extra_attrs: Dict[str, Any] = {}
        self._unsub = None

    # ───────────────────────────── entity API ─────────────────────────────
    @property
    def available(self) -> bool:
        return self._state != "unavailable"

    @property
    def state(self) -> Any:
        return self._state

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return self._extra_attrs

    # ─────────────────────────── lifecycle ────────────────────────────
    async def async_added_to_hass(self) -> None:
        ent_ids: set[str] = {self._source_entity}

        if self._battery_entity:
            ent_ids.add(self._battery_entity)

        if self._combine and self._combine_entity:
            ent_ids.add(self._combine_entity)

        for ent in self._extra_map.values():
            ent_ids.add(ent)

        if self._presence_helper:
            ent_ids.add(self._presence_helper)

        self._unsub = async_track_state_change_event(self.hass, ent_ids, self._update)  # type: ignore[arg-type]
        await self._prime_state()

    async def _prime_state(self) -> None:
        await self.hass.async_add_executor_job(lambda: None)  # yield
        self._update(None)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    # ───────────────────────────── helpers ─────────────────────────────
    @callback
    def _fmt_for_label(self, val: Any, precision: int) -> str:
        try:
            f = float(val)
        except (TypeError, ValueError):
            return str(val)
        p = max(0, min(3, int(precision)))
        if p == 0:
            return str(int(round(f)))
        return f"{f:.{p}f}".rstrip("0").rstrip(".")

    @callback
    def _round_for_attr(self, val: Any, precision: int) -> Any:
        try:
            f = float(val)
        except (TypeError, ValueError):
            return val
        p = max(0, min(3, int(precision)))
        if p == 0:
            return int(round(f))
        return round(f, p)

    # ───────────────────────────── update ─────────────────────────────
    @callback
    def _update(self, _event) -> None:
        self._extra_attrs = {}

        src: State | None = self.hass.states.get(self._source_entity)
        if src is None:
            self._state = "unavailable"
            self.async_write_ha_state()
            return

        # Base state mirrors source
        self._state = src.state

        # Inherit attributes:
        # - If bool True: copy all source attrs
        # - Else if list: copy only listed names
        if self._inherit_attrs_bool and isinstance(src.attributes, dict):
            self._extra_attrs.update(src.attributes)
        elif self._inherit_attrs_list:
            for attr in self._inherit_attrs_list:
                if attr in src.attributes:
                    self._extra_attrs[attr] = src.attributes[attr]

        # Battery
        if self._battery_entity:
            batt = self.hass.states.get(self._battery_entity)
            if batt is not None:
                self._extra_attrs["battery_level"] = batt.state

        # User-defined extra sensors (friendly → entity_id)
        for friendly, ent in self._extra_map.items():
            st = self.hass.states.get(ent)
            if st is not None:
                self._extra_attrs[friendly] = st.state

        # Combine
        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co is not None:
                if self._hyphenate:
                    self._state = f"{self._state} - {self._fmt_for_label(co.state, self._label_precision)}"
                else:
                    key = self._combine_attr_name or "combine"
                    self._extra_attrs[key] = self._round_for_attr(co.state, self._attr_precision)

        # Optional tracker lat/lon cache for platform overrides
        if hasattr(self, "_lat"):
            self._lat = src.attributes.get("latitude")
            self._lon = src.attributes.get("longitude")

        self.async_write_ha_state()
