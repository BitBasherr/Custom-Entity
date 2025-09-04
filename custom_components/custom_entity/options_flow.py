"""Options flow for Custom Entity."""
from __future__ import annotations

import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_SENSORS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
    CONF_HYPHENATE_STATE,
    CONF_PRESENCE_HELPER,  # <-- Added missing constant
    SELECT_ANY_ENTITY,      # <-- Added missing selector
)

_LOGGER = logging.getLogger(__name__)
ENTITY_SENSOR = selector({"entity": {"domain": "sensor"}})


class CustomEntityOptionsFlow(config_entries.OptionsFlow):
    """Edit battery, combine, hyphenate, extra sensors."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry
        self._opts: dict = dict(entry.options or {})
        self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})
        self._pending_entity: str | None = None

    # ── 1: battery & combine toggle ───────────────────────────────────
    async def async_step_init(self, user_input=None):
        if user_input:
            # battery
            if user_input.get(CONF_BATTERY_ENTITY):
                self._opts[CONF_BATTERY_ENTITY] = user_input[CONF_BATTERY_ENTITY]
            else:
                self._opts.pop(CONF_BATTERY_ENTITY, None)

            # combine toggle + hyphenate flag
            # helper boolean (optional)
            if user_input.get(CONF_PRESENCE_HELPER):
                self._opts[CONF_PRESENCE_HELPER] = user_input[CONF_PRESENCE_HELPER]
            else:
                self._opts.pop(CONF_PRESENCE_HELPER, None)

            # combine toggle + hyphenate flag
            self._opts[CONF_COMBINE] = user_input.get(CONF_COMBINE, False)
            self._opts[CONF_HYPHENATE_STATE] = user_input.get(CONF_HYPHENATE_STATE, False)

            if self._opts[CONF_COMBINE]:
                return await self.async_step_combine()
            return await self.async_step_attr_menu()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_BATTERY_ENTITY, default=self._opts.get(CONF_BATTERY_ENTITY)): ENTITY_SENSOR,
                vol.Required(CONF_COMBINE, default=self._opts.get(CONF_COMBINE, False)): bool,
                vol.Optional(CONF_HYPHENATE_STATE, default=self._opts.get(CONF_HYPHENATE_STATE, False)): bool,
                # show helper only if this entry is a tracker
                vol.Optional(CONF_PRESENCE_HELPER, default=self._opts.get(CONF_PRESENCE_HELPER)):
                    SELECT_ANY_ENTITY
            }),
        )

    # ── 2: combine details ────────────────────────────────────────────
    async def async_step_combine(self, user_input=None):
        if user_input:
            self._opts.update({
                CONF_COMBINE_ENTITY:    user_input[CONF_COMBINE_ENTITY],
                CONF_COMBINE_ATTR_NAME: user_input[CONF_COMBINE_ATTR_NAME],
                CONF_HYPHENATE_STATE:   user_input.get(CONF_HYPHENATE_STATE, False),
            })
            return await self.async_step_attr_menu()

        return self.async_show_form(
            step_id="combine",
            data_schema=vol.Schema({
                vol.Required(CONF_COMBINE_ENTITY, default=self._opts.get(CONF_COMBINE_ENTITY)): ENTITY_SENSOR,
                vol.Required(CONF_COMBINE_ATTR_NAME, default=self._opts.get(CONF_COMBINE_ATTR_NAME, "combine")): str,
                vol.Optional(CONF_HYPHENATE_STATE, default=self._opts.get(CONF_HYPHENATE_STATE, False)): bool,
            }),
        )

    # ── 3: attribute menu ────────────────────────────────────────────
    async def async_step_attr_menu(self, user_input=None):
        if user_input:
            choice = user_input.get("choice")
            if not choice or choice == "done":
                return self.async_create_entry(title="", data=self._opts)

            if choice == "add":
                return await self.async_step_attr_pick_entity()

            if choice.startswith("del__"):
                friendly = choice[5:]
                self._opts[CONF_ATTRIBUTE_SENSORS].pop(friendly, None)

        buttons = {
            "done": "✅ Done",
            "add":  "➕ Add attribute",
            **{
                f"del__{k}": f"🗑️ Remove “{k}”"
                for k in sorted(self._opts[CONF_ATTRIBUTE_SENSORS])
            },
        }

        return self.async_show_form(
            step_id="attr_menu",
            data_schema=vol.Schema({vol.Optional("choice"): vol.In(buttons)}),
            description_placeholders={
                "current": ", ".join(self._opts[CONF_ATTRIBUTE_SENSORS]) or "none"
            },
        )

    # add attribute sensor
    async def async_step_attr_pick_entity(self, user_input=None):
        if user_input:
            self._pending_entity = user_input["entity"]
            return await self.async_step_attr_pick_name()

        return self.async_show_form(
            step_id="attr_pick_entity",
            data_schema=vol.Schema({vol.Required("entity"): ENTITY_SENSOR}),
        )

    async def async_step_attr_pick_name(self, user_input=None):
        if user_input:
            friendly = user_input["name"].strip()
            self._opts[CONF_ATTRIBUTE_SENSORS][friendly] = self._pending_entity
            self._pending_entity = None
            return await self.async_step_attr_menu()

        return self.async_show_form(
            step_id="attr_pick_name",
            data_schema=vol.Schema({vol.Required("name"): str}),
        )

    # ── compatibility for HA ≤ 2025.6 ────────────────────────────────
    @callback
    def async_get_result(self):
        return self._opts
