from homeassistant.components.text import TextEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "text":
        return
    async_add_entities([CustomTextEntity(hass, entry)])

class CustomTextEntity(CustomBaseEntity, TextEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_native_value = ""

    @property
    def native_value(self):
        return self._state

    async def async_set_value(self, value: str):
        self._state = value
        self.async_write_ha_state()
