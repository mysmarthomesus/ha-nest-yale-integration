import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .api_client import NestAPIClient
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
            
            try:
                # Validate credentials asynchronously
                await self._validate_credentials(user_input)

                return self.async_create_entry(title="Nest Yale", data=user_input)

            except ValueError as e:
                _LOGGER.error(f"Invalid credentials: {e}")
                errors["base"] = "auth_failure"
            except Exception as e:
                _LOGGER.error(f"Unexpected config flow error: {e}")
                errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(),
            errors=errors
        )

    async def _validate_credentials(self, user_input):
        """Validate API credentials asynchronously."""
        try:
            # Create and test the API client
            api_client = await NestAPIClient.create(
                self.hass,
                issue_token=user_input[CONF_ISSUE_TOKEN],
                api_key=user_input[CONF_API_KEY],
                cookies=user_input[CONF_COOKIES]
            )
            # If we get here, credentials are valid
            await api_client.close()
        except Exception as e:
            _LOGGER.error(f"Credential validation failed: {e}")
            raise ValueError(f"Invalid credentials: {e}")

    @staticmethod
    @callback
    def _get_schema():
        """Return the data schema for the config flow form."""
        return vol.Schema(
            {
                vol.Required(CONF_ISSUE_TOKEN): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_COOKIES): str,
            }
        )