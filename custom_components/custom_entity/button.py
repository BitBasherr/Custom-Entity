from homeassistant.components.button import ButtonEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "button":
        return
    async_add_entities([CustomButtonEntity(hass, entry)])

class CustomButtonEntity(CustomBaseEntity, ButtonEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)

    async def async_press(self):
        # You can perform an action or trigger a state change here
        self._state = "pressed"
        self.async_write_ha_state()
