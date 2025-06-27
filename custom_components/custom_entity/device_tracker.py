from homeassistant.components.device_tracker import TrackerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from .entity_base import CustomBaseEntity
from .const import CONF_HYPHENATE_STATE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("platform") == "device_tracker":
        async_add_entities([CustomTrackerEntity(hass, entry)])


class CustomTrackerEntity(CustomBaseEntity, TrackerEntity):
    """Mirror tracker with optional hyphen-state."""

    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(hass, entry)
        self._attr_source_type = SourceType.GPS
        self._lat: float | None = None
        self._lon: float | None = None

    # -------- base Tracker props (cached by entity_base) -------------
    @property
    def latitude(self):
        return self._lat

    @property
    def longitude(self):
        return self._lon

    # -------- force HA to show the hyphenated _state when requested --
    @property
    def state(self):
        hyphen = (
            self._entry.options.get(CONF_HYPHENATE_STATE)
            if self._entry.options
            else self._entry.data.get(CONF_HYPHENATE_STATE, False)
        )
        if hyphen:
            return self._state          # e.g. "Pastushoks - 12"
        # fall back to TrackerEntity logic (zone engine)
        return super().state

    # -------- cache lat/lon early, then run shared update ------------
    @callback
    def _update(self, _event):
        src = self.hass.states.get(self._source_entity)
        if src:
            self._lat = src.attributes.get("latitude")
            self._lon = src.attributes.get("longitude")
        super()._update(_event)
