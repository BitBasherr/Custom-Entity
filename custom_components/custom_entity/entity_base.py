"""Shared logic for all Custom Entity types."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.core import HomeAssistant, callback, State
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_ATTRIBUTE_SENSORS,
    CONF_BATTERY_ENTITY,
    CONF_COMBINE,
    CONF_COMBINE_ATTR_NAME,
    CONF_COMBINE_ATTR_PRECISION,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_PRECISION,  # legacy for label precision
    CONF_DEVICE_CLASS,
    CONF_FRIENDLY_NAME,
    CONF_HYPHENATE_STATE,
    CONF_INHERIT_ATTRS,
    CONF_SOURCE_ENTITY,
    DEFAULT_COMBINE_PRECISION,
)


class CustomBaseEntity:
    """Mixin with shared wiring/state/updates for all platforms."""

    _attr_name: str | None = None
    _attr_device_class: str | None = None

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry

        # Core (from config flow)
        data = entry.data
        self._source_entity: str = data.get(CONF_SOURCE_ENTITY)
        self._attr_name = data.get(CONF_FRIENDLY_NAME)
        self._attr_device_class = data.get(CONF_DEVICE_CLASS)
        self._inherit_attrs: bool = bool(data.get(CONF_INHERIT_ATTRS, True))

        # Options
        opts = dict(entry.options or {})
        self._battery_entity: str | None = opts.get(CONF_BATTERY_ENTITY)
        self._extra_map: dict[str, str] = dict(opts.get(CONF_ATTRIBUTE_SENSORS, {}))
        self._combine: bool = bool(opts.get(CONF_COMBINE, False))
        self._combine_entity: str | None = opts.get(CONF_COMBINE_ENTITY)
        self._combine_attr_name: str | None = opts.get(CONF_COMBINE_ATTR_NAME)
        self._hyphenate: bool = bool(opts.get(CONF_HYPHENATE_STATE, False))

        # Precision (label + attribute). Keep legacy combine_precision for label.
        self._label_precision: int = int(
            opts.get(
                CONF_COMBINE_LABEL_PRECISION,
                opts.get(CONF_COMBINE_PRECISION, DEFAULT_COMBINE_PRECISION),
            )
        )
        self._attr_precision: int = int(
            opts.get(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION)
        )

        # runtime
        self._state: Any = None
        self._extra_attrs: Dict[str, Any] = {}

    # ─────────────────────────── lifecycle ────────────────────────────
    async def async_added_to_hass(self) -> None:
        """Wire listeners to all inputs that can influence our state/attrs."""
        ent_ids: set[str] = {self._source_entity}

        if self._battery_entity:
            ent_ids.add(self._battery_entity)

        if self._combine and self._combine_entity:
            ent_ids.add(self._combine_entity)

        for ent in self._extra_map.values():
            ent_ids.add(ent)

        # Listen once for all and update on any change
        self._unsub = async_track_state_change_event(
            self.hass, ent_ids, self._update  # type: ignore[arg-type]
        )

        # Prime state on add
        await self._prime_state()

    async def _prime_state(self) -> None:
        """Initial write with current states (no event object available)."""
        await self.hass.async_add_executor_job(lambda: None)  # yield
        self._update(None)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe listeners."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None

    # ───────────────────────────── helpers ─────────────────────────────
    @callback
    def _fmt_for_label(self, val: Any, precision: int) -> str:
        """Format a value for display in the label."""
        try:
            f = float(val)
        except (TypeError, ValueError):
            return str(val)

        p = max(0, min(3, int(precision)))
        if p == 0:
            return str(int(round(f)))
        s = f"{f:.{p}f}".rstrip("0").rstrip(".")
        return s

    @callback
    def _round_for_attr(self, val: Any, precision: int) -> Any:
        """Round numeric for attribute; keep numeric type when possible."""
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
        """Recompute state + attributes from all inputs."""
        self._extra_attrs = {}

        src = self.hass.states.get(self._source_entity)
        if src is None:
            # Underlying entity missing; expose as unavailable
            self._state = "unavailable"
            self.async_write_ha_state()
            return

        # Base state mirrors source
        self._state = src.state

        # Inherit original attributes
        if self._inherit_attrs and isinstance(src.attributes, dict):
            self._extra_attrs.update(src.attributes)

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
                    self._extra_attrs[key] = self._round_for_attr(
                        co.state, self._attr_precision
                    )

        # Single write
        self.async_write_ha_state()
