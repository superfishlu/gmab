# gmab/providers/base.py

from abc import ABC, abstractmethod

class ProviderBase(ABC):
    """
    Abstract base class for all providers.
    """

    def __init__(self, provider_cfg):
        """
        provider_cfg is typically a dict containing credentials, defaults, etc.
        e.g. {
          "api_key": "...",
          "default_region": "...",
          "default_image": "..."
        }
        """
        self.provider_cfg = provider_cfg
        self.provider_name = None  # Will be set by the factory

    @abstractmethod
    def spawn_instance(self, image, region, ssh_key_path, lifetime_minutes):
        """
        Create an instance on the provider and return minimal details.
        Must return a dict with at least these keys:
        {
            "provider": "provider_name",
            "instance_id": "provider-specific-id",
            "label": "instance-name",
            "ip": "ip-address",
            "status": "status",
            "region": "region",
            "image": "image",
            "creation_time": unix_timestamp,
            "lifetime_minutes": minutes
        }
        """
        pass

    @abstractmethod
    def terminate_instance(self, instance_id):
        """
        Terminate an instance by ID or name.
        """
        pass

    @abstractmethod
    def list_instances(self):
        """
        List all instances tagged with 'gmab'.
        Must return a list of dicts with the same structure as spawn_instance().
        """
        pass

    @abstractmethod
    def list_expired_instances(self):
        """
        List all expired instances.
        Must return a list of dicts with the same structure as list_instances().
        """
        pass