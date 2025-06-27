"""Shared logic for all Custom Entity types."""
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_SOURCE_ENTITY, CONF_FRIENDLY_NAME, CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS, CONF_BATTERY_ENTITY, CONF_ATTRIBUTE_SENSORS,
    CONF_COMBINE, CONF_COMBINE_ENTITY, CONF_COMBINE_ATTR_NAME
)


class CustomBaseEntity:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self._entry = entry
        data = entry.data
        opts = entry.options or {}

        self._source_entity     = data[CONF_SOURCE_ENTITY]
        self._device_class      = data.get(CONF_DEVICE_CLASS)
        self._inherit_attrs     = data.get(CONF_INHERIT_ATTRS, [])
        self._battery_entity    = opts.get(CONF_BATTERY_ENTITY)
        self._extra_map         = opts.get(CONF_ATTRIBUTE_SENSORS, {})

        self._combine           = data.get(CONF_COMBINE, False)
        self._combine_entity    = data.get(CONF_COMBINE_ENTITY) or opts.get(CONF_COMBINE_ENTITY)
        self._combine_attr_name = data.get(CONF_COMBINE_ATTR_NAME) or opts.get(CONF_COMBINE_ATTR_NAME)

        self._attr_name = data.get(CONF_FRIENDLY_NAME, "Custom Entity")
        self._attr_unique_id = entry.entry_id
        if self._device_class and hasattr(self, "_attr_device_class"):
            self._attr_device_class = self._device_class

        self._state = None
        self._extra_attrs = {}

    async def async_added_to_hass(self):
        track = async_track_state_change_event
        track(self.hass, [self._source_entity], self._update)
        if self._battery_entity:
            track(self.hass, [self._battery_entity], self._update)
        for ent in self._extra_map.values():
            track(self.hass, [ent], self._update)
        if self._combine and self._combine_entity:
            track(self.hass, [self._combine_entity], self._update)
        self._update(None)

    @property
    def extra_state_attributes(self):
        return self._extra_attrs

    @callback
    def _update(self, _event):
        src = self.hass.states.get(self._source_entity)
        if src:
            self._state = src.state
            for attr in self._inherit_attrs:
                if attr in src.attributes:
                    self._extra_attrs[attr] = src.attributes[attr]

        if self._battery_entity:
            batt = self.hass.states.get(self._battery_entity)
            if batt:
                self._extra_attrs["battery_level"] = batt.state

        for friendly, ent in self._extra_map.items():
            st = self.hass.states.get(ent)
            if st is not None:
                self._extra_attrs[friendly] = st.state

        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co:
                self._extra_attrs[self._combine_attr_name or "combine"] = co.state

        self.async_write_ha_state()
