from homeassistant.components.select import SelectEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "select":
        return
    async_add_entities([CustomSelectEntity(hass, entry)])

class CustomSelectEntity(CustomBaseEntity, SelectEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_options = []

    @property
    def current_option(self):
        return self._state

    async def async_select_option(self, option: str):
        self._state = option
        self.async_write_ha_state()
