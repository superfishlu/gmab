# gmab/providers/base.py

import functools
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import click


@dataclass
class ConfigField:
    """
    Declarative description of a single provider configuration field.

    A provider exposes its configuration surface as a list of these on
    ``CONFIG_SCHEMA``. The base class derives the default config, the interactive
    prompts, credential validation, and secret-masking from that one declaration,
    so providers never hand-write that boilerplate.

    Args:
        key (str): The config key as stored in providers.json (e.g. "api_key").
        label (str): Human-readable prompt label shown during `gmab configure`.
        default (str): Default value used when the field is unset.
        secret (bool): If True, the value is masked by `configure --print`.
        required (bool): If True, the value must be non-empty for the provider to
            be considered fully configured (enforced by validate_config()).
    """
    key: str
    label: str
    default: str = ""
    secret: bool = False
    required: bool = False


class ProviderBase(ABC):
    """
    Abstract base class for all providers.

    Subclasses must set ``name`` (the registry key, e.g. "linode") and
    ``CONFIG_SCHEMA`` (a list of ConfigField), then implement the four instance
    lifecycle methods. Everything else (defaults, prompts, validation, label
    generation, SSH key reading, expiry math) is provided here.
    """

    # Registry key for this provider, e.g. "linode". Subclasses must override.
    name = None

    # Declarative configuration surface. Subclasses must override.
    CONFIG_SCHEMA = []

    def __init__(self, provider_cfg):
        """
        Initialize the provider with configuration.

        Args:
            provider_cfg (dict): Provider configuration containing credentials, defaults, etc.
                e.g. {
                  "api_key": "...",
                  "default_region": "...",
                  "default_image": "..."
                }
        """
        self.provider_cfg = provider_cfg
        self.provider_name = self.name  # Kept for backward compatibility

    # --- Configuration surface (derived from CONFIG_SCHEMA) ------------------

    @classmethod
    def get_default_config(cls):
        """Return the default configuration dict derived from CONFIG_SCHEMA."""
        return {field.key: field.default for field in cls.CONFIG_SCHEMA}

    @classmethod
    def get_config_prompts(cls, provider_config):
        """
        Return a dict of click.prompt partials for interactive configuration,
        one per CONFIG_SCHEMA field, pre-filled with any existing value.
        """
        prompts = {}
        for field in cls.CONFIG_SCHEMA:
            prompts[field.key] = functools.partial(
                click.prompt,
                field.label,
                default=provider_config.get(field.key, field.default),
                hide_input=False,
            )
        return prompts

    @classmethod
    def validate_config(cls, provider_config):
        """
        Return a list of required config keys that are missing/empty.
        An empty list means the provider is fully configured.
        """
        return [
            field.key
            for field in cls.CONFIG_SCHEMA
            if field.required and not provider_config.get(field.key)
        ]

    @classmethod
    def secret_keys(cls):
        """Return the config keys that hold sensitive values (for masking)."""
        return [field.key for field in cls.CONFIG_SCHEMA if field.secret]

    # --- Shared lifecycle helpers -------------------------------------------

    @staticmethod
    def is_expired(creation_time, lifetime_minutes):
        """Return True if an instance created at creation_time has outlived its lifetime."""
        return (int(time.time()) - int(creation_time)) > (int(lifetime_minutes) * 60)

    def _read_ssh_key(self, ssh_key_path=None):
        """
        Read the SSH public key contents from the given path, falling back to the
        provider config's ssh_key_path and finally to ~/.ssh/id_ed25519.pub.

        Raises:
            FileNotFoundError: If the key file does not exist.
        """
        ssh_key_path = ssh_key_path or self.provider_cfg.get("ssh_key_path", "~/.ssh/id_ed25519.pub")
        keyfile = Path(ssh_key_path).expanduser()
        if not keyfile.exists():
            raise FileNotFoundError(f"SSH key not found at {keyfile}")
        with open(keyfile, 'r') as f:
            return f.read().strip()

    def find_instance_id_by_label(self, label):
        """
        Default label->id lookup that scans list_instances(). Providers with a
        cheaper native query (e.g. AWS) may override this.

        Returns:
            str or None: The instance ID if a gmab instance with that label exists.
        """
        for instance in self.list_instances():
            if instance["label"] == label:
                return instance["instance_id"]
        return None

    @classmethod
    def claims_identifier(cls, identifier):
        """
        Return True if the given instance identifier is unambiguously this
        provider's native ID format (e.g. AWS "i-..."). Used by `terminate` as a
        fast path to skip querying every provider. Defaults to False.
        """
        return False

    def ssh_user(self, image=None):
        """
        The SSH login user for instances spawned by this provider, used for the
        post-spawn connect hint. Linode and Hetzner enable root login on their
        default images; providers whose images use a non-root user override this.
        """
        return "root"

    # --- Detail view (gmab list detail / detail verbose) --------------------

    def get_instance_details(self, instance_id):
        """
        Return the full provider/API representation of a single instance, used by
        `gmab list detail [verbose]`. The default falls back to the basic dict
        from list_instances(); providers override this to fetch the richer
        single-instance API payload (which `verbose` renders in full).

        Returns:
            dict: provider-specific instance details (possibly nested).
        """
        for instance in self.list_instances():
            if instance["instance_id"] == str(instance_id):
                return instance
        return {}

    def detail_extras(self, raw):
        """
        Return provider-specific (label, value) rows for the non-verbose
        `gmab list detail` view: the handful of fields worth surfacing beyond
        the common ones (e.g. VPC/subnet for AWS, flavor for OVH). Defaults to
        none. `raw` is whatever get_instance_details() returned.

        Returns:
            list[tuple[str, Any]]: ordered (label, value) pairs.
        """
        return []

    # --- Required provider-specific implementations -------------------------

    @abstractmethod
    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        """
        Create an instance on the provider and return minimal details.

        Args:
            image (str, optional): The image to use for the instance
            region (str, optional): The region to create the instance in
            ssh_key_path (str, optional): Path to the SSH public key to use
            lifetime_minutes (int, optional): Lifetime of the instance in minutes

        Returns:
            dict: A dictionary with at least these keys:
                {
                    "provider": "provider_name",
                    "instance_id": "provider-specific-id",
                    "label": "instance-name",
                    "ip": "ip-address",
                    "status": "status",
                    "region": "region",
                    "image": "image",
                    "creation_time": unix_timestamp,
                    "lifetime_minutes": minutes
                }

        Raises:
            Exception: If the instance creation fails
        """
        pass

    @abstractmethod
    def terminate_instance(self, instance_id):
        """
        Terminate an instance by ID or name.

        Args:
            instance_id (str): The ID or name of the instance to terminate

        Raises:
            Exception: If the termination fails
        """
        pass

    @abstractmethod
    def list_instances(self):
        """
        List all instances tagged with 'gmab'.

        Returns:
            list: A list of dictionaries with the same structure as spawn_instance() returns

        Raises:
            Exception: If listing instances fails
        """
        pass

    @abstractmethod
    def list_expired_instances(self):
        """
        List all expired instances.

        Returns:
            list: A list of dictionaries with the same structure as list_instances() returns,
                 but only including expired instances

        Raises:
            Exception: If listing expired instances fails
        """
        pass
