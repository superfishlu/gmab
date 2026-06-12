import unittest
from unittest.mock import patch

from click.testing import CliRunner

from gmab.cli import cli
from tests.support.config_env import ConfigDirTestCase


GENERAL = {"ssh_key_path": "~/.ssh/id_ed25519.pub", "default_lifetime_minutes": 60, "default_provider": "linode"}
PROVIDERS = {"linode": {"api_key": "tok"}}


class TestCliTerminateConfirmation(ConfigDirTestCase):
    def setUp(self):
        super().setUp()
        self.write_configs(general=GENERAL, providers=PROVIDERS)
        self.runner = CliRunner()

    def test_single_instance_prompts_and_cancels_on_no(self):
        with patch("gmab.cli.terminate_box") as tb:
            result = self.runner.invoke(cli, ["terminate", "gmab-foo"], input="n\n")
        self.assertIn("Are you sure", result.output)
        self.assertIn("cancelled", result.output.lower())
        tb.assert_not_called()

    def test_single_instance_proceeds_on_yes(self):
        with patch("gmab.cli.terminate_box") as tb:
            result = self.runner.invoke(cli, ["terminate", "gmab-foo"], input="y\n")
        self.assertIn("Are you sure", result.output)
        tb.assert_called_once()

    def test_yes_flag_skips_prompt(self):
        with patch("gmab.cli.terminate_box") as tb:
            result = self.runner.invoke(cli, ["terminate", "gmab-foo", "-y"])
        self.assertNotIn("Are you sure", result.output)
        tb.assert_called_once()


if __name__ == "__main__":
    unittest.main()
