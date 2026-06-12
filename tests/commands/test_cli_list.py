import json
import os
import unittest
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from gmab.cli import cli, select_list_columns, _flatten
from gmab.commands.list import get_detailed_instances


class TestSelectListColumns(unittest.TestCase):
    def test_wide_keeps_all_columns(self):
        cols = select_list_columns(130)
        self.assertEqual(len(cols), 8)

    def test_drops_image_first(self):
        cols = select_list_columns(110)
        self.assertNotIn("image", cols)
        self.assertIn("instance_id", cols)
        self.assertIn("region", cols)

    def test_drops_instance_id_before_region(self):
        cols = select_list_columns(90)
        self.assertNotIn("image", cols)
        self.assertNotIn("instance_id", cols)
        self.assertIn("region", cols)

    def test_narrow_keeps_essentials_only(self):
        cols = select_list_columns(70)
        self.assertEqual(set(cols), {"provider", "label", "ip", "status", "time_left"})

    def test_essentials_always_present(self):
        # These survive at any width; Label is the always-present terminate handle.
        essential = {"provider", "label", "ip", "status", "time_left"}
        for width in (40, 70, 90, 200):
            self.assertTrue(essential.issubset(select_list_columns(width)))


class TestListRendersTable(unittest.TestCase):
    SAMPLE = [
        {
            "provider": "ovh",
            "instance_id": "dfe10f41-4c29-4af5-8cec-175881f023ab",
            "label": "gmab-1781265913-60-33xnxgqs",
            "ip": "79.137.120.108",
            "status": "running",
            "region": "GRA9",
            "image": "Ubuntu 22.04",
            "lifetime_left": 58,
        }
    ]

    def test_list_outputs_table_with_label_and_provider(self):
        # Pin a wide console so nothing wraps and the full label stays contiguous.
        with patch.dict(os.environ, {"COLUMNS": "200"}), \
             patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.list_boxes", return_value=self.SAMPLE):
            result = CliRunner().invoke(cli, ["list"])
        self.assertEqual(result.exit_code, 0)
        # The full label (terminate handle) and provider appear in the rendered table.
        self.assertIn("gmab-1781265913-60-33xnxgqs", result.output)
        self.assertIn("ovh", result.output)
        self.assertIn("Instance ID", result.output)

    def test_empty_list_message(self):
        with patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.list_boxes", return_value=[]):
            result = CliRunner().invoke(cli, ["list"])
        self.assertIn("No active instances found.", result.output)


class TestFlatten(unittest.TestCase):
    def test_flatten_nested_dict_and_list(self):
        out = _flatten({"a": {"b": 1}, "c": [10, 20], "d": [], "e": {}})
        self.assertEqual(out["a.b"], 1)
        self.assertEqual(out["c[0]"], 10)
        self.assertEqual(out["c[1]"], 20)
        self.assertEqual(out["d"], "[]")
        self.assertEqual(out["e"], "{}")


class TestListDetailGrammar(unittest.TestCase):
    SAMPLE = (
        {"provider": "ovh", "instance_id": "i1", "label": "gmab-a",
         "status": "running", "ip": "1.1.1.1", "region": "GRA9", "image": "Ubuntu 22.04",
         "creation_time": 1781265913, "lifetime_minutes": 60, "lifetime_left": 30},
        {"raw": True},
        [("Flavor", "d2-2")],
    )

    def _run(self, argv):
        with patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.get_detailed_instances", return_value=[self.SAMPLE]) as gdi, \
             patch("gmab.cli.render_instance_detail") as rid:
            result = CliRunner().invoke(cli, argv)
        return result, gdi, rid

    def test_detail_all(self):
        result, gdi, rid = self._run(["list", "detail"])
        self.assertEqual(result.exit_code, 0)
        gdi.assert_called_once_with(None, None)
        self.assertFalse(rid.call_args.args[3])  # verbose=False

    def test_detail_verbose(self):
        result, gdi, rid = self._run(["list", "detail", "verbose"])
        gdi.assert_called_once_with(None, None)
        self.assertTrue(rid.call_args.args[3])  # verbose=True

    def test_detail_target(self):
        result, gdi, rid = self._run(["list", "detail", "gmab-xyz"])
        gdi.assert_called_once_with(None, "gmab-xyz")

    def test_bare_target_implies_detail(self):
        result, gdi, rid = self._run(["list", "gmab-xyz"])
        gdi.assert_called_once_with(None, "gmab-xyz")

    def test_plain_list_does_not_use_detail(self):
        with patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.list_boxes", return_value=[]), \
             patch("gmab.cli.get_detailed_instances") as gdi:
            CliRunner().invoke(cli, ["list"])
        gdi.assert_not_called()


