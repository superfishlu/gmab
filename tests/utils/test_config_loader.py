import os

from gmab.utils.config_loader import (
    load_config,
    save_config,
    get_default_providers_config,
    ConfigNotFoundError,
)
from gmab.utils.paths import get_config_file_path
from gmab.providers import get_available_providers
from tests.support.config_env import ConfigDirTestCase


class TestConfigLoader(ConfigDirTestCase):
    def test_load_missing_raises(self):
        with self.assertRaises(ConfigNotFoundError):
            load_config("config.json")

    def test_create_if_missing_writes_registry_defaults(self):
        providers = load_config("providers.json", create_if_missing=True)
        self.assertEqual(set(providers.keys()), set(get_available_providers()))
        self.assertTrue(os.path.exists(get_config_file_path("providers.json")))

    def test_save_load_roundtrip(self):
        cfg = {"ssh_key_path": "k", "default_lifetime_minutes": 42, "default_provider": "linode"}
        save_config(cfg, "config.json")
        self.assertEqual(load_config("config.json"), cfg)


class TestDefaultProvidersConfig(ConfigDirTestCase):
    def test_keys_match_registry(self):
        defaults = get_default_providers_config()
        self.assertEqual(set(defaults.keys()), set(get_available_providers()))

    def test_each_provider_gets_its_own_defaults(self):
        # Regression guard: the old code returned AWS defaults for Hetzner.
        defaults = get_default_providers_config()
        self.assertEqual(defaults["hetzner"]["default_region"], "nbg1")
        self.assertEqual(defaults["hetzner"]["default_type"], "cpx11")
        self.assertNotIn("access_key", defaults["hetzner"])
        self.assertIn("access_key", defaults["aws"])
        self.assertIn("default_root_pass", defaults["linode"])
