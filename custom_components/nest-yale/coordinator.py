import asyncio
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

class NestCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_client):
        super().__init__(hass, _LOGGER, name="Nest Yale", update_interval=UPDATE_INTERVAL)
        self.api_client = api_client
        self.data = {"devices": {"locks": {}}, "user_id": None}
        self._observer_task = None

    async def _async_update_data(self):
        """Update data from the stream."""
        await self.api_client.observe()
        self.data = await self.api_client.refresh_state()
        _LOGGER.debug(f"Updated coordinator data: {self.data}")
        return self.data

    async def async_setup(self):
        """Setup the coordinator with initial device data."""
        await self.api_client.async_setup()
        self.data = await self.api_client.refresh_state()
        _LOGGER.debug(f"Initial coordinator data: {self.data}")
        self.async_set_updated_data(self.data)
        self._observer_task = self.hass.async_create_task(self._run_observer())

    async def _run_observer(self):
        """Run the observer loop to stream updates."""
        while True:
            try:
                if not self.api_client.connection.connected:
                    _LOGGER.debug("Re-initializing API client connection")
                    await self.api_client.async_setup()
                    await self.api_client.authenticate()
                async for update in self.api_client.observe():
                    self.data = update
                    self.async_set_updated_data(self.data)
                    _LOGGER.debug(f"Stream updated coordinator data: {self.data}")
                    await asyncio.sleep(0.1)  # Prevent tight loop
            except Exception as e:
                _LOGGER.error(f"Observer error: {e}, retrying in 10 seconds")
                await asyncio.sleep(10)

    async def async_unload(self):
        if self._observer_task:
            self._observer_task.cancel()
            try:
                await self._observer_task
            except asyncio.CancelledError:
                pass