class TestListJsonOutput(unittest.TestCase):
    SAMPLE = [{
        "provider": "ovh", "instance_id": "dfe10f41", "label": "gmab-a", "ip": "1.2.3.4",
        "status": "running", "region": "GRA9", "image": "Ubuntu 22.04",
        "creation_time": 1781265913, "lifetime_minutes": 60, "is_expired": False,
        "lifetime_left": 58.7,
    }]

    def _ctx(self):
        return [
            patch("gmab.cli.check_config_exists", return_value=True),
            patch("gmab.cli.get_configured_providers", return_value=["ovh"]),
        ]

    def test_list_json_is_valid_array(self):
        with patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.list_boxes", return_value=self.SAMPLE):
            result = CliRunner().invoke(cli, ["list", "-o", "json"])
        data = json.loads(result.output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["instance_id"], "dfe10f41")
        self.assertEqual(data[0]["lifetime_left_minutes"], 58)
        self.assertNotIn("lifetime_left", data[0])  # only the cleaned key

    def test_list_json_empty_is_empty_array(self):
        with patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.list_boxes", return_value=[]):
            result = CliRunner().invoke(cli, ["list", "-o", "json"])
        self.assertEqual(json.loads(result.output), [])

    def test_detail_json_includes_extras(self):
        details = [(self.SAMPLE[0], {"raw": 1}, [("Flavor", "d2-2")])]
        with patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.get_detailed_instances", return_value=details):
            result = CliRunner().invoke(cli, ["list", "detail", "-o", "json"])
        data = json.loads(result.output)
        self.assertEqual(data[0]["extras"], {"Flavor": "d2-2"})
        self.assertNotIn("details", data[0])

    def test_detail_verbose_json_includes_raw_details(self):
        details = [(self.SAMPLE[0], {"raw": 1, "vpc": "v-1"}, [("Flavor", "d2-2")])]
        with patch("gmab.cli.check_config_exists", return_value=True), \
             patch("gmab.cli.get_configured_providers", return_value=["ovh"]), \
             patch("gmab.cli.get_detailed_instances", return_value=details):
            result = CliRunner().invoke(cli, ["list", "detail", "verbose", "-o", "json"])
        data = json.loads(result.output)
        self.assertEqual(data[0]["details"], {"raw": 1, "vpc": "v-1"})
        self.assertNotIn("extras", data[0])


class TestGetDetailedInstances(unittest.TestCase):
    INSTANCES = [
        {"provider": "ovh", "instance_id": "i1", "label": "gmab-a"},
        {"provider": "ovh", "instance_id": "i2", "label": "gmab-b"},
    ]

    def _fake_provider(self):
        fake = MagicMock()
        fake.get_instance_details.return_value = {"raw": True}
        fake.detail_extras.return_value = [("Flavor", "d2-2")]
        return fake

    def test_target_filters_and_calls_provider(self):
        fake = self._fake_provider()
        with patch("gmab.commands.list.list_boxes", return_value=self.INSTANCES), \
             patch("gmab.commands.list.load_config", return_value={"ovh": {"x": 1}}), \
             patch("gmab.commands.list.get_provider", return_value=fake):
            res = get_detailed_instances(target="gmab-b")
        self.assertEqual(len(res), 1)
        inst, raw, extras = res[0]
        self.assertEqual(inst["instance_id"], "i2")
        self.assertEqual(raw, {"raw": True})
        self.assertEqual(extras, [("Flavor", "d2-2")])
        fake.get_instance_details.assert_called_once_with("i2")

    def test_unknown_target_raises(self):
        with patch("gmab.commands.list.list_boxes", return_value=self.INSTANCES), \
             patch("gmab.commands.list.load_config", return_value={"ovh": {"x": 1}}):
            with self.assertRaises(ValueError):
                get_detailed_instances(target="does-not-exist")

    def test_details_failure_is_captured_not_raised(self):
        fake = self._fake_provider()
        fake.get_instance_details.side_effect = Exception("boom")
        with patch("gmab.commands.list.list_boxes", return_value=self.INSTANCES[:1]), \
             patch("gmab.commands.list.load_config", return_value={"ovh": {"x": 1}}), \
             patch("gmab.commands.list.get_provider", return_value=fake):
            res = get_detailed_instances()
        self.assertEqual(res[0][1], {"error": "boom"})


if __name__ == "__main__":
    unittest.main()
