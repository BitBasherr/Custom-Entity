"""Device Tracker platform for Custom Entity."""
from __future__ import annotations

from homeassistant.components.device_tracker import DeviceTrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_FRIENDLY_NAME,
    CONF_PRESENCE_HELPER,
)
from .entity_base import CustomBaseEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Custom Entity device_tracker platform."""
    async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(CustomBaseEntity, DeviceTrackerEntity):
    """Mirrors a source entity's lat/lon; optional presence helper metadata."""

    _attr_should_poll = False
    _attr_has_entity_name = False  # we already set a friendly name

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        DeviceTrackerEntity.__init__(self)
        CustomBaseEntity.__init__(self, hass, entry)
        self._attr_name = entry.data.get(CONF_FRIENDLY_NAME, "Custom Tracker")
        # Presence helper is optional and may live in options or legacy data
        self._presence_helper_entity: str | None = (
            (entry.options or {}).get(CONF_PRESENCE_HELPER)
            or (entry.data or {}).get(CONF_PRESENCE_HELPER)
        )

    # ---- DeviceTrackerEntity requirements ----
    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def source_type(self):
        # Using a plain string keeps compatibility across HA versions
        return "gps"

    @property
    def latitude(self):
        return self._lat

    @property
    def longitude(self):
        return self._lon

    # Optional: pass-through any extra attributes from the base,
    # plus expose the presence helper state (if configured) for visibility.
    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes or {}
        if self._presence_helper_entity:
            st = self.hass.states.get(self._presence_helper_entity)
            if st is not None:
                attrs["presence_helper_state"] = st.state
        return attrs
