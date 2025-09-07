"""Init for Custom Entity integration (with entry migration and Options→Data bridge)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    CONF_PLATFORM,
    # migrate keys (existing)
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_SENSORS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,
    CONF_COMBINE_PRECISION,
    CONF_COMBINE_LABEL_PRECISION,
    # address fields (default-all)
    CONF_ADDRESS_FIELDS,
    DEFAULT_ADDRESS_FIELDS,
    # options→data bridge
    OPT_APPLY_DATA_UPDATE,
    DATA_MUTABLE_KEYS,
)

CONFIG_ENTRY_VERSION = 3

_PLATFORM_ENUM: Dict[str, Platform] = {
    "sensor": Platform.SENSOR,
    "binary_sensor": Platform.BINARY_SENSOR,
    "number": Platform.NUMBER,
    "switch": Platform.SWITCH,
    "device_tracker": Platform.DEVICE_TRACKER,
    "light": Platform.LIGHT,
    "climate": Platform.CLIMATE,
    "select": Platform.SELECT,
    "text": Platform.TEXT,
    "button": Platform.BUTTON,
}


def _enum_for_platform(name: Optional[str]) -> list[Platform]:
    if not name:
        return []
    plat = _PLATFORM_ENUM.get(name)
    return [plat] if plat else []


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    version = getattr(entry, "version", 1)

    if version < CONFIG_ENTRY_VERSION:
        data = dict(entry.data or {})
        options = dict(entry.options or {})

        if version < 2:
            for k in (
                CONF_BATTERY_ENTITY,
                CONF_ATTRIBUTE_SENSORS,
                CONF_COMBINE,
                CONF_COMBINE_ENTITY,
                CONF_COMBINE_ATTR_NAME,
                CONF_HYPHENATE_STATE,
                CONF_PRESENCE_HELPER,
            ):
                if k in data and k not in options:
                    options[k] = data.pop(k)

            if CONF_COMBINE_PRECISION in data and CONF_COMBINE_LABEL_PRECISION not in options:
                options[CONF_COMBINE_LABEL_PRECISION] = data.pop(CONF_COMBINE_PRECISION)
            if CONF_COMBINE_PRECISION in options and CONF_COMBINE_LABEL_PRECISION not in options:
                options[CONF_COMBINE_LABEL_PRECISION] = options.pop(CONF_COMBINE_PRECISION)

        if version < 3:
            if CONF_ADDRESS_FIELDS not in data:
                # Default ALL fields selected by default (your request)
                data[CONF_ADDRESS_FIELDS] = list(DEFAULT_ADDRESS_FIELDS)

        entry.version = CONFIG_ENTRY_VERSION
        hass.config_entries.async_update_entry(entry, data=data, options=options)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"entry": entry}

    platforms = _enum_for_platform(entry.data.get(CONF_PLATFORM))
    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)

    async def _on_update(hass: HomeAssistant, entry: ConfigEntry):
        opts = dict(entry.options or {})
        pending = opts.get(OPT_APPLY_DATA_UPDATE)

        if isinstance(pending, dict) and isinstance(pending.get("data"), dict):
            new_data = dict(entry.data or {})
            for k, v in pending["data"].items():
                if k in DATA_MUTABLE_KEYS:
                    new_data[k] = v
            opts.pop(OPT_APPLY_DATA_UPDATE, None)
            hass.config_entries.async_update_entry(entry, data=new_data, options=opts)

        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_on_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    platforms = _enum_for_platform(entry.data.get(CONF_PLATFORM))
    unload_ok = True
    if platforms:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def async_get_options_flow(config_entry: ConfigEntry):
    from .options_flow import CustomEntityOptionsFlow
    return CustomEntityOptionsFlow(config_entry)
