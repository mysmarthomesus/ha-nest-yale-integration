import logging
import asyncio
from homeassistant.components.lock import LockEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Nest Yale Lock entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Use coordinator data directly, no blocking refresh
    locks_data = coordinator.data.get("devices", {}).get("locks", {})
    _LOGGER.debug(f"Initial lock data from coordinator: {locks_data}")

    locks = []
    for device_id, device in locks_data.items():
        if not isinstance(device, dict):
            _LOGGER.warning(f"Invalid device entry for {device_id}: {device}")
            continue
        if "device_id" not in device:
            device["device_id"] = device_id
            _LOGGER.debug(f"Added device_id {device_id} to device: {device}")
        locks.append(NestYaleLock(coordinator, device))

    if locks:
        _LOGGER.info(f"Setting up {len(locks)} Nest Yale locks")
        async_add_entities(locks)
    else:
        _LOGGER.info("No locks found in initial coordinator data; waiting for updates")

class NestYaleLock(LockEntity):
    """Representation of a Nest Yale Lock entity."""

    def __init__(self, coordinator, device):
        """Initialize the lock entity."""
        self._coordinator = coordinator
        self._device = device.copy()  # Avoid modifying shared dict
        self._attr_unique_id = device.get("device_id", f"nest_yale_unknown_{id(self)}")
        self._attr_name = device.get("name", f"Nest Yale Lock {self._attr_unique_id[-4:]}")
        _LOGGER.debug(f"Initialized lock: unique_id={self._attr_unique_id}, device={self._device}")

    @property
    def is_locked(self):
        """Return True if the lock is locked."""
        state = self._device.get("bolt_locked") or self._device.get("state") == "BOLT_STATE_EXTENDED"
        return state if state is not None else False

    @property
    def is_locking(self):
        """Return True if the lock is in the process of locking."""
        return self._device.get("bolt_moving", False) and self._device.get("bolt_moving_to", False)

    @property
    def is_unlocking(self):
        """Return True if the lock is in the process of unlocking."""
        return self._device.get("bolt_moving", False) and not self._device.get("bolt_moving_to", False)

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        return {
            "battery_status": self._device.get("battery_status"),
            "battery_voltage": self._device.get("battery_voltage")
        }

    async def async_lock(self, **kwargs):
        """Lock the device."""
        cmd = {
            "traitLabel": "bolt_lock",
            "command": {
                "type_url": "type.nestlabs.com/weave.trait.security.BoltLockTrait.BoltLockChangeRequest",
                "value": {
                    "state": "BOLT_STATE_EXTENDED",
                    "boltLockActor": {
                        "method": "BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_EXPLICIT",
                        "originator": {"resourceId": self._coordinator.api_client.userid or "unknown"}
                    }
                }
            }
        }
        await self._coordinator.api_client.send_command(cmd, f"DEVICE_{self._attr_unique_id}")
        self._device["bolt_moving"] = True
        self._device["bolt_moving_to"] = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        cmd = {
            "traitLabel": "bolt_lock",
            "command": {
                "type_url": "type.nestlabs.com/weave.trait.security.BoltLockTrait.BoltLockChangeRequest",
                "value": {
                    "state": "BOLT_STATE_RETRACTED",
                    "boltLockActor": {
                        "method": "BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_EXPLICIT",
                        "originator": {"resourceId": self._coordinator.api_client.userid or "unknown"}
                    }
                }
            }
        }
        await self._coordinator.api_client.send_command(cmd, f"DEVICE_{self._attr_unique_id}")
        self._device["bolt_moving"] = True
        self._device["bolt_moving_to"] = False
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity addition to Home Assistant."""
        @callback
        def update_listener():
            new_data = self._coordinator.data["devices"]["locks"].get(self._attr_unique_id)
            if new_data:
                self._device.clear()
                self._device.update(new_data)
                self.async_write_ha_state()
            else:
                _LOGGER.debug(f"No updated data for lock {self._attr_unique_id} in {self._coordinator.data}")
        self.async_on_remove(
            self._coordinator.async_add_listener(update_listener)
        )

    @property
    def available(self):
        """Return True if entity is available."""
        state = self._device.get("bolt_locked") or self._device.get("state")
        available = bool(self._device)  # Available if device data exists
        if not available:
            _LOGGER.debug(f"Lock {self._attr_unique_id} unavailable: {self._device}")
        return available