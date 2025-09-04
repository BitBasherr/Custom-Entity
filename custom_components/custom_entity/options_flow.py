"""Options flow for Custom Entity."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ATTRIBUTE_SENSORS,
    CONF_BATTERY_ENTITY,
    CONF_COMBINE,
    CONF_COMBINE_ATTR_NAME,
    CONF_COMBINE_ATTR_PRECISION,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_LABEL_PRECISION,
    CONF_COMBINE_PRECISION,  # legacy
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,
    DEFAULT_COMBINE_PRECISION,
    SELECT_ANY_ENTITY,
    SELECT_BOOLEANISH,
    SELECT_PRECISION,
    SELECT_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


class CustomEntityOptionsFlow(config_entries.OptionsFlow):
    """Edit battery, combine, hyphenate, precision, extras."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry
        # Start from saved options; never lose unknown keys
        self._opts: dict = dict(entry.options or {})
        self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})
        self._pending_entity: str | None = None

        # Back-compat migration (read once)
        if (
            CONF_COMBINE_PRECISION in self._opts
            and CONF_COMBINE_LABEL_PRECISION not in self._opts
        ):
            self._opts[CONF_COMBINE_LABEL_PRECISION] = self._opts.get(
                CONF_COMBINE_PRECISION, DEFAULT_COMBINE_PRECISION
            )

    # ──────────────────────────────────────────────────────────────────────
    # 1) Base options (battery/helper/toggles)
    # ──────────────────────────────────────────────────────────────────────
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # battery (optional)
            if user_input.get(CONF_BATTERY_ENTITY):
                self._opts[CONF_BATTERY_ENTITY] = user_input[CONF_BATTERY_ENTITY]
            else:
                self._opts.pop(CONF_BATTERY_ENTITY, None)

            # presence helper (optional)
            if user_input.get(CONF_PRESENCE_HELPER):
                self._opts[CONF_PRESENCE_HELPER] = user_input[CONF_PRESENCE_HELPER]
            else:
                self._opts.pop(CONF_PRESENCE_HELPER, None)

            # combine + hyphenate
            self._opts[CONF_COMBINE] = bool(user_input.get(CONF_COMBINE, False))
            self._opts[CONF_HYPHENATE_STATE] = bool(
                user_input.get(CONF_HYPHENATE_STATE, False)
            )

            # Next step (only needed if combining)
            if self._opts[CONF_COMBINE]:
                return await self.async_step_combine()

            # Otherwise finish
            return self.async_create_entry(title="", data=self._opts)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BATTERY_ENTITY, default=self._opts.get(CONF_BATTERY_ENTITY, "")
                ): SELECT_ANY_ENTITY,
                vol.Optional(
                    CONF_PRESENCE_HELPER, default=self._opts.get(CONF_PRESENCE_HELPER, "")
                ): SELECT_BOOLEANISH,
                vol.Optional(
                    CONF_COMBINE, default=self._opts.get(CONF_COMBINE, False)
                ): bool,
                vol.Optional(
                    CONF_HYPHENATE_STATE,
                    default=self._opts.get(CONF_HYPHENATE_STATE, False),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    # ──────────────────────────────────────────────────────────────────────
    # 2) Combine target + precisions + optional attr name
    # ──────────────────────────────────────────────────────────────────────
    async def async_step_combine(self, user_input=None):
        if user_input is not None:
            # required combine entity
            self._opts[CONF_COMBINE_ENTITY] = user_input[CONF_COMBINE_ENTITY]

            # label precision (0–3) used when hyphenating
            self._opts[CONF_COMBINE_LABEL_PRECISION] = user_input.get(
                CONF_COMBINE_LABEL_PRECISION,
                self._opts.get(CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION),
            )

            # attribute precision (0–3) used when NOT hyphenating
            self._opts[CONF_COMBINE_ATTR_PRECISION] = user_input.get(
                CONF_COMBINE_ATTR_PRECISION,
                self._opts.get(CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION),
            )

            # attribute name (used only when NOT hyphenating)
            attr_name = user_input.get(CONF_COMBINE_ATTR_NAME, "").strip()
            if attr_name:
                self._opts[CONF_COMBINE_ATTR_NAME] = attr_name
            else:
                self._opts.pop(CONF_COMBINE_ATTR_NAME, None)

            return self.async_create_entry(title="", data=self._opts)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_COMBINE_ENTITY,
                    default=self._opts.get(CONF_COMBINE_ENTITY, ""),
                ): SELECT_SENSOR,
                vol.Optional(
                    CONF_COMBINE_LABEL_PRECISION,
                    default=self._opts.get(
                        CONF_COMBINE_LABEL_PRECISION, DEFAULT_COMBINE_PRECISION
                    ),
                ): SELECT_PRECISION,
                vol.Optional(
                    CONF_COMBINE_ATTR_PRECISION,
                    default=self._opts.get(
                        CONF_COMBINE_ATTR_PRECISION, DEFAULT_COMBINE_PRECISION
                    ),
                ): SELECT_PRECISION,
                vol.Optional(
                    CONF_COMBINE_ATTR_NAME,
                    default=self._opts.get(CONF_COMBINE_ATTR_NAME, ""),
                ): str,
            }
        )
        return self.async_show_form(step_id="combine", data_schema=schema)

    # ──────────────────────────────────────────────────────────────────────
    # Older HA versions expect this helper
    # ──────────────────────────────────────────────────────────────────────
    @callback
    def async_get_result(self):
        return self._opts
