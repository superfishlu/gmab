from unittest.mock import patch, MagicMock

from gmab.commands.spawn import spawn_box
from gmab.utils.config_loader import ConfigNotFoundError
from tests.support.config_env import ConfigDirTestCase
from tests.support.fakes import FakeProvider, make_instance


GENERAL = {
    "ssh_key_path": "~/.ssh/id_ed25519.pub",
    "default_lifetime_minutes": 60,
    "default_provider": "linode",
}
PROVIDERS = {
    "linode": {"api_key": "tok", "default_region": "nl-ams", "default_image": "linode/ubuntu22.04"},
}


class TestSpawnBox(ConfigDirTestCase):
    def setUp(self):
        super().setUp()
        self.write_configs(general=GENERAL, providers=PROVIDERS)
        self.fake = FakeProvider(PROVIDERS["linode"])
        self.fake.provider_name = "linode"

    def test_uses_default_provider_when_none(self):
        with patch("gmab.commands.spawn.get_provider", return_value=self.fake) as gp:
            spawn_box()
        self.assertEqual(gp.call_args[0][0], "linode")
        self.assertEqual(len(self.fake.spawn_calls), 1)

    def test_passes_explicit_args_through(self):
        with patch("gmab.commands.spawn.get_provider", return_value=self.fake):
            spawn_box(region="custom-region", image="custom-image", lifetime=10)
        call = self.fake.spawn_calls[0]
        self.assertEqual(call["region"], "custom-region")
        self.assertEqual(call["image"], "custom-image")
        self.assertEqual(call["lifetime_minutes"], 10)
        self.assertEqual(call["ssh_key_path"], GENERAL["ssh_key_path"])

    def test_falls_back_to_config_defaults(self):
        with patch("gmab.commands.spawn.get_provider", return_value=self.fake):
            spawn_box()
        call = self.fake.spawn_calls[0]
        self.assertEqual(call["region"], "nl-ams")
        self.assertEqual(call["image"], "linode/ubuntu22.04")
        self.assertEqual(call["lifetime_minutes"], 60)

    def test_unconfigured_provider_raises(self):
        with patch("gmab.commands.spawn.get_provider", return_value=self.fake):
            with self.assertRaises(Exception):
                spawn_box(provider_name="aws")  # not in providers.json

    def test_config_not_found_propagates(self):
        # Wipe configs so load_config raises.
        import os
        for name in ("config.json", "providers.json"):
            os.remove(os.path.join(self.config_dir, name))
        with self.assertRaises(ConfigNotFoundError):
            spawn_box()
