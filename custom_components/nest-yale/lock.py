import logging
from homeassistant.components.lock import LockEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Nest Yale lock from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    devices = coordinator.data or []  # Default to empty list if None
    _LOGGER.debug(f"Coordinator data: {devices}")
    locks = [NestYaleLock(coordinator, device) for device in devices if device.get("has_lock")]
    if locks:
        _LOGGER.info(f"Setting up {len(locks)} Nest Yale locks")
        async_add_entities(locks)
    else:
        _LOGGER.warning("No locks found in coordinator data")

class NestYaleLock(LockEntity):
    """Representation of a Nest Yale lock."""
    def __init__(self, coordinator, device):
        self.coordinator = coordinator
        self.device = device
        self._attr_unique_id = device["device_id"]
        self._attr_name = device["name"]

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return True  # Placeholder; update with actual state from coordinator.data

    async def async_lock(self, **kwargs):
        """Lock the device."""
        _LOGGER.debug(f"Locking {self._attr_name}")
        # Implement lock command here

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        _LOGGER.debug(f"Unlocking {self._attr_name}")
        # Implement unlock command here

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success