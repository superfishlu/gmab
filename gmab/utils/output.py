# gmab/utils/output.py
#
# Output-format helpers shared by the CLI commands. gmab prints human-readable
# tables by default, but every machine-facing command also supports `-o json`
# (and a `output_format` default in config.json) for use in automation.

import json

import click

from gmab.utils.config_loader import load_config, ConfigNotFoundError

OUTPUT_FORMATS = ("text", "json")


def resolve_output_format(output_opt):
    """
    Resolve the effective output format. The `-o/--output` flag wins; otherwise
    fall back to `output_format` in config.json, then to "text".
    """
    if output_opt:
        return output_opt
    try:
        return load_config("config.json").get("output_format", "text")
    except (ConfigNotFoundError, Exception):
        return "text"


def emit_json(obj, err=False):
    """Print an object as pretty JSON (datetimes etc. are stringified). Set
    err=True to write to stderr (e.g. a preview that must not pollute a stdout
    JSON result)."""
    click.echo(json.dumps(obj, indent=2, default=str), err=err)


def instance_to_json(inst):
    """A clean, JSON-serializable view of a gmab instance dict."""
    lifetime_left = inst.get("lifetime_left")
    return {
        "provider": inst.get("provider"),
        "instance_id": inst.get("instance_id"),
        "label": inst.get("label"),
        "ip": inst.get("ip"),
        "status": inst.get("status"),
        "region": inst.get("region"),
        "image": inst.get("image"),
        "creation_time": inst.get("creation_time"),
        "lifetime_minutes": inst.get("lifetime_minutes"),
        "lifetime_left_minutes": int(lifetime_left) if lifetime_left is not None else None,
        "is_expired": inst.get("is_expired"),
    }
