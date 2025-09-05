"""Custom Sensor entity with Mirror mode and Person Label mode."""
from __future__ import annotations

from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity

from .const import (
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_INHERIT_ATTRS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_ATTR_PRECISION,
    DEFAULT_COMBINE_PRECISION,
    CONF_SENSOR_MODE,
    SENSOR_MODE_MIRROR,
    SENSOR_MODE_PERSON_LABEL,
    CONF_PERSON_ENTITY,
    CONF_LABEL_ATTR,
    DEFAULT_LABEL_ATTR,
)


def _to_int(x, fallback: int) -> int:
    try:
        return int(str(x))
    except Exception:
        return fallback


def _fmt_number(val, precision: int) -> str:
    try:
        f = float(val)
        return f"{f:.{precision}f}"
    except Exception:
        return str(val)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([CustomSensorEntity(hass, entry)])


class CustomSensorEntity(SensorEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._entry = entry

        d = entry.data
        o = entry.options or {}

        self._platform = "sensor"
        self._mode = d.get(CONF_SENSOR_MODE, SENSOR_MODE_MIRROR)

        self._source_entity = d.get(CONF_SOURCE_ENTITY)
        self._person_entity = d.get(CONF_PERSON_ENTITY)
        self._label_attr = d.get(CONF_LABEL_ATTR, DEFAULT_LABEL_ATTR)

        self._device_class = d.get(CONF_DEVICE_CLASS)
        self._inherit_attrs = d.get(CONF_INHERIT_ATTRS, [])

        self._attr_name = d.get(CONF_FRIENDLY_NAME, "Custom Sensor")
        self._attr_unique_id = entry.entry_id
        if self._device_class:
            self._attr_device_class = self._device_class

        # combine options (from options)
        self._combine = bool(o.get(CONF_COMBINE, d.get(CONF_COMBINE, False)))
        self._combine_entity = o.get(CONF_COMBINE_ENTITY, d.get(CONF_COMBINE_ENTITY))
        self._combine_attr_name = o.get(CONF_COMBINE_ATTR_NAME, d.get(CONF_COMBINE_ATTR_NAME, "combine"))
        self._hyphenate = bool(o.get(CONF_HYPHENATE_STATE, d.get(CONF_HYPHENATE_STATE, True)))
        self._label_prec = _to_int(o.get(CONF_COMBINE_LABEL_PRECISION, d.get(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION)), DEFAULT_COMBINE_PRECISION)
        self._attr_prec = _to_int(o.get(CONF_COMBINE_ATTR_PRECISION, d.get(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION)), DEFAULT_COMBINE_PRECISION)

        self._state = None
        self._extra_attrs: dict = {}

    async def async_added_to_hass(self):
        self._update()
        # watch source, person and combine entities for changes
        track = self.hass.helpers.event.async_track_state_change_event
        if self._source_entity:
            self.async_on_remove(track([self._source_entity], self._handle_event))
        if self._person_entity:
            self.async_on_remove(track([self._person_entity], self._handle_event))
        if self._combine and self._combine_entity:
            self.async_on_remove(track([self._combine_entity], self._handle_event))

    async def _handle_event(self, _event):
        self._update()
        self.async_write_ha_state()

    def _update(self):
        self._extra_attrs = {}

        # Mirror chosen attributes from source (both modes)
        if self._source_entity:
            src = self.hass.states.get(self._source_entity)
            if src and isinstance(src.attributes, dict):
                for k in self._inherit_attrs:
                    if k in src.attributes:
                        self._extra_attrs[k] = src.attributes[k]

        # Determine base state
        if self._mode == SENSOR_MODE_PERSON_LABEL:
            # This is explicitly a sensor label — not a Person entity
            self._extra_attrs["entity_note"] = "This is a label sensor, not a Person."
            # Prefer person attribute, fall back to device_tracker attribute
            label_val = None
            if self._person_entity:
                pst = self.hass.states.get(self._person_entity)
                if pst:
                    label_val = pst.attributes.get(self._label_attr)
            if label_val is None and self._source_entity:
                sst = self.hass.states.get(self._source_entity)
                if sst:
                    label_val = sst.attributes.get(self._label_attr)
            self._state = "" if label_val in (None, "") else str(label_val)
        else:
            # Mirror mode — copy the source state verbatim
            src = self.hass.states.get(self._source_entity) if self._source_entity else None
            self._state = None if not src else src.state

        # Combine behavior
        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co:
                if self._hyphenate:
                    # show combined value in label with label precision if numeric
                    combined = _fmt_number(co.state, self._label_prec)
                    base = "" if self._state in (None, "unknown", "unavailable") else str(self._state)
                    self._state = f"{base} - {combined}" if base else combined
                else:
                    # add as attribute with attr precision if numeric
                    self._extra_attrs[self._combine_attr_name or "combine"] = _fmt_number(co.state, self._attr_prec)

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._extra_attrs
