# gmab/utils/config_loader.py

import json
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

def load_config(filename):
    """
    Load configuration from the appropriate config directory.
    Creates default config if none exists.
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

    # Create default config if it doesn't exist
    if not config_path.exists():
        default_content = (DEFAULT_GENERAL_CONFIG if actual_filename == 'config.json' 
                         else DEFAULT_PROVIDERS_CONFIG)
        ensure_config_dir_exists()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_content, f, indent=2)

    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config from {config_path}: {str(e)}")
        return {}