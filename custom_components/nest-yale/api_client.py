import aiohttp
import logging
from .const import (
    REQUEST_TIMEOUT,
    SUCCESS_STATUS_CODES,
    PRODUCTION_HOSTNAME,
    API_TIMEOUT_SECONDS,
    GRPC_HOSTNAME,
    USER_AGENT_STRING,
    ENDPOINT_OBSERVE
)

_LOGGER = logging.getLogger(__name__)

class APIClient:
    def __init__(self, session, auth):
        self.session = session
        self.auth = auth

    async def send_protobuf_request(self, endpoint, protobuf_message):
        """Send a Protobuf request with retry on auth failure."""
        if not self.auth.access_token:
            await self.auth.authenticate()

        url = f"https://{GRPC_HOSTNAME}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/x-protobuf",
            "User-Agent": USER_AGENT_STRING,
            "x-goog-api-key": self.auth.api_key,
            "X-Accept-Content-Transfer-Encoding": "binary",
            "X-Accept-Response-Streaming": "true",
            "Referer": f"https://{PRODUCTION_HOSTNAME['api_hostname']}/",
            "Origin": f"https://{PRODUCTION_HOSTNAME['api_hostname']}",
            "Accept": "application/x-protobuf.google.rpc.streambody",  # Match Homebridge streaming
        }
        serialized_request = protobuf_message.SerializeToString()
        _LOGGER.debug(f"Sending request to {url} with data: {serialized_request.hex()}")

        async with self.session.post(
            url, headers=headers, data=serialized_request, cookies=self.auth.cookies, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)
        ) as response:
            _LOGGER.debug(f"Response headers: {response.headers}")
            response_data = await response.read()
            _LOGGER.debug(f"Response data preview: {response_data[:100].hex()}")

            if b"<!doctype html>" in response_data:
                _LOGGER.error("Received HTML instead of Protobuf. Reauthenticating...")
                await self.auth.authenticate()
                async with self.session.post(
                    url, headers=headers, data=serialized_request, cookies=self.auth.cookies, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)
                ) as retry_response:
                    response_data = await retry_response.read()
                    if b"<!doctype html>" in response_data:
                        raise Exception("Authentication failed: Received HTML login page after retry")
            elif response.status not in SUCCESS_STATUS_CODES:
                response_text = await response.text()
                _LOGGER.error(f"Request failed with status {response.status}: {response_text}")
                raise Exception(f"Request failed: {response.status}")
            return response_data