# gmab/providers/__init__.py

from gmab.providers.base import ProviderBase, ConfigField
from gmab.providers.registry import get_registry, get_available_providers

# Re-export the shipped provider classes for backward-compatible imports
# (e.g. `from gmab.providers import LinodeProvider`).
from gmab.providers.linode import LinodeProvider
from gmab.providers.aws import AWSProvider
from gmab.providers.hetzner import HetznerProvider
from gmab.providers.ovh import OVHProvider


def get_provider(provider_name, provider_cfg):
    """
    Factory function to get the appropriate provider instance.

    Args:
        provider_name (str): The registered name of the provider (e.g. 'linode').
        provider_cfg (dict): Provider configuration

    Returns:
        ProviderBase: A provider instance

    Raises:
        ValueError: If the provider name is unknown or if provider config is invalid
    """
    provider_class = get_registry().get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}")

    if not provider_cfg:
        raise ValueError(f"Missing or empty configuration for provider: {provider_name}")

    return provider_class(provider_cfg)
