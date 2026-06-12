import json
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
        with patch("gmab.cli.list_boxes", return_value=[]), \
             patch("gmab.cli.terminate_box") as tb:
            result = self.runner.invoke(cli, ["terminate", "gmab-foo"], input="n\n")
        self.assertIn("will be terminated", result.output)
        self.assertIn("proceed", result.output.lower())
        self.assertIn("cancelled", result.output.lower())
        tb.assert_not_called()

    def test_single_instance_proceeds_on_yes(self):
        with patch("gmab.cli.list_boxes", return_value=[]), \
             patch("gmab.cli.terminate_box") as tb:
            result = self.runner.invoke(cli, ["terminate", "gmab-foo"], input="y\n")
        self.assertIn("will be terminated", result.output)
        tb.assert_called_once()

    def test_yes_flag_skips_prompt(self):
        with patch("gmab.cli.terminate_box") as tb:
            result = self.runner.invoke(cli, ["terminate", "gmab-foo", "-y"])
        self.assertNotIn("Are you sure", result.output)
        tb.assert_called_once()


class TestCliTerminateBatchPreview(ConfigDirTestCase):
    def setUp(self):
        super().setUp()
        self.write_configs(general=GENERAL, providers=PROVIDERS)
        self.runner = CliRunner()
        self.sample = [
            {"provider": "linode", "instance_id": "1", "label": "gmab-a", "ip": "1.1.1.1",
             "status": "running", "region": "nl-ams", "image": "ubuntu", "is_expired": False,
             "lifetime_left": 30},
        ]

    def test_terminate_all_renders_table_preview(self):
        with patch("gmab.cli.list_boxes", return_value=self.sample), \
             patch("gmab.cli.render_instances_table") as render, \
             patch("gmab.cli.terminate_box"):
            result = self.runner.invoke(cli, ["terminate", "all"], input="n\n")
        self.assertIn("will be terminated", result.output)
        render.assert_called_once_with(self.sample)

    def test_terminate_expired_renders_table_preview(self):
        expired = [dict(self.sample[0], is_expired=True, lifetime_left=0)]
        with patch("gmab.cli.list_boxes", return_value=expired), \
             patch("gmab.cli.render_instances_table") as render, \
             patch("gmab.cli.terminate_box"):
            result = self.runner.invoke(cli, ["terminate", "expired"], input="n\n")
        self.assertIn("expired instances will be terminated", result.output)
        render.assert_called_once_with(expired)


class TestCliTerminateJson(ConfigDirTestCase):
    def setUp(self):
        super().setUp()
        self.write_configs(general=GENERAL, providers=PROVIDERS)
        self.runner = CliRunner()
        self.sample = [
            {"provider": "linode", "instance_id": "1", "label": "gmab-a", "ip": "1.1.1.1",
             "status": "running", "region": "nl-ams", "image": "ubuntu", "is_expired": False,
             "lifetime_left": 30},
        ]

    def test_terminate_all_json_reports_results(self):
        with patch("gmab.cli.list_boxes", return_value=self.sample), \
             patch("gmab.cli.render_instances_table") as render, \
             patch("gmab.cli.terminate_box"):
            result = self.runner.invoke(cli, ["terminate", "all", "-y", "-o", "json"])
        data = json.loads(result.output)
        self.assertEqual(data["terminated_count"], 1)
        self.assertEqual(data["failed_count"], 0)
        self.assertEqual(data["terminated"][0]["instance_id"], "1")
        render.assert_not_called()  # no table in JSON mode

    def test_terminate_json_interactive_plan_goes_to_stderr(self):
        # Without -y, the to-be-terminated plan + prompt go to stderr; stdout
        # stays a single JSON result document.
        runner = CliRunner(mix_stderr=False)
        with patch("gmab.cli.list_boxes", return_value=self.sample), \
             patch("gmab.cli.terminate_box"):
            result = runner.invoke(cli, ["terminate", "all", "-o", "json"], input="y\n")
        # CliRunner echoes the typed input onto stdout (a real TTY echoes to the
        # terminal, not the stdout pipe); the result is the object from the first brace.
        stdout = result.stdout
        data = json.loads(stdout[stdout.index("{"):])
        self.assertEqual(data["terminated_count"], 1)
        self.assertIn('"instance_id": "1"', result.stderr)  # plan on stderr
        self.assertIn("proceed", result.stderr.lower())     # prompt on stderr
        self.assertNotIn("proceed", stdout.lower())

    def test_terminate_specific_json_reports_failure(self):
        with patch("gmab.cli.list_boxes", return_value=[]), \
             patch("gmab.cli.terminate_box", side_effect=Exception("nope")):
            result = self.runner.invoke(cli, ["terminate", "gmab-x", "-y", "-o", "json"])
        data = json.loads(result.output)
        self.assertEqual(data["terminated_count"], 0)
        self.assertEqual(data["failed_count"], 1)
        self.assertEqual(data["failed"][0]["error"], "nope")

    def test_terminate_all_json_stdout_is_pure_json(self):
        # Real terminate_box (only the provider layer is mocked) must stay quiet in
        # JSON mode, so its per-instance echo doesn't corrupt the stdout JSON.
        from unittest.mock import MagicMock
        fake = MagicMock()
        runner = CliRunner(mix_stderr=False)
        with patch("gmab.cli.list_boxes", return_value=self.sample), \
             patch("gmab.commands.terminate.load_config", return_value={"linode": {"api_key": "t"}}), \
             patch("gmab.commands.terminate.get_provider", return_value=fake):
            result = runner.invoke(cli, ["terminate", "all", "-y", "-o", "json"])
        data = json.loads(result.stdout)  # would raise if "Terminated instance..." leaked
        self.assertEqual(data["terminated_count"], 1)
        fake.terminate_instance.assert_called_once()


if __name__ == "__main__":
    unittest.main()
