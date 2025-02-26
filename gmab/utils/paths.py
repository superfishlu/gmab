# gmab/utils/paths.py

import os
import sys
from pathlib import Path

def get_config_dir():
    """
    Get the configuration directory following XDG Base Directory Specification.
    Falls back to platform-specific user config locations.
    
    Returns:
        Path: Path object representing the config directory
    """
    # First check if GMAB_CONFIG_DIR environment variable is set
    if 'GMAB_CONFIG_DIR' in os.environ:
        return Path(os.environ['GMAB_CONFIG_DIR'])

    # On Unix-like systems, follow XDG specification
    if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        return Path(xdg_config_home) / 'gmab'

    # On Windows, use %APPDATA%
    elif sys.platform == 'win32':
        return Path(os.environ['APPDATA']) / 'gmab'

    # Fallback to user's home directory
    return Path.home() / '.gmab'

def get_config_file_path(filename):
    """
    Get the full path for a config file.
    
    Args:
        filename (str): The filename
        
    Returns:
        Path: Path object representing the config file path
    """
    config_dir = get_config_dir()
    return config_dir / filename

def ensure_config_dir_exists():
    """
    Create the config directory if it doesn't exist.
    
    Returns:
        Path: Path object representing the config directory
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir