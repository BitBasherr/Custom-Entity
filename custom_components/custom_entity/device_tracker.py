"""Device Tracker platform for Custom Entity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity_base import CustomBaseEntity
from .const import CONF_PRESENCE_HELPER


def _truthy_on(val: str | None) -> bool:
    """Interpret common 'on' states for boolean-ish entities."""
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("on", "home", "open", "true", "1")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Custom Entity device_tracker from a config entry."""
    async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(CustomBaseEntity, TrackerEntity):
    """A device_tracker that mirrors another entity and optionally hyphenates a combine value.

    Presence helper behavior:
    - If Options -> Presence helper is set AND it is OFF, force state to 'not_home'.
    - If helper is ON or not set, pass-through state (including hyphenation if configured).
    """

    _attr_should_poll = False  # we listen to state_changed events

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        CustomBaseEntity.__init__(self, hass, entry)
        self._attr_unique_id = f"{self.entry.entry_id}-tracker"
        # cache presence helper entity_id if configured
        self._presence_helper_entity: str | None = entry.options.get(CONF_PRESENCE_HELPER)

    @property
    def source_type(self) -> SourceType | None:
        """Best-effort source type for UI consistency."""
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose any mirrored/combined attributes to the state machine."""
        return self._extra_attrs

    @callback
    def _update(self, _event) -> None:
        """Apply base recompute, then presence gating for 'home' semantics."""
        # Run the base recompute first
        super()._update(_event)

        # Apply presence gating only if a helper was configured
        if not self._presence_helper_entity:
            return

        helper: State | None = self.hass.states.get(self._presence_helper_entity)
        helper_on = _truthy_on(helper.state if helper else None)

        if not helper_on:
            # If helper is OFF, we force 'not_home' (ignore hyphenation/zone strings)
            self._state = "not_home"
            self.async_write_ha_state()
