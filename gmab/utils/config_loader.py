# gmab/utils/config_loader.py

import json
import os
from pathlib import Path
from gmab.utils.paths import get_config_file_path, ensure_config_dir_exists

# Default configurations
DEFAULT_GENERAL_CONFIG = {
    "ssh_key_path": "~/.ssh/id_ed25519.pub",
    "default_lifetime_minutes": 60,
    "default_provider": "linode"
}

DEFAULT_PROVIDERS_CONFIG = {
    "linode": {
        "api_key": "",
        "default_region": "nl-ams",
        "default_image": "linode/ubuntu22.04",
        "default_type": "g6-nanode-1",
        "default_root_pass": ""
    },
    "aws": {
        "access_key": "",
        "secret_key": "",
        "default_region": "eu-west-1",
        "default_image": "ami-0574da719dca65348",
        "default_type": "t3.micro"
    },
    "hetzner": {
        "api_key": "",
        "default_region": "nbg1",
        "default_image": "ubuntu-22.04",
        "default_type": "cpx11"
    }
}

class ConfigNotFoundError(Exception):
    """Exception raised when a config file does not exist and should not be auto-created."""
    pass

def load_config(filename, create_if_missing=False):
    """
    Load configuration from the appropriate config directory.
    
    Args:
        filename (str): The configuration file to load
        create_if_missing (bool): Whether to create a default config if none exists
    
    Returns:
        dict: The loaded configuration
        
    Raises:
        ConfigNotFoundError: If the config doesn't exist and create_if_missing=False
    """
    # Handle both old-style paths and new config names
    if filename.startswith('gmab/config/'):
        filename = filename.split('/')[-1]

    # Map old filenames to new ones
    filename_map = {
        'general.json': 'config.json',
        'providers.json': 'providers.json'
    }
    
    actual_filename = filename_map.get(filename, filename)
    config_path = get_config_file_path(actual_filename)

    # Check if config exists
    if not config_path.exists():
        # If it doesn't exist and we shouldn't create it, raise an error
        if not create_if_missing:
            raise ConfigNotFoundError(
                f"Configuration file {actual_filename} not found. "
                "Please run 'gmab configure' to set up your configuration."
            )
        
        # Otherwise create default config
        default_content = (DEFAULT_GENERAL_CONFIG if actual_filename == 'config.json' 
                         else DEFAULT_PROVIDERS_CONFIG)
        ensure_config_dir_exists()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_content, f, indent=2)

    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parsing config file {config_path}: {str(e)}")
    except Exception as e:
        raise Exception(f"Error loading config from {config_path}: {str(e)}")

def config_exists():
    """Check if the basic configuration files exist.
    
    Returns:
        bool: True if both config.json and providers.json exist
    """
    config_path = get_config_file_path('config.json')
    providers_path = get_config_file_path('providers.json')
    return config_path.exists() and providers_path.exists()

def save_config(config, filename):
    """Save configuration to file."""
    config_path = get_config_file_path(filename)
    ensure_config_dir_exists()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)