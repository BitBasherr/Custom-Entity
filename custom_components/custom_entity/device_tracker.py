"""Device Tracker platform for Custom Entity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity_base import CustomBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Custom Entity device_tracker from a config entry."""
    async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(CustomBaseEntity, TrackerEntity):
    """A device_tracker that mirrors another entity and optionally hyphenates a combine value."""

    _attr_should_poll = False  # we listen to state_changed events

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        # NOTE: our mixin stores the entry on self.entry (no underscore)
        CustomBaseEntity.__init__(self, hass, entry)
        # Unique ID anchors this entity to the config entry
        self._attr_unique_id = f"{self.entry.entry_id}-tracker"

    @property
    def source_type(self) -> SourceType | None:
        """Best-effort source type for UI consistency."""
        # Most phone/person trackers are GPS; returning GPS is broadly compatible.
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose any mirrored/combined attributes to the state machine."""
        return self._extra_attrs
