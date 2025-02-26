# gmab/providers/__init__.py

from gmab.providers.linode import LinodeProvider
from gmab.providers.aws import AWSProvider
from gmab.providers.hetzner import HetznerProvider

def get_provider(provider_name, provider_cfg):
    """
    Factory function to get the appropriate provider instance.
    
    Args:
        provider_name (str): The name of the provider ('linode', 'aws', or 'hetzner')
        provider_cfg (dict): Provider configuration
        
    Returns:
        ProviderBase: A provider instance
        
    Raises:
        ValueError: If the provider name is unknown or if provider config is invalid
    """
    providers = {
        "linode": LinodeProvider,
        "aws": AWSProvider,
        "hetzner": HetznerProvider
    }
    
    provider_class = providers.get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    if not provider_cfg:
        raise ValueError(f"Missing or empty configuration for provider: {provider_name}")
    
    provider = provider_class(provider_cfg)
    provider.provider_name = provider_name  # Set the provider name
    return provider