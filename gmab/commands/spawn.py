# gmab/commands/spawn.py

import click
from gmab.utils.config_loader import load_config, ConfigNotFoundError
from gmab.providers import get_provider

def spawn_box(provider_name=None, region=None, image=None, lifetime=None):
    """Spawn a new cloud instance with the specified parameters."""
    try:
        # Load main configs
        general_cfg = load_config("config.json")
        providers_cfg = load_config("providers.json")

        # Determine provider
        if not provider_name:
            provider_name = general_cfg.get("default_provider", "linode")

        # Retrieve provider's config
        provider_cfg = providers_cfg.get(provider_name)
        if not provider_cfg:
            raise ValueError(f"Provider '{provider_name}' is not configured. Run 'gmab configure -p {provider_name}' first.")

        # Determine region and image
        chosen_region = region or provider_cfg.get("default_region", "us-east")
        chosen_image = image or provider_cfg.get("default_image", "linode/ubuntu22.04")
        chosen_lifetime = lifetime or general_cfg.get("default_lifetime_minutes", 60)

        # Instantiate provider
        provider = get_provider(provider_name, provider_cfg)

        # Spawn instance
        instance_info = provider.spawn_instance(
            image=chosen_image,
            region=chosen_region,
            ssh_key_path=general_cfg["ssh_key_path"],
            lifetime_minutes=chosen_lifetime
        )

        click.echo(f"Spawned '{provider_name}' instance:")
        click.echo(f"  ID: {instance_info['instance_id']}")
        click.echo(f"  Label: {instance_info['label']}")
        click.echo(f"  IP: {instance_info['ip']}")
        click.echo(f"  Connect via: ssh root@{instance_info['ip']}")
        
        return instance_info
    
    except ConfigNotFoundError:
        # Let the CLI handle this error
        raise
    except Exception as e:
        raise Exception(f"Failed to spawn instance: {str(e)}")