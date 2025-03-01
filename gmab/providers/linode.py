# gmab/providers/linode.py

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

class LinodeProvider(ProviderBase):
    """
    Provider implementation for Linode.
    """

    @staticmethod
    def get_default_config():
        return {
            "api_key": "",
            "default_region": "nl-ams",
            "default_image": "linode/ubuntu22.04",
            "default_type": "g6-nanode-1",
            "default_root_pass": ""
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
            default=provider_config.get('default_region', LinodeProvider.get_default_config()['default_region'])
        )
        config['default_image'] = functools.partial(click.prompt,
            "Default image",
            default=provider_config.get('default_image', LinodeProvider.get_default_config()['default_image'])
        )
        config['default_type'] = functools.partial(click.prompt,
            "Default instance type",
            default=provider_config.get('default_type', LinodeProvider.get_default_config()['default_type'])
        )
        config['default_root_pass'] = functools.partial(click.prompt,
            "Default root password",
            default=provider_config.get('default_root_pass', ''),
            hide_input=False
        )
        return config

    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        """
        Create a new Linode instance.
        
        Args:
            image (str, optional): The Linode image to use
            region (str, optional): The region to create the instance in
            ssh_key_path (str, optional): Path to the SSH public key to use
            lifetime_minutes (int, optional): Lifetime of the instance in minutes
            
        Returns:
            dict: Instance information including ID, IP, etc.
            
        Raises:
            ValueError: If API key is missing or other validation fails
            FileNotFoundError: If SSH key file doesn't exist
            Exception: For API errors or other failures
        """
        token = self.provider_cfg.get("api_key")
        if not token:
            raise ValueError("Linode API key not found in config.")

        # Fallback to defaults if arguments are not provided
        linode_type = self.provider_cfg.get("default_type", "g6-nanode-1")
        default_image = self.provider_cfg.get("default_image", "linode/ubuntu22.04")
        default_region = self.provider_cfg.get("default_region", "us-east")

        if image is None:
            print(f"[INFO] No image specified, falling back to default: {default_image}")
            image = default_image
        if region is None:
            print(f"[INFO] No region specified, falling back to default: {default_region}")
            region = default_region
        
        # Set default lifetime if not specified
        if lifetime_minutes is None:
            lifetime_minutes = 60

        # Current timestamp for creation time
        creation_time = int(time.time())

        root_pass = self.provider_cfg.get("default_root_pass", "ChangeMe123!")
        ssh_key_path = ssh_key_path or self.provider_cfg.get("ssh_key_path", "~/.ssh/id_ed25519.pub")

        keyfile = Path(ssh_key_path).expanduser()
        if not keyfile.exists():
            raise FileNotFoundError(f"SSH key not found at {keyfile}")

        with open(keyfile, 'r') as f:
            ssh_key = f.read().strip()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        # Generate a unique Linode name
        random_name = f"gmab-{generate_random_string(12)}"

        data = {
            "type": linode_type,
            "region": region,
            "image": image,
            "authorized_keys": [ssh_key],
            "root_pass": root_pass,
            "label": random_name,
            "tags": [
                "gmab",
                f"gmab-creation-time-{creation_time}",
                f"gmab-lifetime-{lifetime_minutes}"
            ]
        }

        try:
            resp = requests.post(
                "https://api.linode.com/v4/linode/instances",
                headers=headers,
                json=data,
                timeout=30  # Added timeout for better error handling
            )
            
            if resp.status_code not in (200, 202):
                raise Exception(f"Linode creation failed: {resp.text}")

            instance_data = resp.json()
            ip_address = instance_data["ipv4"][0] if instance_data["ipv4"] else "No IP Assigned"
            
            return {
                "provider": self.provider_name,
                "instance_id": str(instance_data["id"]),
                "ip": ip_address,
                "label": random_name,
                "status": instance_data["status"],
                "region": region,
                "image": image,
                "creation_time": creation_time,
                "lifetime_minutes": lifetime_minutes
            }
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when creating Linode: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to create Linode instance: {str(e)}")

    def get_instance_id_by_label(self, label):
        """
        Find the Linode instance ID by its label, but only for instances with the 'gmab' tag.
        
        Args:
            label (str): The instance label to search for
            
        Returns:
            str or None: The instance ID if found, None otherwise
        """
        instances = self.list_instances()
        for instance in instances:
            if instance["label"] == label:
                return instance["instance_id"]
        return None

    def terminate_instance(self, instance_identifier):
        """
        Terminate a Linode instance by ID or label.
        
        Args:
            instance_identifier (str): A numeric instance ID or label (e.g., "gmab-3ul7u0p1x9ns")
            
        Raises:
            Exception: If the instance cannot be found or deleted
        """
        token = self.provider_cfg.get("api_key")
        if not token:
            raise ValueError("Linode API key not found in config.")
            
        headers = {"Authorization": f"Bearer {token}"}

        if not instance_identifier.isdigit():
            instance_id = self.get_instance_id_by_label(instance_identifier)
            if instance_id is None:
                raise Exception(f"Instance with label '{instance_identifier}' not found or not tagged with 'gmab'.")
        else:
            instance_id = instance_identifier

        try:
            resp = requests.delete(
                f"https://api.linode.com/v4/linode/instances/{instance_id}",
                headers=headers,
                timeout=30  # Added timeout for better error handling
            )

            if resp.status_code not in (200, 204):
                raise Exception(f"Linode deletion failed: {resp.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when terminating Linode: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to terminate Linode instance: {str(e)}")

    def _get_instance_expiry_info(self, tags):
        """
        Helper method to get expiry information from instance tags.
        
        Args:
            tags (list): List of tags from the Linode instance
            
        Returns:
            tuple: (creation_time, lifetime_minutes, is_expired)
        """
        creation_time = 0
        lifetime_minutes = 60
        
        for tag in tags:
            if tag.startswith("gmab-creation-time-"):
                creation_time = int(tag.split("-")[-1])
            elif tag.startswith("gmab-lifetime-"):
                lifetime_minutes = int(tag.split("-")[-1])
        
        current_time = int(time.time())
        is_expired = (current_time - creation_time) > (lifetime_minutes * 60)
        return creation_time, lifetime_minutes, is_expired

    def list_instances(self):
        """
        Retrieve all active Linode instances that have the 'gmab' tag.
        
        Returns:
            list: List of instance dictionaries
            
        Raises:
            Exception: If listing instances fails
        """
        token = self.provider_cfg.get("api_key")
        if not token:
            raise ValueError("Linode API key not found in config.")
            
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(
                "https://api.linode.com/v4/linode/instances", 
                headers=headers,
                timeout=30  # Added timeout for better error handling
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to list Linodes: {response.text}")

            instances = response.json()["data"]
            result = []

            for instance in instances:
                if "gmab" in instance.get("tags", []):
                    creation_time, lifetime_minutes, is_expired = self._get_instance_expiry_info(instance.get("tags", []))
                    
                    # Modify status to include expiry information
                    base_status = instance["status"]
                    status = f"{base_status} (expired)" if is_expired else base_status

                    result.append({
                        "provider": self.provider_name,
                        "instance_id": str(instance["id"]),
                        "label": instance["label"],
                        "ip": instance["ipv4"][0] if instance["ipv4"] else "No IP Assigned",
                        "status": status,
                        "region": instance.get("region", "Unknown"),
                        "image": instance.get("image", "Unknown"),
                        "creation_time": creation_time,
                        "lifetime_minutes": lifetime_minutes,
                        "is_expired": is_expired
                    })

            return result
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error when listing Linodes: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to list Linode instances: {str(e)}")

    def list_expired_instances(self):
        """
        List all expired instances.
        
        Returns:
            list: List of expired instance dictionaries
        """
        return [inst for inst in self.list_instances() if inst['is_expired']]