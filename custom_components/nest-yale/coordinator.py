#coordinator.py
import asyncio
import logging
from datetime import timedelta  # Add this import
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)  # Use timedelta instead of int

class NestCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_client):
        """Initialize the Nest update coordinator."""
        super().__init__(hass, _LOGGER, name="Nest Yale", update_interval=UPDATE_INTERVAL)
        self.api_client = api_client
        self.data = {"devices": {"locks": {}}, "user_id": None}
        self._observer_task = None

    async def _async_update_data(self):
        """Fetch data periodically."""
        try:
            # Fetch latest state
            locks_data = await self.api_client.refresh_state()
            if locks_data:
                self.data["devices"]["locks"] = locks_data
                self.data["user_id"] = self.api_client.userid
            return self.data
        except Exception as e:
            _LOGGER.error(f"Update error: {e}")
            raise

    async def async_setup(self):
        """Set up the coordinator."""
        # Ensure API client is initialized
        await self.api_client.async_setup()

        # Fetch initial state
        try:
            async with asyncio.timeout(60):
                locks_data = await self.api_client.refresh_state()
                if locks_data:
                    self.data["devices"]["locks"] = locks_data
                    self.data["user_id"] = self.api_client.userid
                    self.async_set_updated_data(self.data)
                    _LOGGER.debug(f"Initial lock data set: {self.data}")
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching initial lock data")
        except Exception as e:
            _LOGGER.error(f"Initial setup error: {e}")

        # Start observer in background
        self._observer_task = self.hass.async_create_task(self._run_observer())

    async def _run_observer(self):
        """Continuously listen for lock updates from the Nest API."""
        while True:
            try:
                if not self.api_client.connection.connected:
                    _LOGGER.debug("Re-initializing API client connection")
                    await self.api_client.async_setup()
                    await self.api_client.authenticate()
                async for locks_data in self.api_client.observe():
                    if locks_data:
                        self.data["devices"]["locks"] = locks_data
                        self.data["user_id"] = self.api_client.userid
                        self.async_set_updated_data(self.data)
                        _LOGGER.debug(f"Stream updated coordinator data: {self.data}")
            except Exception as e:
                _LOGGER.error(f"Observer error: {e}, retrying in 10 seconds")
                await asyncio.sleep(10)

    async def async_unload(self):
        """Unload the coordinator."""
        if self._observer_task:
            self._observer_task.cancel()
            try:
                await self._observer_task
            except asyncio.CancelledError:
                pass