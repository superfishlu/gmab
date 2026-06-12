import time
import unittest
from unittest.mock import patch

from gmab.providers.hetzner import HetznerProvider
from tests.support.contracts import assert_instance_shape
from tests.support.http import mock_response


def make_provider():
    p = HetznerProvider({
        "api_key": "tok",
        "default_region": "nbg1",
        "default_image": "ubuntu-22.04",
        "default_type": "cpx11",
    })
    p.provider_name = "hetzner"
    return p


class TestHetznerInit(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            HetznerProvider({})


class TestHetznerSpawn(unittest.TestCase):
    @patch.object(HetznerProvider, "_get_or_create_ssh_key", return_value=42)
    @patch.object(HetznerProvider, "_read_ssh_key", return_value="ssh-ed25519 AAAA")
    @patch("gmab.providers.hetzner.requests.post")
    def test_spawn_builds_payload_and_returns_contract(self, mock_post, _ssh, _key):
        mock_post.return_value = mock_response(
            {"server": {"id": 555, "status": "running",
                        "public_net": {"ipv4": {"ip": "5.5.5.5"}}}},
            status=201,
        )
        provider = make_provider()

        result = provider.spawn_instance(image="ubuntu-22.04", region="nbg1", lifetime_minutes=45)

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.hetzner.cloud/v1/servers")
        payload = kwargs["json"]
        self.assertEqual(payload["server_type"], "cpx11")
        self.assertEqual(payload["location"], "nbg1")
        self.assertEqual(payload["ssh_keys"], [42])
        self.assertTrue(payload["name"].startswith("gmab-"))
        self.assertEqual(payload["labels"]["gmab"], "true")
        self.assertEqual(payload["labels"]["gmab-lifetime"], "45")
        self.assertIn("gmab-creation-time", payload["labels"])

        assert_instance_shape(self, result)
        self.assertEqual(result["instance_id"], "555")
        self.assertEqual(result["ip"], "5.5.5.5")
        self.assertEqual(result["lifetime_minutes"], 45)


class TestHetznerSshKey(unittest.TestCase):
    @patch("gmab.providers.hetzner.requests.post")
    @patch("gmab.providers.hetzner.requests.get")
    def test_reuses_existing_key(self, mock_get, mock_post):
        mock_get.return_value = mock_response(
            {"ssh_keys": [{"id": 7, "public_key": "ssh-ed25519 AAAA"}]}, status=200
        )
        provider = make_provider()
        key_id = provider._get_or_create_ssh_key("ssh-ed25519 AAAA")
        self.assertEqual(key_id, 7)
        mock_post.assert_not_called()

    @patch("gmab.providers.hetzner.requests.post")
    @patch("gmab.providers.hetzner.requests.get")
    def test_creates_key_when_missing(self, mock_get, mock_post):
        mock_get.return_value = mock_response({"ssh_keys": []}, status=200)
        mock_post.return_value = mock_response({"ssh_key": {"id": 9}}, status=201)
        provider = make_provider()
        key_id = provider._get_or_create_ssh_key("ssh-ed25519 NEW")
        self.assertEqual(key_id, 9)
        mock_post.assert_called_once()


class TestHetznerList(unittest.TestCase):
    def _api_payload(self):
        now = int(time.time())
        old = now - 2 * 60 * 60
        def server(sid, name, ip, created, life):
            return {
                "id": sid, "name": name, "status": "running",
                "public_net": {"ipv4": {"ip": ip}},
                "datacenter": {"location": {"name": "nbg1"}},
                "image": {"name": "ubuntu-22.04"},
                "labels": {"gmab": "true",
                           "gmab-creation-time": str(created),
                           "gmab-lifetime": str(life)},
            }
        return {"servers": [server(1, "gmab-live", "1.1.1.1", now, 60),
                            server(2, "gmab-old", "2.2.2.2", old, 60)]}

    @patch("gmab.providers.hetzner.requests.get")
    def test_list_parses_and_computes_expiry(self, mock_get):
        mock_get.return_value = mock_response(self._api_payload(), status=200)
        provider = make_provider()

        instances = provider.list_instances()
        by_label = {i["label"]: i for i in instances}
        self.assertEqual(set(by_label), {"gmab-live", "gmab-old"})
        self.assertFalse(by_label["gmab-live"]["is_expired"])
        self.assertTrue(by_label["gmab-old"]["is_expired"])
        self.assertIn("(expired)", by_label["gmab-old"]["status"])
        self.assertEqual(by_label["gmab-live"]["region"], "nbg1")
        for inst in instances:
            assert_instance_shape(self, inst)


class TestHetznerTerminate(unittest.TestCase):
    @patch("gmab.providers.hetzner.requests.delete")
    def test_terminate_by_numeric_id(self, mock_delete):
        mock_delete.return_value = mock_response(status=200)
        provider = make_provider()
        provider.terminate_instance("555")
        url = mock_delete.call_args[0][0]
        self.assertEqual(url, "https://api.hetzner.cloud/v1/servers/555")

    @patch("gmab.providers.hetzner.requests.delete")
    def test_terminate_by_label_resolves_then_deletes(self, mock_delete):
        mock_delete.return_value = mock_response(status=200)
        provider = make_provider()
        with patch.object(provider, "find_instance_id_by_label", return_value="888") as finder:
            provider.terminate_instance("gmab-foo")
            finder.assert_called_once_with("gmab-foo")
        self.assertEqual(mock_delete.call_args[0][0], "https://api.hetzner.cloud/v1/servers/888")


if __name__ == "__main__":
    unittest.main()
