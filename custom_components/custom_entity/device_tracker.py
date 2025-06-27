from homeassistant.components.device_tracker import TrackerEntity, SourceType
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "device_tracker":
        return
    async_add_entities([CustomTrackerEntity(hass, entry)])

class CustomTrackerEntity(CustomBaseEntity, TrackerEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_source_type = SourceType.GPS

    @property
    def latitude(self):
        return self.hass.states.get(self._source_entity).attributes.get("latitude")

    @property
    def longitude(self):
        return self.hass.states.get(self._source_entity).attributes.get("longitude")
