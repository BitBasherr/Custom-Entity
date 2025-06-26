"""Platform for custom device trackers using config entries."""
import logging

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_SOURCE_ENTITY,
    CONF_FRIENDLY_NAME,
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_ENTITY,
    CONF_ATTRIBUTE_NAME,
    CONF_ATTRIBUTE_SENSORS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities
) -> None:
    data    = entry.data
    opts    = entry.options or {}

    battery_entity   = opts.get(CONF_BATTERY_ENTITY)
    attribute_entity = opts.get(CONF_ATTRIBUTE_ENTITY)
    attribute_name   = data.get(CONF_ATTRIBUTE_NAME) or opts.get(CONF_ATTRIBUTE_NAME)
    attribute_sensors = opts.get(CONF_ATTRIBUTE_SENSORS)

    if not attribute_sensors and attribute_entity and attribute_name:
        attribute_sensors = {attribute_name: attribute_entity}

    combine        = data.get(CONF_COMBINE, False)
    combine_entity = data.get(CONF_COMBINE_ENTITY) or opts.get(CONF_COMBINE_ENTITY)
    combine_name   = data.get(CONF_COMBINE_ATTR_NAME) or opts.get(CONF_COMBINE_ATTR_NAME)

    async_add_entities([
        CustomEntityEntity(
            hass,
            entry.entry_id,
            data.get(CONF_FRIENDLY_NAME) or data.get(CONF_SOURCE_ENTITY),
            data.get(CONF_SOURCE_ENTITY),
            battery_entity,
            attribute_sensors,
            combine,
            combine_entity,
            combine_name,
        )
    ])


class CustomEntityEntity(TrackerEntity):
    """Custom device tracker entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        source_entity: str,
        battery_entity: str | None,
        attribute_sensors: dict | None,
        combine: bool,
        combine_entity: str | None,
        combine_attr_name: str | None,    # ← new
    ) -> None:
        self.hass = hass
        self._source_entity      = source_entity
        self._battery_entity     = battery_entity
        self._attribute_sensors  = attribute_sensors or {}
        self._combine            = combine
        self._combine_entity     = combine_entity
        self._combine_attr_name  = combine_attr_name  # ← new

        self._attr_name                  = name
        self._attr_unique_id             = entry_id
        self._attr_icon                  = "mdi:map-marker"
        self._attr_extra_state_attributes = {}

        self._attr_latitude          = None
        self._attr_longitude         = None
        self._attr_location_accuracy = None
        self._attr_battery_level     = None
        self._combine_value          = None

    @property
    def source_type(self):
        return "gps"

    @property
    def state(self):
        base = super().state
        if self._combine and self._combine_value is not None:
            return f"{base} - {self._combine_value}"
        return base

    async def async_added_to_hass(self):
        async_track_state_change_event(
            self.hass, [self._source_entity], self._async_update
        )
        if self._battery_entity:
            async_track_state_change_event(
                self.hass, [self._battery_entity], self._async_update
            )
        for ent in self._attribute_sensors.values():
            async_track_state_change_event(
                self.hass, [ent], self._async_update
            )
        if self._combine and self._combine_entity:
            async_track_state_change_event(
                self.hass, [self._combine_entity], self._async_update
            )

        # prime initial
        self._async_update(None)

    @callback
    def _async_update(self, event):
        """Handle any tracked-entity change."""
        # 1) coords & zone
        src = self.hass.states.get(self._source_entity)
        if src:
            attrs = src.attributes
            self._attr_latitude          = attrs.get("latitude")
            self._attr_longitude         = attrs.get("longitude")
            self._attr_location_accuracy = attrs.get("gps_accuracy", attrs.get("location_accuracy"))

        # 2) battery
        if self._battery_entity:
            batt = self.hass.states.get(self._battery_entity)
            if batt:
                try:
                    self._attr_battery_level = int(float(batt.state))
                except (ValueError, TypeError):
                    self._attr_battery_level = None

        # 3) extra attribute sensors
        for name, ent in self._attribute_sensors.items():
            at = self.hass.states.get(ent)
            if at:
                self._attr_extra_state_attributes[name] = at.state

        # 4) combine sensor
        if self._combine and self._combine_entity:
            co = self.hass.states.get(self._combine_entity)
            if co:
                self._combine_value = co.state
                # and also expose it under your custom name
                if self._combine_attr_name:
                    self._attr_extra_state_attributes[self._combine_attr_name] = co.state

        self.async_write_ha_state()
