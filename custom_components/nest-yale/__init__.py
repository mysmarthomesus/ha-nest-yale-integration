import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, PLATFORMS, DESCRIPTOR_FILE_PATH
from .coordinator import NestYaleCoordinator
from .auth import NestAuth
from .api_client import APIClient
from .protobuf_manager import ProtobufManager
from .device_parser import DeviceParser

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Nest Yale from a config entry."""
    issue_token = entry.data["issue_token"]
    api_key = entry.data["api_key"]
    cookies = entry.data["cookies"]

    auth = NestAuth(None, issue_token, api_key, cookies)
    api_client = APIClient(auth)
    protobuf_manager = ProtobufManager(DESCRIPTOR_FILE_PATH)
    await protobuf_manager.load_descriptor()
    device_parser = DeviceParser(protobuf_manager)
    coordinator = NestYaleCoordinator(hass, api_client, device_parser)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_unload()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)