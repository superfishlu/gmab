# gmab/cli.py

import sys
import time

import click
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from gmab.commands.spawn import spawn_box
from gmab.commands.terminate import terminate_box
from gmab.commands.list import list_boxes, get_detailed_instances
from gmab.commands.configure import run_configure, print_configs
from gmab.utils.config_loader import config_exists, ConfigNotFoundError, load_config
from gmab.utils.output import resolve_output_format, emit_json, instance_to_json, OUTPUT_FORMATS
from gmab.providers import get_available_providers
from gmab import __version__


def _emit_terminate_result(fmt, terminated, failed):
    """Emit a terminate summary as JSON or human-readable text."""
    if fmt == 'json':
        emit_json({
            "terminated": terminated,
            "failed": failed,
            "terminated_count": len(terminated),
            "failed_count": len(failed),
        })
        return
    if terminated:
        click.echo(f"Successfully terminated {len(terminated)} instance(s).")
    if failed:
        click.echo("\nFailed to terminate the following instances:")
        for item in failed:
            click.echo(f"- {item['instance_id']}: {item['error']}")


# gmab list columns: (key, header, kind). 'flex' columns wrap their content
# (overflow="fold") so long values (OVH's 36-char UUID instance IDs, the
# timestamp-encoded labels) are shown in full across lines instead of being
# truncated; 'fixed' columns are short and never wrap.
LIST_COLUMNS = [
    ('provider', 'Provider', 'fixed'),
    ('instance_id', 'Instance ID', 'flex'),
    ('label', 'Label', 'flex'),
    ('ip', 'IP Address', 'fixed'),
    ('status', 'Status', 'fixed'),
    ('region', 'Region', 'fixed'),
    ('image', 'Image', 'flex'),
    ('time_left', 'Time Left', 'fixed'),
]


def select_list_columns(width):
    """
    Pick which columns to show for a given terminal width. Provider, Label, IP,
    Status and Time Left are always kept; the rest are shed as space runs out, in
    order of least usefulness: Image first, then the wide (and Label-redundant)
    Instance ID, then Region. Label is never dropped; it's the copy-paste handle
    for `terminate`.
    """
    dropped = set()
    if width < 120:
        dropped.add('image')
    if width < 100:
        dropped.add('instance_id')
    if width < 80:
        dropped.add('region')
    return [key for key, _, _ in LIST_COLUMNS if key not in dropped]


def _instance_cell(key, value):
    """
    Build a rich Text cell. Status and Time Left get accent colors (orange for an
    expired status, green for running, red for an expired Time Left); every other
    cell is plain. Using Text (not markup strings) means instance values are never
    accidentally parsed as rich markup.
    """
    low = value.lower()
    if key == 'status':
        if 'expired' in low:
            return Text(value, style='dark_orange')
        if low in ('running', 'active'):
            return Text(value, style='green')
    if key == 'time_left' and value == 'expired':
        return Text(value, style='red')
    return Text(value)


def render_instances_table(instances):
    """
    Render gmab instances as a responsive rich table that auto-sizes to the
    terminal, wraps long cells, drops low-priority columns when too narrow, and
    draws a separator line between instances.
    """
    console = Console()
    keep = select_list_columns(console.width)

    headers = {key: header for key, header, _ in LIST_COLUMNS}
    kinds = {key: kind for key, _, kind in LIST_COLUMNS}

    table = Table(box=_table_box(), show_lines=True)
    for key in keep:
        if kinds[key] == 'flex':
            table.add_column(headers[key], overflow='fold')
        else:
            table.add_column(headers[key], no_wrap=True)

    for instance in instances:
        lifetime_left = instance.get('lifetime_left')
        if lifetime_left is None:
            time_left = '?'
        elif lifetime_left < 1:
            time_left = 'expired'
        else:
            time_left = f"{int(lifetime_left)}m"
        values = {
            'provider': str(instance.get('provider', 'Unknown')),
            'instance_id': str(instance.get('instance_id', 'Unknown')),
            'label': str(instance.get('label', 'Unknown')),
            'ip': str(instance.get('ip', 'No IP')),
            'status': str(instance.get('status', 'Unknown')),
            'region': str(instance.get('region', 'Unknown')),
            'image': str(instance.get('image', 'Unknown')),
            'time_left': time_left,
        }
        table.add_row(*(_instance_cell(key, values[key]) for key in keep))

    console.print(table)


