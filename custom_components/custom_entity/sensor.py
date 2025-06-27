"""Custom Sensor entity."""
from __future__ import annotations

from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity

from .const import CONF_SOURCE_ENTITY, CONF_FRIENDLY_NAME, CONF_DEVICE_CLASS, CONF_INHERIT_ATTRS, DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([CustomSensorEntity(hass, entry)])


class CustomSensorEntity(SensorEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self._entry = entry
        self._source_entity = entry.data[CONF_SOURCE_ENTITY]
        self._device_class = entry.data.get(CONF_DEVICE_CLASS)
        self._inherit_attrs = entry.data.get(CONF_INHERIT_ATTRS, [])
        self._attr_name = entry.data.get(CONF_FRIENDLY_NAME, "Custom Sensor")
        self._attr_unique_id = entry.entry_id
        if self._device_class:
            self._attr_device_class = self._device_class
        self._state = None
        self._extra_attrs = {}
        self.hass = hass

    async def async_added_to_hass(self):
        self._update()
        self.async_on_remove(
            self.hass.helpers.event.async_track_state_change_event(
                [self._source_entity], self._handle_event
            )
        )

    async def _handle_event(self, event):
        self._update()
        self.async_write_ha_state()

    def _update(self):
        src = self.hass.states.get(self._source_entity)
        if src:
            self._state = src.state
            self._extra_attrs = {
                k: v for k, v in src.attributes.items() if k in self._inherit_attrs
            }

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attrs
