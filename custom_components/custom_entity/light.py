from homeassistant.components.light import LightEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "light":
        return
    async_add_entities([CustomLightEntity(hass, entry)])

class CustomLightEntity(CustomBaseEntity, LightEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_is_on = False
        self._attr_brightness = None

    @property
    def is_on(self):
        return str(self._state).lower() in ("on", "true")

    @property
    def brightness(self):
        try:
            return int(self._extra_attrs.get("brightness", 255))
        except Exception:
            return None

    async def async_turn_on(self, **kwargs):
        self._state = "on"
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._state = "off"
        self.async_write_ha_state()
