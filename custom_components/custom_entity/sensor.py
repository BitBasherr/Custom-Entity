"""Custom Sensor entity."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, State
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    # NEW bits:
    CONF_SENSOR_MODE,
    SENSOR_MODE_PERSON_LABEL,
    CONF_PERSON_ENTITY,
    CONF_LABEL_ATTR,
    DEFAULT_LABEL_ATTR,
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    # NEW: if sensor mode is person_label, use PersonLabelSensor; else keep your original
    if entry.data.get(CONF_SENSOR_MODE) == SENSOR_MODE_PERSON_LABEL:
        async_add_entities([PersonLabelSensor(hass, entry)])
    else:
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


# ---------- NEW: Person Label Sensor (still just a sensor) ----------
class PersonLabelSensor(SensorEntity):
    """A sensor that clearly states it's only a sensor (not HA's person)."""

    _attr_icon = "mdi:account"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._entry = entry

        d = entry.data
        o = entry.options or {}

        self._person_entity: str = d.get(CONF_PERSON_ENTITY, "")
        self._tracker_entity: str = d.get(CONF_SOURCE_ENTITY, "")
        self._label_attr: str = d.get(CONF_LABEL_ATTR, DEFAULT_LABEL_ATTR) or DEFAULT_LABEL_ATTR
        self._inherit_attrs = d.get(CONF_INHERIT_ATTRS, [])

        # Reuse hyphenation from options if you’ve enabled it elsewhere; default True here.
        self._hyphenate: bool = bool(o.get("hyphenate_state", True))

        self._attr_name = d.get(CONF_FRIENDLY_NAME, "Person Label (sensor)")
        self._attr_unique_id = f"{entry.entry_id}_person_label"
        self._state: str | None = None
        self._attrs: dict[str, Any] = {
            "note": "This is a sensor entity that mirrors a person and a tracker (not a core person)."
        }

    async def async_added_to_hass(self) -> None:
        async_track_state_change_event(self.hass, [self._person_entity, self._tracker_entity], self._update)
        self._update(None)

    @property
    def state(self) -> str | None:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._attrs

    @callback
    def _update(self, _event) -> None:
        person: State | None = self.hass.states.get(self._person_entity) if self._person_entity else None
        tracker: State | None = self.hass.states.get(self._tracker_entity) if self._tracker_entity else None

        zone = person.state if person else "unknown"
        addr = None
        if tracker and isinstance(tracker.attributes, dict):
            addr = tracker.attributes.get(self._label_attr)
            # carry over common geo attrs
            lat = tracker.attributes.get("latitude")
            lon = tracker.attributes.get("longitude")
            acc = tracker.attributes.get("gps_accuracy")
            if lat is not None:
                self._attrs["latitude"] = lat
            if lon is not None:
                self._attrs["longitude"] = lon
            if acc is not None:
                self._attrs["gps_accuracy"] = acc

            # user-selected inherit list
            for k in self._inherit_attrs or []:
                if k in tracker.attributes:
                    self._attrs[k] = tracker.attributes[k]

        if self._hyphenate and addr:
            self._state = f"{zone} - {addr}"
        else:
            self._state = str(zone)

        if person:
            self._attrs["person"] = person.entity_id
        if tracker:
            self._attrs["tracker"] = tracker.entity_id
            self._attrs[self._label_attr] = addr

        self.async_write_ha_state()
