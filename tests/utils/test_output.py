import unittest

from gmab.utils.output import resolve_output_format, instance_to_json
from tests.support.config_env import ConfigDirTestCase


class TestResolveOutputFormat(ConfigDirTestCase):
    def test_flag_overrides_config(self):
        self.write_configs(general={"output_format": "json"}, providers={})
        self.assertEqual(resolve_output_format("text"), "text")

    def test_falls_back_to_config(self):
        self.write_configs(general={"output_format": "json"}, providers={})
        self.assertEqual(resolve_output_format(None), "json")

    def test_defaults_to_text_when_unset(self):
        self.write_configs(general={"default_provider": "linode"}, providers={})
        self.assertEqual(resolve_output_format(None), "text")

    def test_defaults_to_text_when_no_config(self):
        # No config files written at all.
        self.assertEqual(resolve_output_format(None), "text")


class TestInstanceToJson(unittest.TestCase):
    def test_shape_and_lifetime_rounding(self):
        out = instance_to_json({
            "provider": "ovh", "instance_id": "i", "label": "l", "ip": "1.2.3.4",
            "status": "running", "region": "GRA9", "image": "img",
            "creation_time": 123, "lifetime_minutes": 60, "is_expired": False,
            "lifetime_left": 58.9,
        })
        self.assertEqual(out["lifetime_left_minutes"], 58)  # int, not float
        self.assertIs(out["is_expired"], False)
        self.assertEqual(set(out), {
            "provider", "instance_id", "label", "ip", "status", "region", "image",
            "creation_time", "lifetime_minutes", "lifetime_left_minutes", "is_expired",
        })

    def test_missing_lifetime_left_is_none(self):
        self.assertIsNone(instance_to_json({})["lifetime_left_minutes"])


if __name__ == "__main__":
    unittest.main()
