"""A fake provider + instance factory for driving the command layer offline."""

import time

from gmab.providers.base import ProviderBase, ConfigField


def make_instance(**overrides):
    """Build a contract-shaped instance dict, with overridable fields."""
    instance = {
        "provider": "fake",
        "instance_id": "1",
        "label": "gmab-fake0001",
        "ip": "10.0.0.1",
        "status": "running",
        "region": "test-region",
        "image": "test-image",
        "creation_time": int(time.time()),
        "lifetime_minutes": 60,
        "is_expired": False,
    }
    instance.update(overrides)
    return instance


class FakeProvider(ProviderBase):
    """In-memory provider that records calls and returns canned instances.

    Tests inject canned data by setting `instances` / `spawn_result` on the
    class (or instance) before use, and assert against `terminated`.

    `name` is intentionally None so this fake never registers in the real
    provider registry (get_registry() skips subclasses with a falsy name), even
    though importing this module makes it a ProviderBase subclass in-process.
    """

    name = None

    CONFIG_SCHEMA = [
        ConfigField("api_key", "API Key", secret=True, required=True),
        ConfigField("default_region", "Default region", default="test-region"),
        ConfigField("default_image", "Default image", default="test-image"),
    ]

    def __init__(self, provider_cfg):
        super().__init__(provider_cfg)
        self.instances = []
        self.spawn_result = None
        self.terminated = []
        self.spawn_calls = []

    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        self.spawn_calls.append(
            {
                "image": image,
                "region": region,
                "ssh_key_path": ssh_key_path,
                "lifetime_minutes": lifetime_minutes,
            }
        )
        return self.spawn_result or make_instance()

    def terminate_instance(self, instance_id):
        self.terminated.append(instance_id)

    def list_instances(self):
        return list(self.instances)

    def list_expired_instances(self):
        return [i for i in self.instances if i.get("is_expired")]
