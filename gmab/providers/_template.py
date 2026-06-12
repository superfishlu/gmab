# gmab/providers/_template.py
#
# Reference implementation for adding a new hosting provider to GMAB.
#
# To add a provider:
#   1. Copy this file to gmab/providers/<yourprovider>.py
#   2. Set `name` to the registry key (what users type after `-p`).
#   3. Declare CONFIG_SCHEMA: the credentials + defaults you need.
#   4. Implement the four lifecycle methods below.
#
# That's it. The registry auto-discovers this module on import; you do NOT edit
# the factory, the config loader, the configure command, or the CLI. The leading
# underscore in this filename keeps the template itself out of the registry.
#
# Contract every provider must honor (see gmab/providers/base.py for the helpers
# you inherit): spawn_instance() and list_instances() return dicts with at least
#   provider, instance_id, label, ip, status, region, image,
#   creation_time (unix ts), lifetime_minutes
# Tag/label your instances with "gmab" so list_instances() only ever returns
# gmab-owned resources, which `terminate all` relies on.

import time

from gmab.providers.base import ProviderBase, ConfigField
from gmab.utils.naming import make_label


class TemplateProvider(ProviderBase):
    """Provider implementation for <Your Cloud>."""

    # Registry key: what `gmab spawn -p <name>` matches. Set this to a real
    # value (e.g. "digitalocean") in your copy. Left None here so the template
    # never registers even if the underscore convention is bypassed.
    name = None

    # Declarative config surface. The base class turns this into get_default_config(),
    # the interactive `gmab configure` prompts, validate_config(), and secret masking.
    CONFIG_SCHEMA = [
        ConfigField("api_key", "API Key", secret=True, required=True),
        ConfigField("default_region", "Default region", default="region-1"),
        ConfigField("default_image", "Default image", default="ubuntu-22.04"),
        ConfigField("default_type", "Default instance type", default="small"),
    ]

    # Optional: only override if your provider has an unambiguous native ID
    # format. Returning True lets `terminate` skip querying every provider.
    # @classmethod
    # def claims_identifier(cls, identifier):
    #     return identifier.startswith("inst-")

    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        # Resolve effective values from args, falling back to configured defaults.
        image = image or self.provider_cfg.get("default_image")
        region = region or self.provider_cfg.get("default_region")
        if lifetime_minutes is None:
            lifetime_minutes = 60

        creation_time = int(time.time())
        label = make_label()                       # -> "gmab-<random>"
        ssh_key = self._read_ssh_key(ssh_key_path)  # inherited; raises if missing

        # --- Call your provider's create-instance API here. ------------------
        # Persist creation_time and lifetime_minutes in the instance's tags/labels
        # so list_instances() can recover them later (gmab stores no local DB).
        # Tag the instance with "gmab" so it shows up in list/terminate.
        raise NotImplementedError("Implement spawn_instance() for your provider")

        # return {
        #     "provider": self.provider_name,
        #     "instance_id": str(new_id),
        #     "label": label,
        #     "ip": public_ip,
        #     "status": status,
        #     "region": region,
        #     "image": image,
        #     "creation_time": creation_time,
        #     "lifetime_minutes": lifetime_minutes,
        # }

    def terminate_instance(self, instance_identifier):
        # Accept either a native ID or a gmab label. The inherited
        # find_instance_id_by_label() resolves labels via list_instances().
        if not instance_identifier.isdigit():
            instance_id = self.find_instance_id_by_label(instance_identifier)
            if instance_id is None:
                raise Exception(f"No instance found with label '{instance_identifier}'")
        else:
            instance_id = instance_identifier

        # --- Call your provider's delete-instance API here. ------------------
        raise NotImplementedError("Implement terminate_instance() for your provider")

    def list_instances(self):
        # Query your provider, filtering to gmab-owned instances only, then for
        # each build the standard dict. Use self.is_expired() for the flag and
        # surface it both as the boolean and in the status string (matches the
        # other providers).
        instances = []
        # for server in api_list_gmab_instances():
        #     creation_time = int(server.tags["gmab-creation-time"])
        #     lifetime_minutes = int(server.tags["gmab-lifetime"])
        #     is_expired = self.is_expired(creation_time, lifetime_minutes)
        #     status = f"{server.status} (expired)" if is_expired else server.status
        #     instances.append({
        #         "provider": self.provider_name,
        #         "instance_id": str(server.id),
        #         "label": server.name,
        #         "ip": server.public_ip,
        #         "status": status,
        #         "region": server.region,
        #         "image": server.image,
        #         "creation_time": creation_time,
        #         "lifetime_minutes": lifetime_minutes,
        #         "is_expired": is_expired,
        #     })
        raise NotImplementedError("Implement list_instances() for your provider")
        return instances

    def list_expired_instances(self):
        return [inst for inst in self.list_instances() if inst["is_expired"]]

    # --- Optional: richer `gmab list detail [verbose]` output ----------------
    # The base class provides working defaults (details fall back to the basic
    # list dict; no extras). Override these to surface more from your API.
    #
    # def get_instance_details(self, instance_id):
    #     """Return the full single-instance API payload (verbose renders it all)."""
    #     return api_get_instance(instance_id)
    #
    # def detail_extras(self, raw):
    #     """Provider-specific (label, value) rows for the non-verbose detail view.
    #     Skip fields already shown by gmab (provider, id, label, status, ip,
    #     region, image, created, lifetime, time-left)."""
    #     return [("Flavor", raw.get("flavor")), ("VPC", raw.get("vpc_id"))]
