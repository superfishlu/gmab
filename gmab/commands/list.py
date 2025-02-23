# gmab/commands/list.py

from gmab.providers import get_provider
from gmab.utils.config_loader import load_config
import time

def get_lifetime_left(instance):
    """Calculate the lifetime left in minutes for an instance."""
    creation_time = instance.get('creation_time', 0)
    lifetime_minutes = instance.get('lifetime_minutes', 60)
    elapsed_minutes = (time.time() - creation_time) / 60
    return max(0, lifetime_minutes - elapsed_minutes)

def list_boxes(provider_name=None):
    """
    Retrieve all gmab-tagged instances from the specified provider(s).
    If no provider is specified, list instances from all configured providers.
    """
    
    # Load provider configuration from config file
    providers_config = load_config("providers.json")  # Changed path
    general_config = load_config("config.json")      # Changed path

    instances = []
    
    # If no provider specified, try to list from all configured providers
    if provider_name is None:
        for provider_name, provider_cfg in providers_config.items():
            try:
                provider = get_provider(provider_name, provider_cfg)
                instances.extend(provider.list_instances())
            except Exception as e:
                print(f"Warning: Failed to list instances from provider '{provider_name}': {str(e)}")
    else:
        # List instances from specific provider
        provider_cfg = providers_config.get(provider_name)
        if not provider_cfg:
            raise ValueError(f"Provider configuration for '{provider_name}' not found.")

        provider = get_provider(provider_name, provider_cfg)
        instances = provider.list_instances()

    # Calculate lifetime left for each instance and add it to the instance data
    for instance in instances:
        instance['lifetime_left'] = get_lifetime_left(instance)

    # Sort instances by lifetime left (descending)
    instances.sort(key=lambda x: x['lifetime_left'], reverse=True)

    return instances