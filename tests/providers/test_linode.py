import time
import unittest
from unittest.mock import patch

from gmab.providers.linode import LinodeProvider
from tests.support.contracts import assert_instance_shape
from tests.support.http import mock_response


def make_provider():
    p = LinodeProvider({
        "api_key": "tok",
        "default_region": "nl-ams",
        "default_image": "linode/ubuntu22.04",
        "default_type": "g6-nanode-1",
    })
    p.provider_name = "linode"
    return p


class TestLinodeSpawn(unittest.TestCase):
    @patch.object(LinodeProvider, "_read_ssh_key", return_value="ssh-ed25519 AAAA")
    @patch("gmab.providers.linode.requests.post")
    def test_spawn_builds_payload_and_returns_contract(self, mock_post, _ssh):
        mock_post.return_value = mock_response(
            {"id": 123, "ipv4": ["1.2.3.4"], "status": "provisioning"}, status=200
        )
        provider = make_provider()

        result = provider.spawn_instance(
            image="linode/ubuntu22.04", region="nl-ams", lifetime_minutes=30
        )

        # Correct endpoint + payload shape
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.linode.com/v4/linode/instances")
        payload = kwargs["json"]
        self.assertEqual(payload["type"], "g6-nanode-1")
        self.assertEqual(payload["region"], "nl-ams")
        self.assertEqual(payload["authorized_keys"], ["ssh-ed25519 AAAA"])
        self.assertTrue(payload["label"].startswith("gmab-"))
        self.assertIn("gmab", payload["tags"])
        self.assertTrue(any(t.startswith("gmab-creation-time-") for t in payload["tags"]))
        self.assertIn("gmab-lifetime-30", payload["tags"])

        # Contract-shaped return
        assert_instance_shape(self, result)
        self.assertEqual(result["instance_id"], "123")
        self.assertEqual(result["ip"], "1.2.3.4")
        self.assertEqual(result["lifetime_minutes"], 30)

    def test_spawn_without_api_key_raises(self):
        provider = LinodeProvider({})
        provider.provider_name = "linode"
        with self.assertRaises(ValueError):
            provider.spawn_instance()

    @patch.object(LinodeProvider, "_read_ssh_key", return_value="ssh-ed25519 AAAA")
    @patch("gmab.providers.linode.requests.post")
    def test_spawn_api_error_raises(self, mock_post, _ssh):
        mock_post.return_value = mock_response(status=400, text="bad request")
        provider = make_provider()
        with self.assertRaises(Exception):
            provider.spawn_instance()


class TestLinodeList(unittest.TestCase):
    def _api_payload(self):
        now = int(time.time())
        old = now - 2 * 60 * 60
        return {
            "data": [
                {  # live gmab instance
                    "id": 1, "label": "gmab-live", "ipv4": ["1.1.1.1"],
                    "status": "running", "region": "nl-ams", "image": "linode/ubuntu22.04",
                    "tags": ["gmab", f"gmab-creation-time-{now}", "gmab-lifetime-60"],
                },
                {  # expired gmab instance
                    "id": 2, "label": "gmab-old", "ipv4": ["2.2.2.2"],
                    "status": "running", "region": "nl-ams", "image": "linode/ubuntu22.04",
                    "tags": ["gmab", f"gmab-creation-time-{old}", "gmab-lifetime-60"],
                },
                {  # non-gmab instance must be ignored
                    "id": 3, "label": "other", "ipv4": ["3.3.3.3"],
                    "status": "running", "region": "nl-ams", "image": "x", "tags": [],
                },
            ]
        }

    @patch("gmab.providers.linode.requests.get")
    def test_list_filters_and_computes_expiry(self, mock_get):
        mock_get.return_value = mock_response(self._api_payload(), status=200)
        provider = make_provider()

        instances = provider.list_instances()

        self.assertEqual({i["label"] for i in instances}, {"gmab-live", "gmab-old"})
        by_label = {i["label"]: i for i in instances}
        self.assertFalse(by_label["gmab-live"]["is_expired"])
        self.assertTrue(by_label["gmab-old"]["is_expired"])
        self.assertIn("(expired)", by_label["gmab-old"]["status"])
        for inst in instances:
            assert_instance_shape(self, inst)

    @patch("gmab.providers.linode.requests.get")
    def test_list_expired_filters(self, mock_get):
        mock_get.return_value = mock_response(self._api_payload(), status=200)
        provider = make_provider()
        expired = provider.list_expired_instances()
        self.assertEqual([i["label"] for i in expired], ["gmab-old"])


class TestLinodeTerminate(unittest.TestCase):
    @patch("gmab.providers.linode.requests.delete")
    def test_terminate_by_numeric_id(self, mock_delete):
        mock_delete.return_value = mock_response(status=200)
        provider = make_provider()

        provider.terminate_instance("123")

        url = mock_delete.call_args[0][0]
        self.assertEqual(url, "https://api.linode.com/v4/linode/instances/123")

    @patch("gmab.providers.linode.requests.delete")
    def test_terminate_by_label_resolves_then_deletes(self, mock_delete):
        mock_delete.return_value = mock_response(status=204)
        provider = make_provider()
        with patch.object(provider, "find_instance_id_by_label", return_value="999") as finder:
            provider.terminate_instance("gmab-foo")
            finder.assert_called_once_with("gmab-foo")
        url = mock_delete.call_args[0][0]
        self.assertEqual(url, "https://api.linode.com/v4/linode/instances/999")

    @patch("gmab.providers.linode.requests.delete")
    def test_terminate_unknown_label_raises(self, mock_delete):
        provider = make_provider()
        with patch.object(provider, "find_instance_id_by_label", return_value=None):
            with self.assertRaises(Exception):
                provider.terminate_instance("gmab-missing")


if __name__ == "__main__":
    unittest.main()
