from homeassistant.components.switch import SwitchEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "switch":
        return
    async_add_entities([CustomSwitchEntity(hass, entry)])

class CustomSwitchEntity(CustomBaseEntity, SwitchEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_is_on = False

    @property
    def is_on(self):
        return str(self._state).lower() in ("on", "true")

    async def async_turn_on(self, **kwargs):
        # Optional: mirror to source, or just flip locally
        self._state = "on"
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._state = "off"
        self.async_write_ha_state()
