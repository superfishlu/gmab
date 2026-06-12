# gmab/providers/ovh.py

import time

import ovh
from ovh.exceptions import APIError

from gmab.providers.base import ProviderBase, ConfigField
from gmab.utils.naming import generate_random_string


class OVHProvider(ProviderBase):
    """
    Provider implementation for OVHcloud Public Cloud.

    OVH differs from the simple REST providers in three ways that shape this class:
      * Every call is scoped to a Public Cloud project (``service_name``).
      * Instances carry no arbitrary tags/labels, so gmab's creation-time and
        lifetime are encoded into the instance *name*
        (``gmab-<creation_time>-<lifetime>-<random>``) and list_instances()
        filters on the ``gmab-`` prefix.
      * ``flavorId``/``imageId`` are region-specific UUIDs. Users configure human
        names (``d2-2``, ``Ubuntu 22.04``) which are resolved to UUIDs per-region
        at spawn time, so the defaults don't rot the way raw UUIDs would.
    """

    name = "ovh"

    CONFIG_SCHEMA = [
        ConfigField("application_key", "Application Key", secret=True, required=True),
        ConfigField("application_secret", "Application Secret", secret=True, required=True),
        ConfigField("consumer_key", "Consumer Key", secret=True, required=True),
        ConfigField("service_name", "Public Cloud project ID", required=True),
        ConfigField("endpoint", "API endpoint", default="ovh-eu"),
        ConfigField("default_region", "Default region", default="GRA9"),
        ConfigField("default_flavor", "Default instance type", default="d2-2"),
        ConfigField("default_image", "Default image", default="Ubuntu 22.04"),
    ]

    def __init__(self, provider_cfg):
        super().__init__(provider_cfg)

        missing = [
            key
            for key in ("application_key", "application_secret", "consumer_key", "service_name")
            if not provider_cfg.get(key)
        ]
        if missing:
            raise ValueError(
                "OVH requires the following config values: " + ", ".join(missing)
            )

        self.service_name = provider_cfg["service_name"]
        self._image_name_cache = {}
        self.client = ovh.Client(
            endpoint=provider_cfg.get("endpoint", "ovh-eu"),
            application_key=provider_cfg["application_key"],
            application_secret=provider_cfg["application_secret"],
            consumer_key=provider_cfg["consumer_key"],
        )

    def ssh_user(self, image=None):
        # OVH's Ubuntu images log in as 'ubuntu' (no root login), like AWS.
        return "ubuntu"

    # --- Helpers -------------------------------------------------------------

    def _base(self):
        return f"/cloud/project/{self.service_name}"

    @staticmethod
    def _public_ipv4(instance):
        """Return the first public IPv4 from an OVH instance, or a placeholder."""
        for addr in instance.get("ipAddresses") or []:
            if addr.get("type") == "public" and addr.get("version") == 4:
                return addr.get("ip", "No IP Assigned")
        return "No IP Assigned"

    @staticmethod
    def _parse_name(name):
        """
        Recover (creation_time, lifetime_minutes) from a gmab-encoded instance
        name 'gmab-<creation>-<lifetime>-<random>'. Falls back to (0, 60) for
        names that don't follow the scheme.
        """
        parts = name.split("-")
        if len(parts) >= 4 and parts[0] == "gmab" and parts[1].isdigit() and parts[2].isdigit():
            return int(parts[1]), int(parts[2])
        return 0, 60

    def _resolve_flavor_id(self, region, flavor_name):
        try:
            flavors = self.client.get(f"{self._base()}/flavor", region=region)
        except APIError as e:
            raise Exception(f"Failed to list OVH flavors: {str(e)}")
        for flavor in flavors:
            if flavor.get("name") == flavor_name:
                return flavor["id"]
        available = ", ".join(sorted({f.get("name", "") for f in flavors}))
        raise Exception(
            f"Flavor '{flavor_name}' not found in region '{region}'. Available: {available}"
        )

    def _resolve_image_name(self, region, image_id):
        """
        Map an OVH imageId (UUID) back to its human name for display, cached per
        region. Falls back to the raw id if the lookup fails; the list endpoint
        only returns imageId, so this keeps `gmab list` readable.
        """
        if not image_id or not region:
            return image_id or "Unknown"
        if region not in self._image_name_cache:
            try:
                images = self.client.get(f"{self._base()}/image", region=region)
                self._image_name_cache[region] = {img["id"]: img["name"] for img in images}
            except APIError:
                self._image_name_cache[region] = {}
        return self._image_name_cache[region].get(image_id, image_id)

    def _resolve_image_id(self, region, image_name):
        try:
            images = self.client.get(f"{self._base()}/image", region=region, osType="linux")
        except APIError as e:
            raise Exception(f"Failed to list OVH images: {str(e)}")
        for image in images:
            if image.get("name") == image_name:
                return image["id"]
        raise Exception(
            f"Image '{image_name}' not found in region '{region}'."
        )

    def _get_or_create_ssh_key(self, region, ssh_key_content):
        """Reuse an existing project SSH key matching the public key, else create one."""
        try:
            keys = self.client.get(f"{self._base()}/sshkey", region=region)
            for key in keys:
                if key.get("publicKey", "").strip() == ssh_key_content.strip():
                    return key["id"]

            created = self.client.post(
                f"{self._base()}/sshkey",
                name=f"gmab-key-{generate_random_string(8)}",
                publicKey=ssh_key_content,
                region=region,
            )
            return created["id"]
        except APIError as e:
            raise Exception(f"Failed to get or create OVH SSH key: {str(e)}")

    # --- Lifecycle -----------------------------------------------------------

    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        chosen_region = region or self.provider_cfg.get("default_region", "GRA9")
        chosen_flavor = self.provider_cfg.get("default_flavor", "d2-2")
        chosen_image = image or self.provider_cfg.get("default_image", "Ubuntu 22.04")

        if lifetime_minutes is None:
            lifetime_minutes = 60

        creation_time = int(time.time())
        instance_name = f"gmab-{creation_time}-{lifetime_minutes}-{generate_random_string(8)}"

        ssh_key_content = self._read_ssh_key(ssh_key_path)

        try:
            flavor_id = self._resolve_flavor_id(chosen_region, chosen_flavor)
            image_id = self._resolve_image_id(chosen_region, chosen_image)
            ssh_key_id = self._get_or_create_ssh_key(chosen_region, ssh_key_content)

            instance = self.client.post(
                f"{self._base()}/instance",
                name=instance_name,
                flavorId=flavor_id,
                imageId=image_id,
                region=chosen_region,
                sshKeyId=ssh_key_id,
                monthlyBilling=False,
            )

            return {
                "provider": self.provider_name,
                "instance_id": str(instance["id"]),
                "label": instance_name,
                "ip": self._public_ipv4(instance),
                "status": instance.get("status", "BUILD"),
                "region": chosen_region,
                "image": chosen_image,
                "creation_time": creation_time,
                "lifetime_minutes": lifetime_minutes,
            }

        except APIError as e:
            raise Exception(f"Failed to create OVH instance: {str(e)}")

    def terminate_instance(self, instance_identifier):
        # gmab labels are the full encoded instance name; anything else is treated
        # as a native OVH instance UUID.
        if instance_identifier.startswith("gmab-"):
            instance_id = self.find_instance_id_by_label(instance_identifier)
            if instance_id is None:
                raise Exception(f"No instance found with label '{instance_identifier}'")
        else:
            instance_id = instance_identifier

        try:
            self.client.delete(f"{self._base()}/instance/{instance_id}")
        except APIError as e:
            raise Exception(f"Failed to terminate OVH instance: {str(e)}")

    def list_instances(self):
        try:
            instances = self.client.get(f"{self._base()}/instance")
        except APIError as e:
            raise Exception(f"Failed to list OVH instances: {str(e)}")

        result = []
        for instance in instances:
            name = instance.get("name", "")
            if not name.startswith("gmab-"):
                continue

            creation_time, lifetime_minutes = self._parse_name(name)
            is_expired = self.is_expired(creation_time, lifetime_minutes)
            # Normalize OVH's OpenStack status to match the other providers
            # ("ACTIVE" -> "running"); lower-case the rest (e.g. BUILD -> build).
            raw_status = instance.get("status", "UNKNOWN")
            base_status = "running" if raw_status == "ACTIVE" else raw_status.lower()
            status = f"{base_status} (expired)" if is_expired else base_status

            result.append({
                "provider": self.provider_name,
                "instance_id": str(instance["id"]),
                "label": name,
                "ip": self._public_ipv4(instance),
                "status": status,
                "region": instance.get("region", "Unknown"),
                "image": self._resolve_image_name(
                    instance.get("region", ""), instance.get("imageId", "")
                ),
                "creation_time": creation_time,
                "lifetime_minutes": lifetime_minutes,
                "is_expired": is_expired,
            })

        return result

    def list_expired_instances(self):
        return [inst for inst in self.list_instances() if inst["is_expired"]]

    def get_instance_details(self, instance_id):
        """Fetch the full OVH instance object for the detail view."""
        try:
            return self.client.get(f"{self._base()}/instance/{instance_id}")
        except APIError as e:
            raise Exception(f"Failed to get OVH instance details: {str(e)}")

    def detail_extras(self, raw):
        # Image/Created are already in the common detail rows, so only add extras.
        # The single-instance endpoint may return flavor as a nested object or
        # only as an ID depending on API version, so handle both.
        flavor = raw.get("flavor")
        flavor_name = (flavor.get("name") if isinstance(flavor, dict) else None) or raw.get("flavorId")
        return [
            ("Flavor", flavor_name),
            ("Plan code", raw.get("planCode")),
            ("Monthly billing", raw.get("monthlyBilling")),
            ("SSH key", raw.get("sshKeyId")),
        ]
