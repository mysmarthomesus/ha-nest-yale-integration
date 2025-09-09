"""Config flow for Nest Yale integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN, CONF_ISSUE_TOKEN, CONF_API_KEY, CONF_COOKIES

_LOGGER = logging.getLogger(__name__)


class NestYaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nest Yale integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # For now, just create the entry without validation
            # TODO: Add credential validation
            return self.async_create_entry(
                title="Nest Yale Lock",
                data=user_input
            )

        data_schema = vol.Schema({
            vol.Required(CONF_ISSUE_TOKEN, default=""): str,
            vol.Required(CONF_API_KEY, default=""): str,
            vol.Required(CONF_COOKIES, default=""): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )