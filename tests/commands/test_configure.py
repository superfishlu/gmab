import json
import os
import tempfile
import unittest
from unittest.mock import patch

from gmab.commands.configure import run_configure, validate_configs, print_configs
from gmab.utils.paths import get_config_file_path
from tests.support.config_env import ConfigDirTestCase


class TestRunConfigure(ConfigDirTestCase):
    def test_specific_provider_writes_both_files(self):
        # Scripted answers, in call order:
        # configure_general: ssh_key_path, default_lifetime, default_provider, output_format
        # configure_provider(linode): api_key, region, image, type, root_pass
        answers = [
            "/tmp/key.pub", 30, "linode", "text",
            "TOKEN123", "nl-ams", "linode/ubuntu22.04", "g6-nanode-1", "rootpw",
        ]
        with patch("click.prompt", side_effect=answers):
            run_configure("linode")

        with open(get_config_file_path("config.json")) as f:
            general = json.load(f)
        with open(get_config_file_path("providers.json")) as f:
            providers = json.load(f)

        self.assertEqual(general["default_provider"], "linode")
        self.assertEqual(general["default_lifetime_minutes"], 30)
        self.assertEqual(general["output_format"], "text")
        self.assertEqual(providers["linode"]["api_key"], "TOKEN123")
        self.assertEqual(providers["linode"]["default_region"], "nl-ams")
        self.assertEqual(providers["linode"]["default_root_pass"], "rootpw")


class TestValidateConfigs(ConfigDirTestCase):
    def test_warns_when_required_credential_missing(self):
        # Real ssh key file so the ssh warning doesn't fire and muddy the assert.
        fd, key_path = tempfile.mkstemp()
        os.close(fd)
        self.addCleanup(os.remove, key_path)
        self.write_configs(
            general={"ssh_key_path": key_path, "default_lifetime_minutes": 60, "default_provider": "linode"},
            providers={"linode": {"api_key": ""}},  # required api_key missing
        )
        with patch("gmab.commands.configure.click.echo") as echo:
            validate_configs()
        output = " ".join(str(c) for c in echo.call_args_list)
        self.assertIn("not fully configured", output)
        self.assertIn("api_key", output)


class TestPrintConfigs(ConfigDirTestCase):
    def test_masks_secret_fields_only(self):
        self.write_configs(
            general={"ssh_key_path": "x", "default_lifetime_minutes": 60, "default_provider": "linode"},
            providers={"linode": {"api_key": "SUPERSECRET", "default_region": "nl-ams", "default_root_pass": "PWSECRET"}},
        )
        with patch("gmab.commands.configure.click.echo") as echo:
            print_configs()
        output = "\n".join(str(c) for c in echo.call_args_list)
        # secrets masked
        self.assertNotIn("SUPERSECRET", output)
        self.assertNotIn("PWSECRET", output)
        self.assertIn("********", output)
        # non-secret value still visible
        self.assertIn("nl-ams", output)


if __name__ == "__main__":
    unittest.main()
