import logging
import os
import asyncio
from google.protobuf import descriptor_pb2, message_factory
from google.protobuf import descriptor_pool

_LOGGER = logging.getLogger(__name__)

class ProtobufManager:
    def __init__(self, descriptor_file):
        self.descriptor_file = descriptor_file
        self.pool = None
        self.factory = None

    def _read_descriptor_file(self):
        """Read the Protobuf descriptor file synchronously."""
        with open(self.descriptor_file, "rb") as f:
            return f.read()

    async def load_descriptor(self):
        """Load the Protobuf descriptor set asynchronously."""
        _LOGGER.info(f"Loading descriptor file from: {self.descriptor_file}")
        if not os.path.exists(self.descriptor_file):
            _LOGGER.error(f"Descriptor file not found: {self.descriptor_file}")
            raise FileNotFoundError(f"Descriptor file missing: {self.descriptor_file}")

        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self._read_descriptor_file)
        descriptor_set = descriptor_pb2.FileDescriptorSet.FromString(data)

        self.pool = descriptor_pool.DescriptorPool()
        for file_desc_proto in descriptor_set.file:
            self.pool.Add(file_desc_proto)
            _LOGGER.debug(f"Registered descriptor: {file_desc_proto.name}")

        self.factory = message_factory.MessageFactory(self.pool)
        _LOGGER.info("Successfully loaded descriptor set")

    def create_message(self, message_name):
        """Create a Protobuf message from the descriptor pool."""
        if self.pool is None or self.factory is None:
            raise RuntimeError("Descriptor not loaded yet")
        descriptor = self.pool.FindMessageTypeByName(message_name)
        if descriptor is None:
            raise KeyError(f"Message type '{message_name}' not found in descriptor pool")
        return self.factory.GetPrototype(descriptor)()