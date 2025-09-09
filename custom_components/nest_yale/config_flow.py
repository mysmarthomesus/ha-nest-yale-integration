"""Config flow for Nest Yale integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, CONF_ISSUE_TOKEN, CONF_API_KEY, CONF_COOKIES

_LOGGER = logging.getLogger(__name__)


class NestYaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Nest Yale."""

    VERSION = 1

    async def async_step_user(self, user_input=None):  # type: ignore[override]
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            try:
                # Basic presence validation (full auth happens later in async_setup_entry)
                for key in (CONF_ISSUE_TOKEN, CONF_API_KEY, CONF_COOKIES):
                    if not user_input.get(key):
                        raise ValueError(f"Missing {key}")
                return self.async_create_entry(title="Nest Yale", data=user_input)
            except ValueError:
                errors["base"] = "auth_failure"
            except Exception as err:  # pragma: no cover
                _LOGGER.exception("Unexpected error during config flow: %s", err)
                errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def _schema():
        return vol.Schema(
            {
                vol.Required(CONF_ISSUE_TOKEN): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_COOKIES): str,
            }
        )