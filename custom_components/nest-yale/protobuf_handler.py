import os
import logging
import uuid
import asyncio
from google.protobuf.message import DecodeError
from .device_parser import DeviceParser
from .proto import root_pb2
from .protobuf_manager import read_protobuf_file
from .const import (
    USER_AGENT_STRING,
    URL_PROTOBUF,
    ENDPOINT_OBSERVE,
    PRODUCTION_HOSTNAME,
)

_LOGGER = logging.getLogger(__name__)

class NestProtobufHandler:
    def __init__(self):
        self.stream_body = root_pb2.StreamBody()

    async def refresh_state(self, connection, access_token):
        """Fetch the initial state of devices using Protobuf streaming."""
        headers = {
            "Authorization": f"Basic {access_token}",
            "Content-Type": "application/x-protobuf",
            "X-Accept-Content-Transfer-Encoding": "binary",
            "X-Accept-Response-Streaming": "true",
            "User-Agent": USER_AGENT_STRING,
            "request-id": str(uuid.uuid4()),
            "referer": "https://home.nest.com/",
            "origin": "https://home.nest.com",
            "x-nl-webapp-version": "NlAppSDKVersion/8.15.0 NlSchemaVersion/2.1.20-87-gce5742894"
        }

        api_url = f"{URL_PROTOBUF.format(grpc_hostname=PRODUCTION_HOSTNAME['grpc_hostname'])}{ENDPOINT_OBSERVE}"
        proto_path = os.path.join(os.path.dirname(__file__), "proto", "ObserveTraits.protobuf")
        observe_data = await read_protobuf_file(proto_path)

        try:
            async with asyncio.timeout(10):
                async for chunk in connection.stream(api_url, headers, observe_data):
                    try:
                        message = self.stream_body.FromString(chunk)
                        _LOGGER.debug(f"Decoded refresh message: {message!s:.200}")
                        if message.status and message.status.code != 0:
                            _LOGGER.error(f"Server returned status: {message.status.code} - {message.status.message}")
                            continue
                        locks_data = DeviceParser.parse_locks(message)
                        _LOGGER.debug(f"Parsed locks data: {locks_data}")
                        if locks_data.get("yale"):
                            return locks_data
                    except DecodeError as e:
                        _LOGGER.error(f"Protobuf decoding error in refresh: {e}")
                        _LOGGER.debug(f"Raw chunk causing decode error: {chunk.hex()[:200]}")  # Log raw data
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching initial state from stream")
        return {"yale": {}, "user_id": None}

    async def stream(self, api_url, headers, observe_data, connection, hass):
        """Stream updates from the Nest API."""
        try:
            async for chunk in connection.stream(api_url, headers, observe_data):
                try:
                    message = self.stream_body.FromString(chunk)
                    _LOGGER.debug(f"Decoded stream message: {message!s:.200}")
                    if message.status and message.status.code != 0:
                        _LOGGER.error(f"Server returned status: {message.status.code} - {message.status.message}")
                        continue
                    locks_data = DeviceParser.parse_locks(message)
                    _LOGGER.debug(f"Stream updated locks: {locks_data}")
                    yield locks_data
                except DecodeError as e:
                    _LOGGER.error(f"Protobuf decoding error in stream: {e}")
                    _LOGGER.debug(f"Raw chunk causing decode error: {chunk.hex()[:200]}")  # Log raw data
                    yield {"yale": {}, "user_id": None}  # Fallback to keep stream alive
        except asyncio.TimeoutError:
            _LOGGER.warning("Stream chunk timeout; continuing")
            yield {"yale": {}, "user_id": None}