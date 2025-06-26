import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    CONF_FRIENDLY_NAME,
    CONF_SOURCE_ENTITY,
    CONF_COMBINE,
    CONF_COMBINE_ENTITY,
    CONF_COMBINE_ATTR_NAME,
)
from .options_flow import CustomEntityOptionsFlow

class CustomEntityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Custom Entity."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step: ask for name, source entity, and combine toggle."""
        if user_input is not None:
            self._data = {
                CONF_FRIENDLY_NAME: user_input[CONF_FRIENDLY_NAME],
                CONF_SOURCE_ENTITY:  user_input[CONF_SOURCE_ENTITY],
                CONF_COMBINE:         user_input.get(CONF_COMBINE, False),
            }
            if self._data[CONF_COMBINE]:
                return await self.async_step_combine()
            return self.async_create_entry(
                title=self._data[CONF_FRIENDLY_NAME],
                data=self._data
            )

        schema = vol.Schema({
            vol.Required(CONF_FRIENDLY_NAME): str,
            vol.Required(CONF_SOURCE_ENTITY): selector(
                {"entity": {"domain": ["device_tracker", "person"]}}
            ),
            vol.Optional(CONF_COMBINE, default=False): bool,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_combine(self, user_input=None):
        """If combine=True, ask for the sensor and attribute name."""
        if user_input is not None:
            self._data[CONF_COMBINE_ENTITY]    = user_input[CONF_COMBINE_ENTITY]
            self._data[CONF_COMBINE_ATTR_NAME] = user_input[CONF_COMBINE_ATTR_NAME]
            return self.async_create_entry(
                title=self._data[CONF_FRIENDLY_NAME],
                data=self._data
            )

        schema = vol.Schema({
            vol.Required(CONF_COMBINE_ENTITY): selector(
                {"entity": {"domain": "sensor"}}
            ),
            vol.Required(CONF_COMBINE_ATTR_NAME, default=""): str,
        })
        return self.async_show_form(step_id="combine", data_schema=schema)

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry):
        """Delegate to options flow."""
        return CustomEntityOptionsFlow(config_entry)
