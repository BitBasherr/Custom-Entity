from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """No YAML setup needed."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the device_tracker platform and register option-update listener."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward to platform
    await hass.config_entries.async_forward_entry_setups(entry, ["r"])

    # ----- NEW: reload entity when options change --------------------
    async def _reload_on_update(hass: HomeAssistant, entry: ConfigEntry):
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_reload_on_update))
    # -----------------------------------------------------------------

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the platform and cleanup."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["device_tracker"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
