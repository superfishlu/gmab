# gmab/commands/terminate.py

import click
from gmab.utils.config_loader import load_config, ConfigNotFoundError
from gmab.providers import get_provider, get_registry

def get_instance_provider(instance_identifier, providers_cfg):
    """
    Determine which provider an instance belongs to based on ID format and provider queries.
    Returns tuple of (provider_name, provider_instance) or (None, None) if not found.
    
    Args:
        instance_identifier (str): The instance ID or label
        providers_cfg (dict): The provider configurations
        
    Returns:
        tuple: (provider_name, provider_instance) or (None, None) if not found
    """
    # Fast path: if a provider recognizes this identifier as its own native ID
    # format (e.g. AWS "i-..."), use it directly when it's configured.
    for provider_name, provider_class in get_registry().items():
        if provider_class.claims_identifier(instance_identifier) and providers_cfg.get(provider_name):
            provider = get_provider(provider_name, providers_cfg[provider_name])
            return provider_name, provider

    # Otherwise (labels, numeric IDs, unconfigured fast-path), query each provider
    for provider_name, provider_cfg in providers_cfg.items():
        if not provider_cfg:  # Skip empty provider configs
            continue
            
        provider = get_provider(provider_name, provider_cfg)
        try:
            instances = provider.list_instances()
            
            for instance in instances:
                if (instance['instance_id'] == instance_identifier or 
                    instance['label'] == instance_identifier):
                    return provider_name, provider
        except Exception:
            # Skip providers that fail to list instances
            continue

    return None, None

def terminate_box(instance_id, provider_name=None):
    """
    Terminate an instance by ID or label.
    
    Args:
        instance_id (str): The instance ID or label to terminate
        provider_name (str, optional): The provider name. If None, it will be determined from the instance ID.
        
    Raises:
        ConfigNotFoundError: If configuration files don't exist
        ValueError: If the provider can't be determined or found
        Exception: For other errors
    """
    try:
        # Load configs
        providers_cfg = load_config("providers.json")
        general_cfg = load_config("config.json")

        if provider_name:
            # If provider is specified, use it directly
            provider_cfg = providers_cfg.get(provider_name)
            if not provider_cfg:
                raise ValueError(f"Provider '{provider_name}' is not configured. Run 'gmab configure -p {provider_name}' first.")
            provider = get_provider(provider_name, provider_cfg)
        else:
            # Try to determine provider from instance ID
            provider_name, provider = get_instance_provider(instance_id, providers_cfg)
            if not provider:
                raise ValueError(f"Could not determine provider for instance '{instance_id}'. Make sure the provider is configured.")

        # Terminate the instance
        provider.terminate_instance(instance_id)
        click.echo(f"Terminated instance '{instance_id}' on '{provider_name}'.")
        
    except ConfigNotFoundError:
        # Let the CLI handle this error
        raise
    except Exception as e:
        # Re-raise with a more informative message
        raise Exception(f"Failed to terminate instance: {str(e)}")