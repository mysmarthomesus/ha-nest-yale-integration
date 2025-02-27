import logging
from google.protobuf.message import DecodeError

_LOGGER = logging.getLogger(__name__)

class DeviceParser:
    def __init__(self, protobuf_manager):
        self.protobuf_manager = protobuf_manager

    def parse_devices(self, response_data):
        """Parse the Protobuf response from Observe into a device list."""
        if isinstance(response_data, bytes):
            response = self.protobuf_manager.create_message("nest.rpc.StreamBody")
            try:
                response.ParseFromString(response_data)
                _LOGGER.debug(f"Full StreamBody response: {response}")
            except DecodeError as e:
                _LOGGER.error(f"Failed to parse Protobuf response: {e}")
                raise
        else:
            response = response_data  # Already parsed

        devices = {}
        if response.status.code == 0:  # Success status
            for nest_msg in response.message:
                for get_prop in nest_msg.get:
                    resource_id = get_prop.object.id or "unknown"
                    trait_key = get_prop.object.key
                    if trait_key == "weave.trait.security.BoltLockTrait":
                        if resource_id not in devices:
                            devices[resource_id] = {"device_id": resource_id, "name": f"Nest Yale Lock {resource_id[-4:]}"}
                        devices[resource_id]["has_lock"] = True
        else:
            _LOGGER.warning(f"StreamBody status indicates failure: code={response.status.code}, message={response.status.message}")

        device_list = [device for device in devices.values() if device.get("has_lock", False)]
        _LOGGER.info(f"Found {len(device_list)} locks")
        return device_list