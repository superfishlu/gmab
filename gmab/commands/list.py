# gmab/commands/list.py

from gmab.providers import get_provider
from gmab.utils.config_loader import load_config, ConfigNotFoundError
import time
import click

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
    
    Args:
        provider_name (str, optional): The provider to list instances from. If None, list from all providers.
        
    Returns:
        list: A list of instance dictionaries with provider, instance_id, label, etc.
        
    Raises:
        ConfigNotFoundError: If configuration files don't exist
        ValueError: If the specified provider configuration is not found
        Exception: For other errors
    """
    try:
        # Load provider configuration from config file
        providers_config = load_config("providers.json")
        general_config = load_config("config.json")

        instances = []
        
        # If no provider specified, try to list from all configured providers
        if provider_name is None:
            # Now we only iterate over providers that actually have a configuration
            for provider_name, provider_cfg in providers_config.items():
                if not provider_cfg:  # Skip empty configs
                    continue
                    
                try:
                    provider = get_provider(provider_name, provider_cfg)
                    provider_instances = provider.list_instances()
                    instances.extend(provider_instances)
                except Exception as e:
                    click.echo(f"Warning: Failed to list instances from provider '{provider_name}': {str(e)}")
        else:
            # List instances from specific provider
            provider_cfg = providers_config.get(provider_name)
            if not provider_cfg:
                raise ValueError(f"Provider '{provider_name}' is not configured. Run 'gmab configure -p {provider_name}' first.")

            provider = get_provider(provider_name, provider_cfg)
            instances = provider.list_instances()

        # Calculate lifetime left for each instance and add it to the instance data
        for instance in instances:
            instance['lifetime_left'] = get_lifetime_left(instance)

        # Sort instances by lifetime left (descending)
        instances.sort(key=lambda x: x['lifetime_left'], reverse=True)

        return instances
        
    except ConfigNotFoundError:
        # Let the CLI handle this error
        raise
    except Exception as e:
        # Re-raise with a more informative message
        raise Exception(f"Failed to list instances: {str(e)}")


def get_detailed_instances(provider_name=None, target=None):
    """
    Gather per-instance details for `gmab list detail [verbose]`.

    Args:
        provider_name (str, optional): Restrict to one provider.
        target (str, optional): An instance id or label; if given, only that
            instance is returned, otherwise all matching instances are.

    Returns:
        list[tuple[dict, dict, list]]: (instance, raw_details, detail_extras) per
            instance, where `instance` is the standard list dict, `raw_details` is
            the full provider API payload, and `detail_extras` is the provider's
            curated (label, value) rows.

    Raises:
        ConfigNotFoundError: If configuration files don't exist.
        ValueError: If `target` matches no instance.
    """
    instances = list_boxes(provider_name)

    if target:
        instances = [i for i in instances if target in (i['instance_id'], i['label'])]
        if not instances:
            raise ValueError(f"No instance found matching '{target}'.")

    providers_config = load_config("providers.json")
    results = []
    for inst in instances:
        provider_cfg = providers_config.get(inst['provider'])
        provider = get_provider(inst['provider'], provider_cfg)
        try:
            raw = provider.get_instance_details(inst['instance_id'])
        except Exception as e:
            raw = {"error": str(e)}
        try:
            extras = provider.detail_extras(raw)
        except Exception:
            extras = []
        results.append((inst, raw, extras))

    return results