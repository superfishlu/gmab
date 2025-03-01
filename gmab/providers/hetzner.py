# gmab/providers/hetzner.py

import click
import functools
import requests
import random
import string
import time
from pathlib import Path
from gmab.providers.base import ProviderBase

def generate_random_string(length=12):
    """Generate a random string of lowercase letters and digits."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class HetznerProvider(ProviderBase):
    """
    Provider implementation for Hetzner Cloud.
    """
    
    def __init__(self, provider_cfg):
        """
        Initialize the Hetzner provider with the given configuration.
        
        Args:
            provider_cfg (dict): Hetzner provider configuration including API token, etc.
        """
        super().__init__(provider_cfg)
        
        # Validate required config values
        api_key = provider_cfg.get('api_key')
        if not api_key:
            raise ValueError("Hetzner requires an API key to be configured")
            
        self.api_url = "https://api.hetzner.cloud/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _get_instance_expiry_info(self, labels):
        """
        Helper method to get expiry information from instance labels.
        
        Args:
            labels (dict): Key-value labels from the Hetzner instance
            
        Returns:
            tuple: (creation_time, lifetime_minutes, is_expired)
        """
        creation_time = 0
        lifetime_minutes = 60
        
        # In Hetzner, we store these as gmab-creation-time and gmab-lifetime
        creation_time = int(labels.get("gmab-creation-time", "0"))
        lifetime_minutes = int(labels.get("gmab-lifetime", "60"))
        
        current_time = int(time.time())
        is_expired = (current_time - creation_time) > (lifetime_minutes * 60)
        return creation_time, lifetime_minutes, is_expired

    def _get_or_create_ssh_key(self, ssh_key_content):
        """
        Helper method to get existing SSH key or create a new one.
        
        Args:
            ssh_key_content (str): The SSH public key content
            
        Returns:
            int: SSH key ID
            
        Raises:
            Exception: If SSH key cannot be created or found
        """
        try:
            # First list existing SSH keys
            list_response = requests.get(
                f"{self.api_url}/ssh_keys",
                headers=self.headers,
                timeout=30
            )
            
            if list_response.status_code != 200:
                raise Exception(f"Failed to list SSH keys: {list_response.text}")
                
            # Check if we have a matching key
            ssh_keys = list_response.json()["ssh_keys"]
            for key in ssh_keys:
                if key["public_key"].strip() == ssh_key_content.strip():
                    return key["id"]
            
            # If no matching key found, create new one
            ssh_key_name = f"gmab-key-{generate_random_string(8)}"
            create_response = requests.post(
                f"{self.api_url}/ssh_keys",
                headers=self.headers,
                json={
                    "name": ssh_key_name,
                    "public_key": ssh_key_content
                },
                timeout=30
            )

            if create_response.status_code != 201:
                raise Exception(f"Failed to create SSH key: {create_response.text}")

            return create_response.json()["ssh_key"]["id"]
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when managing SSH keys: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to get or create SSH key: {str(e)}")
        
    @staticmethod
    def get_default_config():
        return {
            "api_key": "",
            "default_region": "nbg1",
            "default_image": "ubuntu-22.04",
            "default_type": "cpx11"
        }
    
    @staticmethod
    def get_config_prompts(provider_config):
        config = {}
        config['api_key'] = functools.partial(click.prompt,
            "API Key",
            default=provider_config.get('api_key', ''),
            hide_input=False
        )
        config['default_region'] = functools.partial(click.prompt,
            "Default region",
            default=provider_config.get('default_region', HetznerProvider.get_default_config()['default_region'])
        )
        config['default_image'] = functools.partial(click.prompt,
            "Default image",
            default=provider_config.get('default_image', HetznerProvider.get_default_config()['default_image'])
        )
        config['default_type'] = functools.partial(click.prompt,
            "Default instance type",
            default=provider_config.get('default_type', HetznerProvider.get_default_config()['default_type'])
        )
        return config

    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        """
        Create a new Hetzner Cloud server.
        
        Args:
            image (str, optional): The Hetzner image to use
            region (str, optional): The location to create the server in
            ssh_key_path (str, optional): Path to the SSH public key to use
            lifetime_minutes (int, optional): Lifetime of the server in minutes
            
        Returns:
            dict: Server information including ID, IP, etc.
            
        Raises:
            ValueError: If API key is missing
            FileNotFoundError: If SSH key file doesn't exist
            Exception: For API errors or other failures
        """
        # Use provided values or fall back to defaults
        default_type = self.provider_cfg.get("default_type", "cpx11")
        default_image = self.provider_cfg.get("default_image", "ubuntu-22.04")
        default_region = self.provider_cfg.get("default_region", "nbg1")

        chosen_image = image or default_image
        chosen_region = region or default_region
        
        if lifetime_minutes is None:
            lifetime_minutes = 60

        # Current timestamp for creation time
        creation_time = int(time.time())

        # Read SSH key
        ssh_key_path = ssh_key_path or self.provider_cfg.get("ssh_key_path", "~/.ssh/id_ed25519.pub")
        keyfile = Path(ssh_key_path).expanduser()
        if not keyfile.exists():
            raise FileNotFoundError(f"SSH key not found at {keyfile}")

        with open(keyfile, 'r') as f:
            ssh_key_content = f.read().strip()

        # Generate a unique name
        instance_name = f"gmab-{generate_random_string(12)}"

        try:
            # Get or create SSH key
            ssh_key_id = self._get_or_create_ssh_key(ssh_key_content)

            # Create the server with Hetzner-compliant labels
            create_response = requests.post(
                f"{self.api_url}/servers",
                headers=self.headers,
                json={
                    "name": instance_name,
                    "server_type": default_type,
                    "image": chosen_image,
                    "location": chosen_region,
                    "ssh_keys": [ssh_key_id],
                    "labels": {
                        "gmab": "true",
                        "gmab-creation-time": str(creation_time),
                        "gmab-lifetime": str(lifetime_minutes)
                    }
                },
                timeout=60  # Server creation can take a bit longer
            )

            if create_response.status_code != 201:
                raise Exception(f"Failed to create server: {create_response.text}")

            server_data = create_response.json()["server"]
            
            return {
                "provider": self.provider_name,
                "instance_id": str(server_data["id"]),
                "label": instance_name,
                "ip": server_data.get("public_net", {}).get("ipv4", {}).get("ip", "No IP Assigned"),
                "status": server_data["status"],
                "region": chosen_region,
                "image": chosen_image,
                "creation_time": creation_time,
                "lifetime_minutes": lifetime_minutes
            }
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when creating server: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to create Hetzner instance: {str(e)}")

    def get_instance_id_by_label(self, label):
        """
        Find instance ID by label, but only for instances with the 'gmab' label.
        
        Args:
            label (str): The instance label to search for
            
        Returns:
            str or None: The instance ID if found, None otherwise
        """
        try:
            instances = self.list_instances()
            for instance in instances:
                if instance["label"] == label:
                    return instance["instance_id"]
            return None
            
        except Exception:
            return None

    def terminate_instance(self, instance_identifier):
        """
        Terminate a Hetzner server by ID or label.
        
        Args:
            instance_identifier (str): Either a numeric instance ID or a label
            
        Raises:
            Exception: If the server cannot be found or deleted
        """
        try:
            # If it's not a numeric ID, try to find by label
            if not instance_identifier.isdigit():
                instance_id = self.get_instance_id_by_label(instance_identifier)
                if instance_id is None:
                    raise Exception(f"No instance found with label '{instance_identifier}'")
            else:
                instance_id = instance_identifier

            # Delete the server
            delete_response = requests.delete(
                f"{self.api_url}/servers/{instance_id}",
                headers=self.headers,
                timeout=30
            )

            if delete_response.status_code not in (200, 204):
                raise Exception(f"Failed to delete server: {delete_response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when terminating server: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to terminate Hetzner instance: {str(e)}")

    def list_instances(self):
        """
        List all Hetzner servers tagged with 'gmab'.
        
        Returns:
            list: List of instance dictionaries
            
        Raises:
            Exception: If listing servers fails
        """
        try:
            response = requests.get(
                f"{self.api_url}/servers",
                headers=self.headers,
                params={"label_selector": "gmab"},
                timeout=30
            )

            if response.status_code != 200:
                raise Exception(f"Failed to list servers: {response.text}")

            instances = []
            for server in response.json()["servers"]:
                creation_time, lifetime_minutes, is_expired = self._get_instance_expiry_info(server.get("labels", {}))
                
                # Modify status to include expiry information
                base_status = server["status"]
                status = f"{base_status} (expired)" if is_expired else base_status

                instances.append({
                    "provider": self.provider_name,
                    "instance_id": str(server["id"]),
                    "label": server["name"],
                    "ip": server.get("public_net", {}).get("ipv4", {}).get("ip", "No IP Assigned"),
                    "status": status,
                    "region": server["datacenter"]["location"]["name"],
                    "image": server["image"]["name"],
                    "creation_time": creation_time,
                    "lifetime_minutes": lifetime_minutes,
                    "is_expired": is_expired
                })

            return instances
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when listing servers: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to list Hetzner instances: {str(e)}")

    def list_expired_instances(self):
        """
        List all expired instances.
        
        Returns:
            list: List of expired instance dictionaries
        """
        return [inst for inst in self.list_instances() if inst['is_expired']]