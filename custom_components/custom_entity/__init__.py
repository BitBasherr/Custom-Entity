"""Init for Custom Entity integration (with entry migration and Options→Data bridge)."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SUPPORTED_PLATFORMS,
    CONF_PLATFORM,
    # migrate keys
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_SENSORS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,
    CONF_COMBINE_PRECISION,
    CONF_COMBINE_LABEL_PRECISION,
    OPT_APPLY_DATA_UPDATE,
    DATA_MUTABLE_KEYS,
)

CONFIG_ENTRY_VERSION = 2  # bump when we migrate formats


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy entries to the latest structure without breaking IDs."""
    version = getattr(entry, "version", 1)

    if version < CONFIG_ENTRY_VERSION:
        data = dict(entry.data or {})
        options = dict(entry.options or {})

        # Move combine-related toggles from data -> options if they were stored there previously
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

        # Migrate legacy single precision to new label precision if not already present
        if CONF_COMBINE_PRECISION in data and CONF_COMBINE_LABEL_PRECISION not in options:
            options[CONF_COMBINE_LABEL_PRECISION] = data.pop(CONF_COMBINE_PRECISION)
        if CONF_COMBINE_PRECISION in options and CONF_COMBINE_LABEL_PRECISION not in options:
            options[CONF_COMBINE_LABEL_PRECISION] = options.pop(CONF_COMBINE_PRECISION)

        entry.version = CONFIG_ENTRY_VERSION
        hass.config_entries.async_update_entry(entry, data=data, options=options)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single Custom Entity entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"entry": entry}

    platform = entry.data.get(CONF_PLATFORM)
    if platform in SUPPORTED_PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, [platform])

    async def _on_update(hass: HomeAssistant, entry: ConfigEntry):
        """
        On any options update:
          • Apply requested DATA changes (if any) from options marker
          • Clean marker keys
          • Reload the entry to apply platform/source/etc. changes
        """
        # 1) Apply pending data changes requested by options flow
        opts = dict(entry.options or {})
        pending: Dict[str, Any] | None = opts.get(OPT_APPLY_DATA_UPDATE)
        if isinstance(pending, dict) and "data" in pending and isinstance(pending["data"], dict):
            new_data = dict(entry.data or {})
            for k, v in pending["data"].items():
                if k in DATA_MUTABLE_KEYS:
                    new_data[k] = v
            # Clean the marker before saving
            opts.pop(OPT_APPLY_DATA_UPDATE, None)
            hass.config_entries.async_update_entry(entry, data=new_data, options=opts)

        # 2) Always reload to reflect any changed options/platform
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_on_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a single Custom Entity entry."""
    platform = entry.data.get(CONF_PLATFORM)
    unload_ok = True
    if platform in SUPPORTED_PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, [platform])
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


# Options flow bridge
async def async_get_options_flow(config_entry: ConfigEntry):
    from .options_flow import CustomEntityOptionsFlow
    return CustomEntityOptionsFlow(config_entry)
