from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from .entity_base import CustomBaseEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") != "climate":
        return
    async_add_entities([CustomClimateEntity(hass, entry)])

class CustomClimateEntity(CustomBaseEntity, ClimateEntity):
    def __init__(self, hass, entry):
        super().__init__(hass, entry)
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
        self._attr_temperature_unit = hass.config.units.temperature_unit
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_target_temperature = 22.0

    @property
    def target_temperature(self):
        return self._attr_target_temperature

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is not None:
            self._attr_target_temperature = temp
            self.async_write_ha_state()

    @property
    def hvac_mode(self):
        return self._attr_hvac_mode

    async def async_set_hvac_mode(self, hvac_mode):
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
