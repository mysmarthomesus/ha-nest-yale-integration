import logging
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .auth import NestAuth
from .protobuf_manager import ProtobufManager
from .api_client import APIClient
from .device_parser import DeviceParser
from .coordinator import NestYaleCoordinator
from .const import DOMAIN, DESCRIPTOR_FILE_PATH, CONF_ISSUE_TOKEN, CONF_API_KEY, CONF_COOKIES, parse_cookies

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nest Yale from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    async with aiohttp.ClientSession() as session:
        auth = NestAuth(session, entry.data[CONF_ISSUE_TOKEN], entry.data[CONF_API_KEY], parse_cookies(entry.data[CONF_COOKIES]))
        await auth.authenticate()
        protobuf_manager = ProtobufManager(DESCRIPTOR_FILE_PATH)
        await protobuf_manager.load_descriptor()
        api_client = APIClient(session, auth)
        device_parser = DeviceParser(protobuf_manager)
        coordinator = NestYaleCoordinator(hass, api_client, device_parser)
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}  # Store as dict for clarity
    await hass.config_entries.async_forward_entry_setups(entry, ["lock"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, ["lock"]):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False