def _table_box():
    """Rounded borders, falling back to ASCII when the console can't encode them."""
    encoding = (getattr(sys.stdout, 'encoding', '') or '').lower()
    return box.ROUNDED if encoding in ('utf-8', 'utf8', 'cp65001') else box.ASCII


def _human_time(ts):
    """Format a unix timestamp as local time; '-' when unknown."""
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return '-'
    if ts <= 0:
        return '-'
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))


def _flatten(value, prefix=''):
    """Flatten a nested dict/list into {dotted.key: scalar} for the verbose view."""
    rows = {}
    if isinstance(value, dict):
        if not value:
            rows[prefix or 'value'] = '{}'
        for k, v in value.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            rows.update(_flatten(v, key))
    elif isinstance(value, (list, tuple)):
        if not value:
            rows[prefix or 'value'] = '[]'
        for i, v in enumerate(value):
            rows.update(_flatten(v, f"{prefix}[{i}]"))
    else:
        rows[prefix or 'value'] = value
    return rows


def render_instance_detail(inst, raw, extras, verbose):
    """
    Render one instance as a two-column (Field / Value) table. Non-verbose shows
    a curated set (the common fields plus the provider's detail_extras); verbose
    dumps the entire provider API payload (flattened).
    """
    console = Console()
    table_box = _table_box()
    sep = '·' if table_box is box.ROUNDED else '-'  # keep the title ASCII-safe too
    title = f"{inst.get('provider', '?')}  {sep}  {inst.get('label', '?')}"
    table = Table(box=table_box, title=title, title_justify='left')
    table.add_column('Field', no_wrap=True, style='bold')
    table.add_column('Value', overflow='fold')

    if verbose:
        flat = _flatten(raw)
        for key in sorted(flat):
            table.add_row(str(key), Text(str(flat[key])))
    else:
        lifetime_left = inst.get('lifetime_left', 0)
        time_left = 'expired' if lifetime_left < 1 else f"{int(lifetime_left)}m"
        rows = [
            ('Provider', inst.get('provider')),
            ('Instance ID', inst.get('instance_id')),
            ('Label', inst.get('label')),
            ('Status', inst.get('status')),
            ('IP', inst.get('ip')),
            ('Region', inst.get('region')),
            ('Image', inst.get('image')),
            ('Created', _human_time(inst.get('creation_time'))),
            ('Lifetime', f"{inst.get('lifetime_minutes')}m"),
            ('Time left', time_left),
        ] + list(extras)
        for label, value in rows:
            if value is None or value == '':
                continue
            table.add_row(str(label), Text(str(value)))

    console.print(table)


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

@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name='gmab',message='%(prog)s %(version)s')
@click.pass_context
def cli(ctx):
    """ gmab (Give Me A Box) - CLI tool to spawn, list, and manage temporary cloud boxes. """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@cli.command()
@click.option('--provider', '-p', default=None, help='Provider name (default from config).')
@click.option('--region', '-r', default=None, help='Override region (default from config).')
@click.option('--image', '-i', default=None, help='Override image (default from config).')
@click.option('--lifetime', '-t', type=int, default=None, help='Lifetime in minutes (default: 60).')
@click.option('--output', '-o', type=click.Choice(OUTPUT_FORMATS), default=None,
              help='Output format (default from config, else text).')
