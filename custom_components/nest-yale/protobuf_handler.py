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
        self.nest_message = root_pb2.NestMessage()
        self.devices = {}
        self.buffer = bytearray()
        self.max_buffer_size = 65536  # 64KB limit

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
        self.devices.clear()
        try:
            async with asyncio.timeout(10):
                async for chunk in connection.stream(api_url, headers, observe_data):
                    _LOGGER.debug(f"Received raw chunk: {chunk.hex()[:200]}")
                    self.buffer.extend(chunk)
                    self._process_buffer()
                    if len(self.buffer) > self.max_buffer_size:
                        _LOGGER.warning(f"Buffer exceeds {self.max_buffer_size} bytes, trimming to last half")
                        self.buffer = self.buffer[-self.max_buffer_size//2:]
            _LOGGER.debug(f"Finished initial stream, aggregated devices: {self.devices}")
            return {"devices": {"locks": {k: v for k, v in self.devices.items() if v.get("device_type") == "lock"}}, "user_id": None}
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching initial state from stream")
            return {"devices": {"locks": {}}, "user_id": None}

    async def stream(self, api_url, headers, observe_data, connection, hass):
        self.buffer.clear()
        self.devices.clear()
        try:
            async for chunk in connection.stream(api_url, headers, observe_data):
                _LOGGER.debug(f"Received raw chunk: {chunk.hex()[:200]}")
                self.buffer.extend(chunk)
                self._process_buffer()
                if len(self.buffer) > self.max_buffer_size:
                    _LOGGER.warning(f"Buffer exceeds {self.max_buffer_size} bytes, trimming to last half")
                    self.buffer = self.buffer[-self.max_buffer_size//2:]
                yield {"devices": {"locks": {k: v for k, v in self.devices.items() if v.get("device_type") == "lock"}}, "user_id": None}
        except asyncio.TimeoutError:
            _LOGGER.warning("Stream chunk timeout; continuing")
            yield {"devices": {"locks": {}}, "user_id": None}

    def _process_buffer(self):
        """Process HTTP/2 framed buffer to aggregate device data."""
        pos = 0
        error_count = 0
        max_errors = 10

        while pos + 9 < len(self.buffer):  # Need 9 bytes for HTTP/2 frame header
            _LOGGER.debug(f"Processing buffer at pos {pos}: {self.buffer[pos:pos+9].hex()} (length: {len(self.buffer)})")
            try:
                # Parse HTTP/2 frame header
                frame_length = int.from_bytes(self.buffer[pos:pos+3], "big")
                frame_type = self.buffer[pos+3]
                frame_flags = self.buffer[pos+4]
                stream_id = int.from_bytes(self.buffer[pos+5:pos+9], "big")

                total_len = 9 + frame_length

                if total_len > len(self.buffer):
                    _LOGGER.debug(f"Incomplete frame at pos {pos}: need {total_len}, have {len(self.buffer)}")
                    break

                if frame_length > 16384 or frame_length < 0:  # HTTP/2 default max frame size is 2^14
                    _LOGGER.error(f"Invalid frame length {frame_length} at pos {pos}, skipping")
                    pos += total_len
                    error_count += 1
                    continue

                _LOGGER.debug(f"Frame at pos {pos}: length={frame_length}, type={hex(frame_type)}, flags={hex(frame_flags)}, stream_id={stream_id}")

                if frame_type != 0x0:  # Only process DATA frames (0x0)
                    _LOGGER.debug(f"Skipping non-DATA frame type {hex(frame_type)} at pos {pos}")
                    pos += total_len
                    continue

                payload = self.buffer[pos + 9:pos + total_len]
                _LOGGER.debug(f"Extracted DATA frame payload at pos {pos}: {payload.hex()[:200]} (length: {frame_length})")

                try:
                    stream_message = self.stream_body.FromString(payload)
                    _LOGGER.debug(f"Decoded StreamBody at pos {pos}: {stream_message!s}")
                    if stream_message.status and stream_message.status.code != 0:
                        _LOGGER.error(f"Server status: {stream_message.status.code} - {stream_message.status.message}")
                        return
                    self._aggregate_devices(stream_message)
                    error_count = 0
                except DecodeError:
                    _LOGGER.debug(f"StreamBody decode failed at pos {pos}, trying NestMessage")
                    nest_message = self.nest_message.FromString(payload)
                    _LOGGER.debug(f"Decoded NestMessage at pos {pos}: {nest_message!s}")
                    self._aggregate_devices(root_pb2.StreamBody(message=[nest_message]))
                    error_count = 0

                pos += total_len
            except (DecodeError, ValueError) as e:
                _LOGGER.error(f"Error at pos {pos}: {e}, skipping frame")
                pos += 9  # Move to next potential frame
                error_count += 1
                if error_count >= max_errors:
                    _LOGGER.error(f"Too many errors ({error_count}), trimming unparsed: {self.buffer[pos:pos+50].hex()[:100]}")
                    self.buffer = self.buffer[pos:]
                    error_count = 0
                    pos = 0

        self.buffer[:] = self.buffer[pos:]  # Clean processed data
        _LOGGER.debug(f"Buffer after processing: {self.buffer.hex()[:200]} (length: {len(self.buffer)})")

    def _aggregate_devices(self, message):
        """Aggregate device data from StreamBody message."""
        locks_data = DeviceParser.parse_locks(message)
        for device_id, lock_info in locks_data.get("yale", {}).items():
            if device_id not in self.devices:
                self.devices[device_id] = {"device_id": device_id, "device_type": "lock"}
            self.devices[device_id].update(lock_info)
            _LOGGER.debug(f"Aggregated lock {device_id}: {self.devices[device_id]}")
        if locks_data.get("user_id"):
            for device_id in self.devices:
                self.devices[device_id]["user_id"] = locks_data["user_id"]