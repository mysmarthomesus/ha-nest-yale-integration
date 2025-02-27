import httpx
import logging
import asyncio
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
    def __init__(self, auth):
        self.auth = auth
        self.client = httpx.AsyncClient(http2=True, timeout=API_TIMEOUT_SECONDS)

    async def send_protobuf_request(self, endpoint, protobuf_message):
        """Send a Protobuf request with streaming support."""
        await self.auth.authenticate()
        _LOGGER.debug(f"Using JWT: {self.auth.access_token[:10]}...")

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
            "Accept": "application/x-protobuf.google.rpc.streambody",
        }
        if isinstance(protobuf_message, bytes):
            serialized_request = protobuf_message
        else:
            serialized_request = protobuf_message.SerializeToString()
        _LOGGER.debug(f"Sending request to {url} with headers: {headers}, data: {serialized_request.hex()}")

        async with self.client.stream("POST", url, headers=headers, content=serialized_request, cookies=self.auth.cookies) as response:
            _LOGGER.debug(f"Response status: {response.status_code}, headers: {response.headers}")
            response_data = b""
            async for chunk in response.aiter_bytes():
                response_data += chunk
                _LOGGER.debug(f"Received chunk: {chunk.hex()} (total length: {len(response_data)} bytes)")
                break  # Process first chunk for now; adjust for full stream later
            return response_data

    async def close(self):
        await self.client.aclose()