def spawn(provider, region, image, lifetime, output):
    """ Spawn a new instance. """
    if not check_config_exists():
        return
    fmt = resolve_output_format(output)
    try:
        if provider and provider not in get_configured_providers():
            click.echo(f"Error: Provider '{provider}' is not configured.")
            click.echo(f"Please run 'gmab configure -p {provider}' to configure this provider.")
            return

        spawn_box(provider, region, image, lifetime, output=fmt)
    except ConfigNotFoundError:
        click.echo("Error: GMAB is not configured.")
        click.echo("Please run 'gmab configure' to set up your configuration.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@cli.command()
@click.argument('instance_ids', nargs=-1)
@click.option('--provider', '-p', default=None, help='Provider name (default from config).')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt.')
@click.option('--output', '-o', type=click.Choice(OUTPUT_FORMATS), default=None,
              help='Output format (default from config, else text).')
def terminate(instance_ids, provider, yes, output):
    """ Terminate one or more instances by ID or label.

    Use 'all' to terminate all instances, or 'expired' to terminate expired instances.
    Asks for y/n confirmation in every case; pass -y/--yes to skip the prompt.
    Use -o json for machine-readable output (the prompt, if any, goes to stderr).
    """
    if not check_config_exists():
        return

    fmt = resolve_output_format(output)

    def preview(instances, header):
        """Show what will be terminated before the prompt. Text mode prints the
        rich table to stdout; JSON mode prints a JSON 'plan' to stderr, so stdout
        stays a single result document."""
        if fmt == 'json':
            emit_json([instance_to_json(i) for i in instances], err=True)
        else:
            click.echo(header)
            render_instances_table(instances)

    def confirm_or_abort():
        """Return True to proceed. Honors -y; emits the cancellation output."""
        if yes:
            return True
        # In JSON mode the prompt goes to stderr so stdout stays valid JSON.
        if click.confirm("Do you want to proceed?", err=(fmt == 'json')):
            return True
        if fmt == 'json':
            emit_json({"cancelled": True, "terminated": [], "failed": [],
                       "terminated_count": 0, "failed_count": 0})
        else:
            click.echo("Operation cancelled.")
        return False

    def nothing(message):
        """Report that there's nothing to terminate."""
        if fmt == 'json':
            emit_json({"terminated": [], "failed": [], "terminated_count": 0,
                       "failed_count": 0, "message": message})
        else:
            click.echo(message)

    def run(instances):
        """Terminate instance dicts; return (terminated, failed) result lists."""
        terminated, failed = [], []
        for inst in instances:
            try:
                terminate_box(inst['instance_id'], inst['provider'], quiet=(fmt == 'json'))
                terminated.append({"provider": inst['provider'],
                                   "instance_id": inst['instance_id'],
                                   "label": inst.get('label')})
            except Exception as e:
                failed.append({"instance_id": inst['instance_id'], "error": str(e)})
        return terminated, failed

    try:
        if provider and provider not in get_configured_providers():
            click.echo(f"Error: Provider '{provider}' is not configured.")
            click.echo(f"Please run 'gmab configure -p {provider}' to configure this provider.")
            return

        # Handle 'expired'
        if len(instance_ids) == 1 and instance_ids[0] == 'expired':
            instances = list_boxes(provider)
            expired_instances = [i for i in instances if i.get('is_expired', False)]
            if not expired_instances:
                nothing("No expired instances found." if instances else "No active instances found.")
                return
            if not yes:
                preview(expired_instances, "The following expired instances will be terminated:")
            if not confirm_or_abort():
                return
            _emit_terminate_result(fmt, *run(expired_instances))
            return

        # Handle 'all'
        if len(instance_ids) == 1 and instance_ids[0] == 'all':
            instances = list_boxes(provider)
            if not instances:
                nothing("No active instances found.")
                return
            if not yes:
                preview(instances, "The following instances will be terminated:")
            if not confirm_or_abort():
                return
            _emit_terminate_result(fmt, *run(instances))
            return

        # Specific ids/labels
        if not instance_ids:
            nothing("No instance IDs or labels provided.")
            return
        if len(instance_ids) > 5:
            click.echo("Error: Cannot terminate more than 5 instances at once.")
            return

        if not yes:
            # Resolve the given ids/labels to full instance dicts so the preview
            # matches `list`; fall back to a minimal "not found" row for anything
            # we can't look up (terminate_box surfaces the real error on proceed).
            try:
                known = list_boxes(provider)
            except Exception:
                known = []
            by_id = {i['instance_id']: i for i in known}
            by_label = {i['label']: i for i in known}
            rows = []
            for ident in instance_ids:
                match = by_id.get(ident) or by_label.get(ident)
                rows.append(match or {
                    "provider": provider or "?", "instance_id": ident, "label": "",
                    "ip": "", "status": "not found", "region": "", "image": "",
                    "lifetime_left": None,
                })
            noun = "instance" if len(instance_ids) == 1 else "instances"
            preview(rows, f"The following {noun} will be terminated:")

        if not confirm_or_abort():
            return

        terminated, failed = [], []
        for ident in instance_ids:
            try:
                terminate_box(ident, provider, quiet=(fmt == 'json'))
                terminated.append({"provider": provider, "instance_id": ident, "label": None})
            except Exception as e:
                failed.append({"instance_id": ident, "error": str(e)})
        _emit_terminate_result(fmt, terminated, failed)

    except ConfigNotFoundError:
        click.echo("Error: GMAB is not configured.")
        click.echo("Please run 'gmab configure' to set up your configuration.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@cli.command(name='list')  # Explicitly name the command
@click.option('--provider', '-p',
              help='Provider name (list all providers if not specified).')
@click.option('--output', '-o', type=click.Choice(OUTPUT_FORMATS), default=None,
              help='Output format (default from config, else text).')
@click.argument('args', nargs=-1)
def list_command(provider, output, args):  # Renamed from 'list' to avoid conflicts
    """List active instances.

    Plain `gmab list` shows the summary table. `gmab list detail` shows a
    per-instance detail table; add `verbose` to dump the full provider API
    response. Pass an instance id or label to show just that one instance.
    Use `-o json` for machine-readable output.

    \b
    Examples:
      gmab list                       summary table for all instances
      gmab list detail                detail table for every instance
      gmab list detail verbose        full API dump for every instance
      gmab list detail <id|label>     detail for a single instance
      gmab list -o json               summary as JSON
    """
    if not check_config_exists():
        return

    fmt = resolve_output_format(output)

    # 'detail' and 'verbose' are mode keywords (like terminate's 'all'/'expired');
    # any other argument is treated as a target instance id or label.
    tokens = [a.lower() for a in args]
    detail = 'detail' in tokens
    verbose = 'verbose' in tokens
    targets = [a for a in args if a.lower() not in ('detail', 'verbose')]
    target = targets[0] if targets else None
    # A bare target or 'verbose' implies the detail view.
    if target or verbose:
        detail = True

    try:
        # Check if provider is configured
        if provider and provider not in get_configured_providers():
            click.echo(f"Error: Provider '{provider}' is not configured.")
            click.echo(f"Please run 'gmab configure -p {provider}' to configure this provider.")
            return

        if detail:
            details = get_detailed_instances(provider, target)
            if fmt == 'json':
                payload = []
                for inst, raw, extras in details:
                    entry = instance_to_json(inst)
                    if verbose:
                        entry['details'] = raw
                    else:
                        entry['extras'] = dict(extras)
                    payload.append(entry)
                emit_json(payload)
                return
            if not details:
                click.echo("No active instances found.")
                return
            for inst, raw, extras in details:
                render_instance_detail(inst, raw, extras, verbose)
            return

        instances = list_boxes(provider)
        if fmt == 'json':
            emit_json([instance_to_json(i) for i in instances])
            return
        if not instances or len(instances) == 0:
            click.echo("No active instances found.")
            return

        render_instances_table(instances)

    except ConfigNotFoundError:
        click.echo("Error: GMAB is not configured.")
        click.echo("Please run 'gmab configure' to set up your configuration.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@cli.command()
@click.option(
    '--provider', '-p',
    type=click.Choice(['all'] + get_available_providers()),
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