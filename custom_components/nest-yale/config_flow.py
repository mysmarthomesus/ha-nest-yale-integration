import voluptuous as vol
import logging
import os
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from .const import (
    DOMAIN,
    CONF_ISSUE_TOKEN,
    CONF_API_KEY,
    CONF_COOKIES,
    DESCRIPTOR_FILE_PATH,
    ENDPOINT_OBSERVE,
    parse_cookies
)
from .auth import NestAuth
from .protobuf_manager import ProtobufManager
from .api_client import APIClient
from .device_parser import DeviceParser
from .coordinator import NestYaleCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME, default="Nest Yale Lock"): str,
    vol.Required(CONF_ISSUE_TOKEN): str,
    vol.Required(CONF_API_KEY): str,
    vol.Required(CONF_COOKIES): str,
})

class NestYaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nest Yale Lock."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                issue_token = user_input[CONF_ISSUE_TOKEN]
                api_key = user_input[CONF_API_KEY]
                cookies = parse_cookies(user_input[CONF_COOKIES])
                auth = NestAuth(None, issue_token, api_key, cookies)  # No session needed
                await auth.authenticate()
                protobuf_manager = ProtobufManager(DESCRIPTOR_FILE_PATH)
                await protobuf_manager.load_descriptor()
                api_client = APIClient(auth)  # No session
                device_parser = DeviceParser(protobuf_manager)
                proto_path = os.path.join(os.path.dirname(__file__), "ObserveTraits.protobuf")
                loop = asyncio.get_running_loop()
                with open(proto_path, "rb") as f:
                    serialized_request = await loop.run_in_executor(None, f.read)
                _LOGGER.debug(f"Loaded ObserveTraits.protobuf in config flow, serialized: {serialized_request.hex()}")
                response_data = await api_client.send_protobuf_request(ENDPOINT_OBSERVE, serialized_request)
                devices = device_parser.parse_devices(response_data)
                _LOGGER.debug(f"Devices found during setup: {devices}")
                await api_client.close()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
            except FileNotFoundError as e:
                _LOGGER.error(f"ObserveTraits.protobuf not found at {proto_path}. Please ensure the file exists.")
                errors["base"] = "file_not_found"
            except Exception as e:
                _LOGGER.error(f"Unexpected error during config: {e}", exc_info=True)
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA, errors=errors)

    async def _async_find_existing_entry(self, user_input):
        """Check if an entry already exists."""
        for entry in self._async_current_entries():
            if (entry.data.get(CONF_ISSUE_TOKEN) == user_input[CONF_ISSUE_TOKEN] and
                entry.data.get(CONF_API_KEY) == user_input[CONF_API_KEY]):
                return entry
        return None