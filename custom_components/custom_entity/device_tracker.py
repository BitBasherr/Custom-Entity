# custom_components/custom_entity/device_tracker.py
"""Device Tracker platform for Custom Entity (hyphenated label supported)."""
from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_FRIENDLY_NAME, CONF_PRESENCE_HELPER
from .entity_base import CustomBaseEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Custom Entity device_tracker platform."""
    async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(CustomBaseEntity, TrackerEntity):
    """Mirrors a source tracker’s lat/lon and exposes a composed, hyphenated state string."""

    _attr_should_poll = False
    _attr_has_entity_name = False  # we set a friendly name ourselves

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        TrackerEntity.__init__(self)
        CustomBaseEntity.__init__(self, hass, entry)
        self._attr_name = entry.data.get(CONF_FRIENDLY_NAME, "Custom Tracker")

        # Optional presence helper (stored in options or legacy data)
        self._presence_helper_entity: str | None = (
            (entry.options or {}).get(CONF_PRESENCE_HELPER)
            or (entry.data or {}).get(CONF_PRESENCE_HELPER)
        )

    # ---- TrackerEntity essentials ----
    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def source_type(self):
        # Keep using a simple string for broad HA compatibility
        return "gps"

    @property
    def latitude(self):
        return self._lat

    @property
    def longitude(self):
        return self._lon

    # ---- The important bit: override state so hyphenated label appears ----
    @property
    def state(self):
        """Return the composed state string built in CustomBaseEntity._update()."""
        return self._state

    # Add presence-helper state alongside inherited extra attributes
    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes or {}
        if self._presence_helper_entity:
            st = self.hass.states.get(self._presence_helper_entity)
            if st is not None:
                attrs["presence_helper_state"] = st.state
        return attrs
