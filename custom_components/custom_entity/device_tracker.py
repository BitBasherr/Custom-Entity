from homeassistant.components.device_tracker import TrackerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from .entity_base import CustomBaseEntity
from .const import CONF_HYPHENATE_STATE, CONF_PRESENCE_HELPER


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
        # helper boolean (may be None for legacy configs)
        self._helper = (
            self._entry.options.get(CONF_PRESENCE_HELPER)
            if self._entry.options
            else self._entry.data.get(CONF_PRESENCE_HELPER)
        )

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
        helper_ok = (
            self.hass.states.is_state(self._helper, "on") if self._helper else True
        )

        if src and helper_ok:
            # mirror the real tracker (lat, lon, state)
            self._lat = src.attributes.get("latitude")
            self._lon = src.attributes.get("longitude")
            super()._update(_event)              # sets _state etc.
        else:
            # treat as away
            self._state = "not_home"
            self._lat = self._lon = None
            self.async_write_ha_state()
