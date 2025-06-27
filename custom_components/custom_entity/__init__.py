from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    platform = entry.data.get("platform")
    if platform:
        await hass.config_entries.async_forward_entry_setup(entry, platform)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    platform = entry.data.get("platform")
    if platform:
        return await hass.config_entries.async_forward_entry_unload(entry, platform)
    return True
