from homeassistant.components.number import NumberEntity
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "number":
        return
    async_add_entities([CustomNumberEntity(hass, entry)])

class CustomNumberEntity(CustomBaseEntity, NumberEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_min_value = 0
        self._attr_max_value = 100
        self._attr_step = 1

    @property
    def value(self):
        try:
            return float(self._state)
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: float):
        # Optional: mirror set value back to source (unsupported)
        self._state = value
        self.async_write_ha_state()
