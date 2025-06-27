from homeassistant.components.device_tracker import TrackerEntity, SourceType
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "device_tracker":
        return
    async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(CustomBaseEntity, TrackerEntity):
    """Mirror a device/person entity with optional hyphenated state."""

    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_source_type = SourceType.GPS
        self._lat: float | None = None
        self._lon: float | None = None

    # HA calls these even before async_added_to_hass finishes.
    @property
    def latitude(self):
        return self._lat

    @property
    def longitude(self):
        return self._lon
    
    @callback
    # Override _update to store lat/lon and then call parent logic
    def _update(self, _event):
        src_state = self.hass.states.get(self._source_entity)
        if src_state is not None:
            self._lat = src_state.attributes.get("latitude")
            self._lon = src_state.attributes.get("longitude")
        # run the shared logic (updates self._state, attributes, etc.)
        super()._update(_event)
