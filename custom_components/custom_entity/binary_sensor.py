from homeassistant.components.binary_sensor import BinarySensorEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "binary_sensor":
        return
    async_add_entities([CustomBinarySensor(hass, entry)])

class CustomBinarySensor(CustomBaseEntity, BinarySensorEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)

    @property
    def is_on(self):
        return str(self._state).lower() in ("on", "true", "open", "active", "home")
