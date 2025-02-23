# gmab/commands/terminate.py

import click
from gmab.utils.config_loader import load_config
from gmab.providers import get_provider

def get_instance_provider(instance_identifier, providers_cfg):
    """
    Determine which provider an instance belongs to based on ID format and provider queries.
    Returns tuple of (provider_name, provider_instance) or (None, None) if not found.
    """
    # First try to determine by ID format
    if instance_identifier.startswith('i-'):
        # AWS instance ID format
        provider_name = "aws"
    elif instance_identifier.startswith('gmab-'):
        # Check all providers for this label since multiple could use this format
        provider_name = None
    else:
        # For numeric IDs or other formats, we need to check all providers
        provider_name = None

    if provider_name and provider_name in providers_cfg:
        provider = get_provider(provider_name, providers_cfg[provider_name])
        return provider_name, provider

    # If we couldn't determine by format or need to check labels, query each provider
    for provider_name, provider_cfg in providers_cfg.items():
        provider = get_provider(provider_name, provider_cfg)
        instances = provider.list_instances()
        
        for instance in instances:
            if (instance['instance_id'] == instance_identifier or 
                instance['label'] == instance_identifier):
                return provider_name, provider

    return None, None

def terminate_box(instance_id, provider_name=None):
    """Terminate an instance by ID."""
    # Load configs
    providers_cfg = load_config("providers.json")  # Changed path
    general_cfg = load_config("config.json")      # Changed path

    if provider_name:
        # If provider is specified, use it directly
        provider_cfg = providers_cfg.get(provider_name)
        if not provider_cfg:
            raise ValueError(f"Provider '{provider_name}' not found in providers.json")
        provider = get_provider(provider_name, provider_cfg)
    else:
        # Try to determine provider from instance ID
        provider_name, provider = get_instance_provider(instance_id, providers_cfg)
        if not provider:
            raise ValueError(f"Could not determine provider for instance '{instance_id}'")

    # Terminate the instance
    provider.terminate_instance(instance_id)
    click.echo(f"Terminated instance '{instance_id}' on '{provider_name}'.")