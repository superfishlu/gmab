# gmab/cli.py

import click
from gmab.commands.spawn import spawn_box
from gmab.commands.terminate import terminate_box
from gmab.commands.list import list_boxes
from gmab.commands.configure import run_configure, print_configs
from gmab.utils.config_loader import DEFAULT_PROVIDERS_CONFIG, config_exists, ConfigNotFoundError, load_config

def check_config_exists():
    """Check if config exists and show an error message if it doesn't."""
    if not config_exists():
        click.echo("Error: GMAB is not configured.")
        click.echo("Please run 'gmab configure' to set up your configuration.")
        return False
    return True

def get_configured_providers():
    """Get a list of providers that have been explicitly configured."""
    try:
        providers_config = load_config("providers.json")
        return list(providers_config.keys())
    except (ConfigNotFoundError, Exception):
        return []

@click.group()
def cli():
    """ gmab (Give Me A Box) - CLI tool to spawn, list, and manage temporary cloud boxes. """
    pass

@cli.command()
@click.option('--provider', '-p', default=None, help='Provider name (default from config).')
@click.option('--region', '-r', default=None, help='Override region (default from config).')
@click.option('--image', '-i', default=None, help='Override image (default from config).')
@click.option('--lifetime', '-t', type=int, default=None, help='Lifetime in minutes (default: 60).')
def spawn(provider, region, image, lifetime):
    """ Spawn a new instance. """
    if not check_config_exists():
        return
    try:
        if provider and provider not in get_configured_providers():
            click.echo(f"Error: Provider '{provider}' is not configured.")
            click.echo(f"Please run 'gmab configure -p {provider}' to configure this provider.")
            return
            
        spawn_box(provider, region, image, lifetime)
    except ConfigNotFoundError:
        click.echo("Error: GMAB is not configured.")
        click.echo("Please run 'gmab configure' to set up your configuration.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@cli.command()
@click.argument('instance_ids', nargs=-1)
@click.option('--provider', '-p', default=None, help='Provider name (default from config).')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt.')
def terminate(instance_ids, provider, yes):
    """ Terminate one or more instances by ID or label. 
    
    Use 'all' to terminate all instances, or 'expired' to terminate expired instances.
    """
    if not check_config_exists():
        return
    
    try:
        if provider and provider not in get_configured_providers():
            click.echo(f"Error: Provider '{provider}' is not configured.")
            click.echo(f"Please run 'gmab configure -p {provider}' to configure this provider.")
            return
            
        # Handle 'expired' command
        if len(instance_ids) == 1 and instance_ids[0] == 'expired':
            # Get all instances
            instances = list_boxes(provider)
            if not instances:
                click.echo("No active instances found.")
                return
            
            # Filter expired instances
            expired_instances = [inst for inst in instances if inst.get('is_expired', False)]
            
            if not expired_instances:
                click.echo("No expired instances found.")
                return
            
            # Show what will be terminated
            click.echo("The following expired instances will be terminated:")
            for instance in expired_instances:
                click.echo(f"- {instance['instance_id']} ({instance['provider']}: {instance['label']})")
            
            # Ask for confirmation unless -y flag is used
            if not yes and not click.confirm("Do you want to proceed?"):
                click.echo("Operation cancelled.")
                return
            
            # Terminate expired instances
            success_count = 0
            failed_instances = []
            for instance in expired_instances:
                try:
                    terminate_box(instance['instance_id'], instance['provider'])
                    success_count += 1
                except Exception as e:
                    failed_instances.append((instance['instance_id'], str(e)))
            
            # Print summary
            if success_count > 0:
                click.echo(f"Successfully terminated {success_count} expired instance(s).")
            if failed_instances:
                click.echo("\nFailed to terminate the following instances:")
                for instance_id, error in failed_instances:
                    click.echo(f"- {instance_id}: {error}")
            
            return

        # Handle 'all' command
        if len(instance_ids) == 1 and instance_ids[0] == 'all':
            # Get all instances
            instances = list_boxes(provider)
            if not instances:
                click.echo("No active instances found.")
                return
            
            # Show what will be terminated
            click.echo("The following instances will be terminated:")
            for instance in instances:
                click.echo(f"- {instance['instance_id']} ({instance['provider']}: {instance['label']})")
            
            # Ask for confirmation unless -y flag is used
            if not yes and not click.confirm("Do you want to proceed?"):
                click.echo("Operation cancelled.")
                return
            
            # Terminate all instances
            success_count = 0
            failed_instances = []
            for instance in instances:
                try:
                    terminate_box(instance['instance_id'], instance['provider'])
                    success_count += 1
                except Exception as e:
                    failed_instances.append((instance['instance_id'], str(e)))
            
            # Print summary
            if success_count > 0:
                click.echo(f"Successfully terminated {success_count} instance(s).")
            if failed_instances:
                click.echo("\nFailed to terminate the following instances:")
                for instance_id, error in failed_instances:
                    click.echo(f"- {instance_id}: {error}")
            
            return
        
        # Regular termination logic
        if not instance_ids:
            click.echo("No instance IDs or labels provided.")
            return
            
        if len(instance_ids) > 5:
            click.echo("Error: Cannot terminate more than 5 instances at once.")
            return

        if len(instance_ids) > 1 and not yes:
            # Ask for confirmation when terminating multiple instances
            instances_str = "', '".join(instance_ids)
            if not click.confirm(f"Are you sure you want to terminate instances: '{instances_str}'?"):
                click.echo("Operation cancelled.")
                return

        success_count = 0
        failed_instances = []
        for instance_id in instance_ids:
            try:
                terminate_box(instance_id, provider)
                success_count += 1
            except Exception as e:
                failed_instances.append((instance_id, str(e)))

        # Print summary
        if success_count > 0:
            click.echo(f"Successfully terminated {success_count} instance(s).")
        if failed_instances:
            click.echo("\nFailed to terminate the following instances:")
            for instance_id, error in failed_instances:
                click.echo(f"- {instance_id}: {error}")

    except ConfigNotFoundError:
        click.echo("Error: GMAB is not configured.")
        click.echo("Please run 'gmab configure' to set up your configuration.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@cli.command(name='list')  # Explicitly name the command
@click.option('--provider', '-p', 
              help='Provider name (list all providers if not specified).')
def list_command(provider):  # Renamed from 'list' to avoid conflicts
    """ List active instances. """
    if not check_config_exists():
        return
    
    try:
        # Check if provider is configured
        if provider and provider not in get_configured_providers():
            click.echo(f"Error: Provider '{provider}' is not configured.")
            click.echo(f"Please run 'gmab configure -p {provider}' to configure this provider.")
            return
            
        instances = list_boxes(provider)

        if not instances or len(instances) == 0:
            click.echo("No active instances found.")
            return

        # Updated column widths
        columns = {
            'Provider': 10,
            'Instance ID': 22,
            'Label': 20,
            'IP Address': 18,
            'Status': 20,  # Increased to accommodate "(expired)" suffix
            'Region': 15,
            'Image': 25,
            'Time Left': 15  # Changed from 'Lifetime' to 'Time Left'
        }

        # Print header
        header = (
            f"{'Provider':<{columns['Provider']}} "
            f"{'Instance ID':<{columns['Instance ID']}} "
            f"{'Label':<{columns['Label']}} "
            f"{'IP Address':<{columns['IP Address']}} "
            f"{'Status':<{columns['Status']}} "
            f"{'Region':<{columns['Region']}} "
            f"{'Image':<{columns['Image']}} "
            f"{'Time Left':<{columns['Time Left']}}"
        )
        click.echo(header)
        click.echo("=" * (sum(columns.values()) + len(columns) - 1))

        for instance in instances:
            # Add safety checks for required fields
            provider = instance.get('provider', 'Unknown')
            instance_id = instance.get('instance_id', 'Unknown')
            label = instance.get('label', 'Unknown')
            ip = instance.get('ip', 'No IP')
            status = instance.get('status', 'Unknown')
            region = instance.get('region', 'Unknown')
            image = instance.get('image', 'Unknown')
            
            # Format lifetime left
            lifetime_left = instance.get('lifetime_left', 0)
            if lifetime_left < 1:
                time_left = "expired"
            else:
                time_left = f"{int(lifetime_left)}m"

            click.echo(
                f"{provider:<{columns['Provider']}} "
                f"{instance_id:<{columns['Instance ID']}} "
                f"{label:<{columns['Label']}} "
                f"{ip:<{columns['IP Address']}} "
                f"{status:<{columns['Status']}} "
                f"{region:<{columns['Region']}} "
                f"{image:<{columns['Image']}} "
                f"{time_left:<{columns['Time Left']}}"
            )

    except ConfigNotFoundError:
        click.echo("Error: GMAB is not configured.")
        click.echo("Please run 'gmab configure' to set up your configuration.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@cli.command()
@click.option(
    '--provider', '-p',
    type=click.Choice(['all'] + list(DEFAULT_PROVIDERS_CONFIG.keys())),
    default='all',
    help='Specific provider to configure (default: all providers).'
)
@click.option(
    '--print', 'print_config', is_flag=True,
    help='Print current configuration files and their locations.'
)
def configure(provider, print_config):
    """ Configure GMAB settings and provider credentials. 
    
    This command helps you set up or update your GMAB configuration, including SSH keys,
    provider credentials, and default settings. You can configure all providers or specify
    a single provider to configure.

    The configuration will be stored in your user config directory:
    - Linux/macOS: ~/.config/gmab/
    - Windows: %APPDATA%\\gmab\\
    
    You can override the config location by setting the GMAB_CONFIG_DIR environment variable.
    """
    if print_config:
        print_configs()
    else:
        run_configure(provider)

def main():
    cli()

if __name__ == '__main__':
    main()