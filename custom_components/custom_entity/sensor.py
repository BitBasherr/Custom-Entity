from homeassistant.components.sensor import SensorEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "sensor":
        return
    async_add_entities([CustomSensorEntity(hass, entry)])

class CustomSensorEntity(CustomBaseEntity, SensorEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)

    @property
    def state(self):
        return self._state
