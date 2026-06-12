import unittest
from unittest.mock import patch

from gmab.commands.terminate import get_instance_provider, terminate_box
from tests.support.config_env import ConfigDirTestCase
from tests.support.fakes import FakeProvider, make_instance


GENERAL = {"ssh_key_path": "~/.ssh/id_ed25519.pub", "default_lifetime_minutes": 60, "default_provider": "linode"}


def fake_for(name, instances=None):
    f = FakeProvider({})
    f.provider_name = name
    f.instances = instances or []
    return f


class TestGetInstanceProvider(unittest.TestCase):
    def test_aws_fastpath_skips_scanning(self):
        # If the fast path works, we never call list_instances (which here raises).
        scanning = fake_for("aws")
        def boom():
            raise AssertionError("should not scan")
        scanning.list_instances = boom
        with patch("gmab.commands.terminate.get_provider", return_value=scanning):
            name, provider = get_instance_provider("i-123", {"aws": {"access_key": "x"}})
        self.assertEqual(name, "aws")

    def test_label_scan_finds_provider(self):
        fakes = {
            "linode": fake_for("linode", [make_instance(provider="linode", label="gmab-foo")]),
            "hetzner": fake_for("hetzner", []),
        }
        with patch("gmab.commands.terminate.get_provider", side_effect=lambda n, c: fakes[n]):
            name, provider = get_instance_provider("gmab-foo", {"linode": {"api_key": "a"}, "hetzner": {"api_key": "b"}})
        self.assertEqual(name, "linode")

    def test_not_found_returns_none(self):
        fakes = {"linode": fake_for("linode", [make_instance(provider="linode", label="gmab-other")])}
        with patch("gmab.commands.terminate.get_provider", side_effect=lambda n, c: fakes[n]):
            name, provider = get_instance_provider("gmab-missing", {"linode": {"api_key": "a"}})
        self.assertIsNone(name)
        self.assertIsNone(provider)

    def test_skips_empty_cfg_during_scan(self):
        fakes = {"linode": fake_for("linode", [make_instance(provider="linode", label="gmab-foo")])}
        with patch("gmab.commands.terminate.get_provider", side_effect=lambda n, c: fakes[n]) as gp:
            get_instance_provider("gmab-foo", {"linode": {"api_key": "a"}, "hetzner": {}})
        self.assertNotIn("hetzner", [c[0][0] for c in gp.call_args_list])


class TestTerminateBox(ConfigDirTestCase):
    def test_explicit_provider_terminates(self):
        self.write_configs(general=GENERAL, providers={"linode": {"api_key": "a"}})
        fake = fake_for("linode")
        with patch("gmab.commands.terminate.get_provider", return_value=fake):
            terminate_box("123", "linode")
        self.assertEqual(fake.terminated, ["123"])

    def test_autodetect_provider_terminates(self):
        self.write_configs(general=GENERAL, providers={"linode": {"api_key": "a"}})
        fake = fake_for("linode", [make_instance(provider="linode", label="gmab-foo", instance_id="50")])
        with patch("gmab.commands.terminate.get_provider", return_value=fake):
            terminate_box("gmab-foo")
        self.assertEqual(fake.terminated, ["gmab-foo"])

    def test_unconfigured_explicit_provider_raises(self):
        self.write_configs(general=GENERAL, providers={"linode": {"api_key": "a"}})
        with self.assertRaises(Exception):
            terminate_box("i-1", "aws")


if __name__ == "__main__":
    unittest.main()
