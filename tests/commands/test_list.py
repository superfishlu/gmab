import time
import unittest
from unittest.mock import patch

from gmab.commands.list import list_boxes, get_lifetime_left
from tests.support.config_env import ConfigDirTestCase
from tests.support.fakes import FakeProvider, make_instance


GENERAL = {"ssh_key_path": "~/.ssh/id_ed25519.pub", "default_lifetime_minutes": 60, "default_provider": "linode"}


class TestGetLifetimeLeft(unittest.TestCase):
    def test_half_consumed(self):
        inst = {"creation_time": int(time.time()) - 30 * 60, "lifetime_minutes": 60}
        self.assertAlmostEqual(get_lifetime_left(inst), 30, delta=1)

    def test_never_negative(self):
        inst = {"creation_time": int(time.time()) - 200 * 60, "lifetime_minutes": 60}
        self.assertEqual(get_lifetime_left(inst), 0)


def fake_for(name, instances):
    f = FakeProvider({})
    f.provider_name = name
    f.instances = instances
    return f


class TestListBoxes(ConfigDirTestCase):
    def test_aggregates_and_sorts_across_providers(self):
        self.write_configs(general=GENERAL, providers={"linode": {"api_key": "a"}, "hetzner": {"api_key": "b"}})
        now = int(time.time())
        fakes = {
            "linode": fake_for("linode", [make_instance(provider="linode", label="lin", creation_time=now - 50 * 60)]),
            "hetzner": fake_for("hetzner", [make_instance(provider="hetzner", label="het", creation_time=now - 10 * 60)]),
        }
        with patch("gmab.commands.list.get_provider", side_effect=lambda name, cfg: fakes[name]):
            instances = list_boxes()

        self.assertEqual({i["provider"] for i in instances}, {"linode", "hetzner"})
        # hetzner created more recently -> more lifetime_left -> sorted first (desc)
        self.assertEqual(instances[0]["label"], "het")
        self.assertIn("lifetime_left", instances[0])

    def test_skips_empty_provider_config(self):
        self.write_configs(general=GENERAL, providers={"linode": {"api_key": "a"}, "aws": {}})
        fakes = {"linode": fake_for("linode", [make_instance(provider="linode")])}
        with patch("gmab.commands.list.get_provider", side_effect=lambda name, cfg: fakes[name]) as gp:
            instances = list_boxes()
        # aws had empty config -> get_provider never called for it
        called_names = [c[0][0] for c in gp.call_args_list]
        self.assertNotIn("aws", called_names)
        self.assertEqual(len(instances), 1)

    def test_provider_error_warns_not_crash(self):
        self.write_configs(general=GENERAL, providers={"linode": {"api_key": "a"}, "hetzner": {"api_key": "b"}})
        good = fake_for("linode", [make_instance(provider="linode", label="ok")])
        bad = fake_for("hetzner", [])

        def boom():
            raise Exception("API down")
        bad.list_instances = boom

        fakes = {"linode": good, "hetzner": bad}
        with patch("gmab.commands.list.get_provider", side_effect=lambda name, cfg: fakes[name]):
            with patch("gmab.commands.list.click.echo") as echo:
                instances = list_boxes()

        self.assertEqual([i["label"] for i in instances], ["ok"])
        self.assertTrue(any("Failed to list instances" in str(c) for c in echo.call_args_list))

    def test_specific_unconfigured_provider_raises(self):
        self.write_configs(general=GENERAL, providers={"linode": {"api_key": "a"}})
        with self.assertRaises(Exception):
            list_boxes("aws")
