import os
import logging
import uuid
import asyncio
from google.protobuf.message import DecodeError
from google.protobuf.internal.decoder import _DecodeVarint32
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
        self.buffer = bytearray()  # Persistent buffer for stream data
        self.pending_length = 0    # Length of next expected message

    async def refresh_state(self, connection, access_token):
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

        self.buffer.clear()
        self.pending_length = 0
        try:
            async with asyncio.timeout(10):
                async for chunk in connection.stream(api_url, headers, observe_data):
                    _LOGGER.debug(f"Received raw chunk: {chunk.hex()[:200]}")
                    locks_data = self._process_chunk(chunk)
                    if locks_data and locks_data.get("yale"):
                        return locks_data
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching initial state from stream")
        return {"yale": {}, "user_id": None}

    async def stream(self, api_url, headers, observe_data, connection, hass):
        self.buffer.clear()
        self.pending_length = 0
        try:
            async for chunk in connection.stream(api_url, headers, observe_data):
                _LOGGER.debug(f"Received raw chunk: {chunk.hex()[:200]}")
                locks_data = self._process_chunk(chunk)
                if locks_data:
                    yield locks_data
        except asyncio.TimeoutError:
            _LOGGER.warning("Stream chunk timeout; continuing")
            yield {"yale": {}, "user_id": None}

    def _process_chunk(self, chunk):
        """Process a chunk, decoding length-prefixed StreamBody messages."""
        self.buffer.extend(chunk)
        _LOGGER.debug(f"Buffer state: {self.buffer.hex()[:200]} (length: {len(self.buffer)})")

        while len(self.buffer) > 0:
            # If no pending length set, decode the next varint
            if self.pending_length == 0:
                try:
                    msg_len, pos = _DecodeVarint32(self.buffer, 0)
                    self.pending_length = msg_len + pos  # Total length including varint
                    _LOGGER.debug(f"Detected message length: {msg_len} (total: {self.pending_length})")
                except ValueError as e:
                    _LOGGER.error(f"Invalid varint at buffer start: {e}, clearing buffer")
                    self.buffer.clear()
                    return None

            # Check if we have a complete message
            if len(self.buffer) >= self.pending_length:
                try:
                    msg_data = self.buffer[:self.pending_length]
                    message = self.stream_body.FromString(msg_data)
                    _LOGGER.debug(f"Decoded StreamBody message: {message!s:.200}")

                    # Remove processed message from buffer
                    self.buffer = self.buffer[self.pending_length:]
                    self.pending_length = 0
                    _LOGGER.debug(f"Buffer after decode: {self.buffer.hex()[:200]} (length: {len(self.buffer)})")

                    if message.status and message.status.code != 0:
                        _LOGGER.error(f"Server returned status: {message.status.code} - {message.status.message}")
                        return {"yale": {}, "user_id": None}

                    locks_data = DeviceParser.parse_locks(message)
                    _LOGGER.debug(f"Parsed locks data: {locks_data}")
                    return locks_data

                except DecodeError as e:
                    _LOGGER.error(f"Decode error on full message: {e}, resetting buffer")
                    self.buffer.clear()
                    self.pending_length = 0
                    return None
            else:
                _LOGGER.debug(f"Buffer too short: {len(self.buffer)} < {self.pending_length}, waiting for more data")
                break

        return None  # No complete message yet