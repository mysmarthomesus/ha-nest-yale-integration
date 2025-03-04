import os
import logging
import uuid
import httpx
from google.protobuf import any_pb2
from .auth import NestAuthenticator
from .connection import NestConnection
from .protobuf_handler import NestProtobufHandler
from .const import (
    API_RETRY_DELAY_SECONDS,
    URL_PROTOBUF,
    ENDPOINT_OBSERVE,
    ENDPOINT_SENDCOMMAND,
    PRODUCTION_HOSTNAME,
    USER_AGENT_STRING,
)
from .protobuf_manager import read_protobuf_file

_LOGGER = logging.getLogger(__name__)

class NestAPIClient:
    def __init__(self, hass, issue_token, api_key, cookies):
        self.hass = hass
        self.authenticator = NestAuthenticator(issue_token, api_key, cookies)
        self.connection = NestConnection()
        self.protobuf_handler = NestProtobufHandler()
        self.access_token = None
        self.userid = None
        self.transport_url = None
        self.current_state = {"devices": {"locks": {}}, "user_id": None}

    @classmethod
    async def create(cls, hass, issue_token, api_key, cookies):
        instance = cls(hass, issue_token, api_key, cookies)
        await instance.async_setup()
        return instance

    async def async_setup(self):
        await self.connection.setup()

    async def authenticate(self):
        try:
            auth_data = await self.authenticator.authenticate(self.connection.client)
            _LOGGER.debug(f"Raw auth_data received: {auth_data}")
            if not auth_data or not isinstance(auth_data, dict) or "access_token" not in auth_data:
                raise ValueError(f"Authentication failed: Invalid auth_data received - {auth_data}")
            self.access_token = auth_data["access_token"]
            self.userid = auth_data.get("userid")
            self.transport_url = auth_data.get("urls", {}).get("transport_url")
            _LOGGER.debug(f"Authenticated successfully with token: {self.access_token[:10]}...")
        except httpx.HTTPError as e:
            _LOGGER.error(f"Authentication failed due to HTTP error: {e}")
            raise
        except AttributeError as e:
            _LOGGER.error(f"Unexpected attribute error in auth_data handling: {e} - auth_data: {auth_data}")
            raise
        except Exception as e:
            _LOGGER.error(f"Authentication failed with unexpected error: {e}")
            raise

    async def refresh_state(self):
        if not self.connection.connected or not self.access_token:
            await self.authenticate()

        headers = {
            "Authorization": f"Basic {self.access_token}",
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

        async for locks_data in self.protobuf_handler.stream(api_url, headers, observe_data, self.connection, self.hass):
            # Convert {"yale": {...}} to flat {device_id: {...}} structure
            yale_data = locks_data.get("yale", {})
            if yale_data:
                normalized_locks = {}
                for lock_id, lock_info in yale_data.items():
                    normalized_locks[lock_id] = lock_info
                self.current_state["devices"]["locks"] = normalized_locks
                self.current_state["user_id"] = self.userid
                return normalized_locks
        return {}

    async def observe(self):
        if not self.connection.connected or not self.access_token:
            await self.authenticate()

        headers = {
            "Authorization": f"Basic {self.access_token}",
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

        ping_task = await self.connection.start_ping()
        try:
            async for locks_data in self.protobuf_handler.stream(api_url, headers, observe_data, self.connection, self.hass):
                # Convert {"yale": {...}} to flat {device_id: {...}} structure
                yale_data = locks_data.get("yale", {})
                normalized_locks = {}
                for lock_id, lock_info in yale_data.items():
                    normalized_locks[lock_id] = lock_info
                self.current_state["devices"]["locks"] = normalized_locks
                self.current_state["user_id"] = self.userid
                yield normalized_locks
        except httpx.ReadTimeout as e:
            _LOGGER.warning(f"Stream timed out: {e}; will retry on next cycle")
            self.connection.connected = False
            return
        except httpx.HTTPError as e:
            _LOGGER.error(f"Error in observe stream: {e}")
            self.connection.connected = False
            raise
        finally:
            if ping_task:
                ping_task.cancel()

    async def send_command(self, command, device_id):
        if not self.connection.connected or not self.access_token:
            await self.authenticate()

        headers = {
            "Authorization": f"Basic {self.access_token}",
            "Content-Type": "application/x-protobuf",
            "User-Agent": USER_AGENT_STRING
        }

        api_url = f"{URL_PROTOBUF.format(grpc_hostname=PRODUCTION_HOSTNAME['grpc_hostname'])}{ENDPOINT_SENDCOMMAND}"

        cmd_any = any_pb2.Any()
        cmd_any.type_url = command["command"]["type_url"]
        cmd_any.value = command["command"]["value"].SerializeToString()

        request = root_pb2.ResourceCommandRequest(
            resourceCommands=[root_pb2.ResourceCommand(command=cmd_any)],
            resourceRequest=root_pb2.ResourceRequest(
                resourceId=device_id,
                requestId=str(uuid.uuid4())
            )
        )
        encoded_data = request.SerializeToString()

        try:
            raw_data = await self.connection.post(api_url, headers, encoded_data)
            response_data = root_pb2.ResourceCommandResponseFromAPI.FromString(raw_data)
            _LOGGER.debug(f"Command sent to {device_id}: {command}")
            return response_data
        except httpx.HTTPError as e:
            _LOGGER.error(f"Failed to send command to {device_id}: {e}")
            raise

    async def close(self):
        await self.connection.close()