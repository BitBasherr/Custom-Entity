"""Wizard-style Options flow for Custom Entity (with ✅ Done button)."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BATTERY_ENTITY,
    CONF_ATTRIBUTE_SENSORS,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
)

_LOGGER = logging.getLogger(__name__)
ENTITY_SENSOR = selector({"entity": {"domain": "sensor"}})


class CustomEntityOptionsFlow(config_entries.OptionsFlow):
    """Interactive wizard for editing Custom Entity options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        try:
            super().__init__(entry)       # HA < 2025.7
            self._entry = self.config_entry
        except TypeError:
            super().__init__()            # HA ≥ 2025.7
            self._entry = entry

        self._opts: dict = dict(self._entry.options or {})
        self._opts.setdefault(CONF_ATTRIBUTE_SENSORS, {})
        self._pending_entity: str | None = None

    # ------------------------------------------------------------------
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            if ent := user_input.get(CONF_BATTERY_ENTITY):
                self._opts[CONF_BATTERY_ENTITY] = ent
            else:
                self._opts.pop(CONF_BATTERY_ENTITY, None)

            self._opts[CONF_COMBINE] = user_input.get(CONF_COMBINE, False)
            if self._opts[CONF_COMBINE]:
                return await self.async_step_combine()
            return await self.async_step_attr_menu()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BATTERY_ENTITY): ENTITY_SENSOR,
                    vol.Required(
                        CONF_COMBINE,
                        default=self._opts.get(CONF_COMBINE, False),
                    ): bool,
                }
            ),
        )

    # ------------------------------------------------------------------
    async def async_step_combine(self, user_input=None):
        if user_input is not None:
            self._opts[CONF_COMBINE_ENTITY] = user_input[CONF_COMBINE_ENTITY]
            self._opts[CONF_COMBINE_ATTR_NAME] = user_input[CONF_COMBINE_ATTR_NAME]
            return await self.async_step_attr_menu()

        return self.async_show_form(
            step_id="combine",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COMBINE_ENTITY,
                        default=self._opts.get(CONF_COMBINE_ENTITY, ""),
                    ): ENTITY_SENSOR,
                    vol.Required(
                        CONF_COMBINE_ATTR_NAME,
                        default=self._opts.get(CONF_COMBINE_ATTR_NAME, ""),
                    ): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    async def async_step_attr_menu(self, user_input=None):
        """Show list of attributes; add/remove or finish."""
        # --------- POST -------------------------------------------------
        if user_input is not None:
            # Empty submit or explicit "done"
            if not user_input or user_input.get("choice") == "done":
                return self.async_create_entry(title="", data=self._opts)

            action = user_input["choice"]
            if action == "add":
                return await self.async_step_attr_pick_entity()

            # delete
            friendly = action[5:]
            self._opts[CONF_ATTRIBUTE_SENSORS].pop(friendly, None)

        # --------- GET --------------------------------------------------
        buttons: dict[str, str] = {
            "done": "✅  Done",
            "add":  "➕  Add attribute",
        }
        for friendly in sorted(self._opts[CONF_ATTRIBUTE_SENSORS]):
            buttons[f"del__{friendly}"] = f"🗑️  Remove “{friendly}”"

        return self.async_show_form(
            step_id="attr_menu",
            data_schema=vol.Schema(
                {vol.Optional("choice"): vol.In(buttons)}
            ),
            description_placeholders={
                "current": ", ".join(self._opts[CONF_ATTRIBUTE_SENSORS]) or "none",
            },
        )

    # ------------------------------------------------------------------
    async def async_step_attr_pick_entity(self, user_input=None):
        if user_input is not None:
            self._pending_entity = user_input["entity"]
            return await self.async_step_attr_pick_name()

        return self.async_show_form(
            step_id="attr_pick_entity",
            data_schema=vol.Schema({vol.Required("entity"): ENTITY_SENSOR}),
        )

    async def async_step_attr_pick_name(self, user_input=None):
        if user_input is not None:
            friendly = user_input["name"].strip()
            self._opts[CONF_ATTRIBUTE_SENSORS][friendly] = self._pending_entity
            self._pending_entity = None
            return await self.async_step_attr_menu()

        return self.async_show_form(
            step_id="attr_pick_name",
            data_schema=vol.Schema({vol.Required("name"): str}),
        )

    # ------------------------------------------------------------------
    @callback
    def async_get_result(self):
        return self._opts

    async_step_attr_menu.last_step = True  # type: ignore[attr-defined]
