"""Device Tracker platform for Custom Entity (back-compat unique_id & presence gating)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import TrackerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State, callback

from .entity_base import CustomBaseEntity
from .const import CONF_PRESENCE_HELPER

def _truthy_on(val: str | None) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("on", "home", "open", "true", "1")

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") == "device_tracker":
        async_add_entities([CustomTrackerEntity(hass, entry)])

class CustomTrackerEntity(CustomBaseEntity, TrackerEntity):
    """Mirror a device_tracker with optional hyphenated label and presence gating."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        # BACK-COMPAT: keep the old unique_id exactly the entry_id so entity_id doesn't change
        self._attr_unique_id = entry.entry_id
        self._presence_helper_entity: str | None = self.entry.options.get(CONF_PRESENCE_HELPER) or self.entry.data.get(CONF_PRESENCE_HELPER)

    @property
    def source_type(self) -> SourceType | None:
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra_attrs

    @callback
    def _update(self, _event) -> None:
        """Base recompute then apply presence gating for 'home'."""
        super()._update(_event)

        helper_id = self._presence_helper_entity
        if not helper_id:
            return

        helper: State | None = self.hass.states.get(helper_id)
        if not _truthy_on(helper.state if helper else None):
            self._state = "not_home"
            self.async_write_ha_state()
