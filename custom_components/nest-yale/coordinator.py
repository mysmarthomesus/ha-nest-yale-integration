import asyncio
import logging
import os
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import ENDPOINT_OBSERVE, API_SUBSCRIBE_DELAY_SECONDS, API_RETRY_DELAY_SECONDS

_LOGGER = logging.getLogger(__name__)

class NestYaleCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_client, device_parser):
        super().__init__(
            hass,
            _LOGGER,
            name="Nest Yale",
            update_interval=timedelta(seconds=API_SUBSCRIBE_DELAY_SECONDS),
        )
        self.api_client = api_client
        self.device_parser = device_parser
        self.devices = []

    async def _async_update_data(self):
        """Fetch data from the Nest API."""
        try:
            proto_path = os.path.join(os.path.dirname(__file__), "ObserveTraits.protobuf")
            loop = asyncio.get_running_loop()
            with open(proto_path, "rb") as f:
                serialized_request = await loop.run_in_executor(None, f.read)
            _LOGGER.debug(f"Loaded ObserveTraits.protobuf, serialized: {serialized_request.hex()}")

            response_data = await self.api_client.send_protobuf_request(ENDPOINT_OBSERVE, serialized_request)
            self.devices = self.device_parser.parse_devices(response_data)
            return self.devices
        except FileNotFoundError as e:
            _LOGGER.error(f"ObserveTraits.protobuf not found at {proto_path}. Please ensure the file exists.")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to update data: {e}", exc_info=True)
            await asyncio.sleep(API_RETRY_DELAY_SECONDS)
            raise

    async def async_unload(self):
        await self.api_client.close()