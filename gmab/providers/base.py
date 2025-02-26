# gmab/providers/base.py

from abc import ABC, abstractmethod

class ProviderBase(ABC):
    """
    Abstract base class for all providers.
    """

    def __init__(self, provider_cfg):
        """
        Initialize the provider with configuration.
        
        Args:
            provider_cfg (dict): Provider configuration containing credentials, defaults, etc.
                e.g. {
                  "api_key": "...",
                  "default_region": "...",
                  "default_image": "..."
                }
        """
        self.provider_cfg = provider_cfg
        self.provider_name = None  # Will be set by the factory

    @abstractmethod
    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        """
        Create an instance on the provider and return minimal details.
        
        Args:
            image (str, optional): The image to use for the instance
            region (str, optional): The region to create the instance in
            ssh_key_path (str, optional): Path to the SSH public key to use
            lifetime_minutes (int, optional): Lifetime of the instance in minutes
            
        Returns:
            dict: A dictionary with at least these keys:
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
                
        Raises:
            Exception: If the instance creation fails
        """
        pass

    @abstractmethod
    def terminate_instance(self, instance_id):
        """
        Terminate an instance by ID or name.
        
        Args:
            instance_id (str): The ID or name of the instance to terminate
            
        Raises:
            Exception: If the termination fails
        """
        pass

    @abstractmethod
    def list_instances(self):
        """
        List all instances tagged with 'gmab'.
        
        Returns:
            list: A list of dictionaries with the same structure as spawn_instance() returns
            
        Raises:
            Exception: If listing instances fails
        """
        pass

    @abstractmethod
    def list_expired_instances(self):
        """
        List all expired instances.
        
        Returns:
            list: A list of dictionaries with the same structure as list_instances() returns,
                 but only including expired instances
                 
        Raises:
            Exception: If listing expired instances fails
        """
        pass