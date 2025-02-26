# gmab/commands/configure.py

import click
from pathlib import Path
import json
from gmab.utils.paths import get_config_file_path, ensure_config_dir_exists
from gmab.utils.config_loader import (
    load_config, save_config, DEFAULT_GENERAL_CONFIG, 
    DEFAULT_PROVIDERS_CONFIG, ConfigNotFoundError
)

def update_nested_dict(original, updates):
    """Recursively update a nested dictionary without overwriting unspecified values."""
    for key, value in updates.items():
        if key in original and isinstance(original[key], dict) and isinstance(value, dict):
            update_nested_dict(original[key], value)
        elif value is not None:  # Only update if value is not None
            original[key] = value
    return original

def print_configs():
    """Print the current configuration files and their contents."""
    config_files = {
        'config.json': 'General Configuration',
        'providers.json': 'Provider Configuration'
    }

    for filename, description in config_files.items():
        config_path = get_config_file_path(filename)
        click.echo(f"\n{description}")
        click.echo(f"Location: {config_path}")
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    # Handle sensitive data
                    if filename == 'providers.json':
                        # Mask sensitive values in a copy of the config
                        masked_config = json.loads(json.dumps(config_data))
                        for provider in masked_config.values():
                            for key in provider:
                                if key in ['api_key', 'access_key', 'secret_key', 'default_root_pass']:
                                    provider[key] = '********'
                        config_data = masked_config
                    
                    click.echo("Contents:")
                    click.echo(json.dumps(config_data, indent=2))
            except Exception as e:
                click.echo(f"Error reading configuration: {str(e)}")
        else:
            click.echo("File does not exist")

def configure_general(current_config):
    """Configure general settings."""
    click.echo("\nConfiguring general settings:")
    
    ssh_key_path = click.prompt(
        "SSH public key path",
        default=current_config.get('ssh_key_path', DEFAULT_GENERAL_CONFIG['ssh_key_path'])
    )
    
    default_lifetime = click.prompt(
        "Default instance lifetime (minutes)",
        default=current_config.get('default_lifetime_minutes', DEFAULT_GENERAL_CONFIG['default_lifetime_minutes']),
        type=int
    )
    
    # Only show providers that have been configured
    available_providers = list(DEFAULT_PROVIDERS_CONFIG.keys())
    
    # In case we're updating an existing config, get the current provider
    current_provider = current_config.get('default_provider', DEFAULT_GENERAL_CONFIG['default_provider'])
    
    default_provider = click.prompt(
        "Default provider",
        default=current_provider,
        type=click.Choice(available_providers, case_sensitive=False)
    )
    
    return {
        'ssh_key_path': ssh_key_path,
        'default_lifetime_minutes': default_lifetime,
        'default_provider': default_provider
    }

def configure_provider(provider_name, current_config):
    """Configure a specific provider."""
    click.echo(f"\nConfiguring {provider_name} provider:")
    
    provider_config = current_config.get(provider_name, {})
    default_config = DEFAULT_PROVIDERS_CONFIG[provider_name]
    
    # Provider-specific configuration
    if provider_name == "aws":
        # AWS configuration in exact order from providers.json.sample
        config = {}
        config['access_key'] = click.prompt(
            "Access Key",
            default=provider_config.get('access_key', ''),
            hide_input=False
        )
        config['secret_key'] = click.prompt(
            "Secret Key",
            default=provider_config.get('secret_key', ''),
            hide_input=False
        )
        config['default_region'] = click.prompt(
            "Default region",
            default=provider_config.get('default_region', default_config['default_region'])
        )
        config['default_image'] = click.prompt(
            "Default image",
            default=provider_config.get('default_image', default_config['default_image'])
        )
        config['default_type'] = click.prompt(
            "Default instance type",
            default=provider_config.get('default_type', default_config['default_type'])
        )
        return config

    elif provider_name == "linode":
        config = {}
        config['api_key'] = click.prompt(
            "API Key",
            default=provider_config.get('api_key', ''),
            hide_input=False
        )
        config['default_region'] = click.prompt(
            "Default region",
            default=provider_config.get('default_region', default_config['default_region'])
        )
        config['default_image'] = click.prompt(
            "Default image",
            default=provider_config.get('default_image', default_config['default_image'])
        )
        config['default_type'] = click.prompt(
            "Default instance type",
            default=provider_config.get('default_type', default_config['default_type'])
        )
        config['default_root_pass'] = click.prompt(
            "Default root password",
            default=provider_config.get('default_root_pass', ''),
            hide_input=False
        )
        return config

    elif provider_name == "hetzner":
        config = {}
        config['api_key'] = click.prompt(
            "API Key",
            default=provider_config.get('api_key', ''),
            hide_input=False
        )
        config['default_region'] = click.prompt(
            "Default region",
            default=provider_config.get('default_region', default_config['default_region'])
        )
        config['default_image'] = click.prompt(
            "Default image",
            default=provider_config.get('default_image', default_config['default_image'])
        )
        config['default_type'] = click.prompt(
            "Default instance type",
            default=provider_config.get('default_type', default_config['default_type'])
        )
        return config

def validate_configs():
    """Perform basic validation of the configuration files."""
    try:
        general_config = load_config('config.json')
        providers_config = load_config('providers.json')
        
        # Check if SSH key exists
        ssh_key_path = Path(general_config.get('ssh_key_path', '')).expanduser()
        if not ssh_key_path.exists():
            click.echo(f"\nWarning: SSH key not found at {ssh_key_path}")
        
        # Check if default provider is configured
        default_provider = general_config.get('default_provider')
        if default_provider:
            if default_provider not in providers_config:
                click.echo(f"\nWarning: Default provider '{default_provider}' is not configured")
            else:
                provider_config = providers_config.get(default_provider, {})
                if default_provider == 'aws':
                    if not provider_config.get('access_key') or not provider_config.get('secret_key'):
                        click.echo(f"\nWarning: Default provider '{default_provider}' is not fully configured (missing AWS credentials)")
                elif not provider_config.get('api_key'):
                    click.echo(f"\nWarning: Default provider '{default_provider}' is not fully configured (missing API key)")
    except Exception as e:
        click.echo(f"\nWarning: Could not validate configurations: {str(e)}")

def run_configure(provider):
    """Main configure function to be called from CLI."""
    # Ensure config directory exists
    config_dir = ensure_config_dir_exists()
    click.echo(f"Using config directory: {config_dir}")
    
    # Load existing configs or create new empty ones
    try:
        general_config = load_config('config.json')
    except ConfigNotFoundError:
        general_config = {}
    
    try:
        providers_config = load_config('providers.json')
    except ConfigNotFoundError:
        providers_config = {}
    
    if provider == 'all':
        # Configure general settings
        new_general_config = configure_general(general_config)
        save_config(new_general_config, 'config.json')
        
        # Configure each provider
        for prov in DEFAULT_PROVIDERS_CONFIG.keys():
            if click.confirm(f"\nDo you want to configure {prov}?", default=True):
                providers_config[prov] = configure_provider(prov, providers_config)
        
        save_config(providers_config, 'providers.json')
    
    else:
        # If no general config exists, configure it first
        if not general_config:
            new_general_config = configure_general({})
            save_config(new_general_config, 'config.json')
        
        # Configure only the specified provider
        providers_config[provider] = configure_provider(provider, providers_config)
        save_config(providers_config, 'providers.json')
    
    # Validate the final configuration
    validate_configs()
    
    click.echo("\nConfiguration completed successfully!")
    click.echo(f"Config files are located in: {config_dir}")