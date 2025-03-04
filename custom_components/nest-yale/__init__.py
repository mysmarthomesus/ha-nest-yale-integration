#__init__.py
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, PLATFORMS
from .api_client import NestAPIClient
from .coordinator import NestCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nest Yale Lock from a config entry."""
    _LOGGER.debug("Setting up Nest Yale Lock integration.")

    issue_token = entry.data.get("issue_token")
    api_key = entry.data.get("api_key")
    cookies = entry.data.get("cookies")

    if not issue_token or not api_key or not cookies:
        _LOGGER.error("Missing required authentication credentials. Setup failed.")
        return False

    conn = await NestAPIClient.create(hass, issue_token, api_key, cookies)  # Use create()
    await conn.authenticate()

    coordinator = NestCoordinator(hass, conn)
    await coordinator.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Nest Yale Lock integration successfully set up.")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Nest Yale Lock integration.")

    coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        await coordinator.api_client.close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)