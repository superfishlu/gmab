import time
import unittest
from unittest.mock import patch, Mock

from gmab.providers.ovh import OVHProvider
from tests.support.contracts import assert_instance_shape


def make_provider():
    p = OVHProvider({
        "application_key": "ak",
        "application_secret": "as",
        "consumer_key": "ck",
        "service_name": "proj-123",
        "endpoint": "ovh-eu",
        "default_region": "GRA9",
        "default_flavor": "d2-2",
        "default_image": "Ubuntu 22.04",
    })
    p.provider_name = "ovh"
    # Replace the real ovh.Client with a mock; no network, ever.
    p.client = Mock()
    return p


class TestOVHInit(unittest.TestCase):
    def test_requires_credentials_and_service_name(self):
        with self.assertRaises(ValueError):
            OVHProvider({})

    def test_requires_service_name(self):
        with self.assertRaises(ValueError):
            OVHProvider({
                "application_key": "ak",
                "application_secret": "as",
                "consumer_key": "ck",
            })


class TestOVHSpawn(unittest.TestCase):
    def _wire(self, provider, sshkeys):
        def fake_get(target, **kwargs):
            if target.endswith("/flavor"):
                return [{"id": "flv-1", "name": "d2-2"}, {"id": "flv-x", "name": "b3-8"}]
            if target.endswith("/image"):
                return [{"id": "img-1", "name": "Ubuntu 22.04"}]
            if target.endswith("/sshkey"):
                return sshkeys
            raise AssertionError(f"unexpected GET {target}")

        def fake_post(target, **kwargs):
            if target.endswith("/sshkey"):
                return {"id": "key-new"}
            if target.endswith("/instance"):
                return {"id": "inst-123", "status": "BUILD", "ipAddresses": []}
            raise AssertionError(f"unexpected POST {target}")

        provider.client.get.side_effect = fake_get
        provider.client.post.side_effect = fake_post

    @patch.object(OVHProvider, "_read_ssh_key", return_value="ssh-ed25519 AAAA")
    def test_spawn_builds_payload_and_returns_contract(self, _ssh):
        provider = make_provider()
        self._wire(provider, sshkeys=[{"id": "key-1", "publicKey": "ssh-ed25519 AAAA"}])

        result = provider.spawn_instance(region="GRA9", lifetime_minutes=45)

        # Find the instance-create POST call.
        create = next(
            c for c in provider.client.post.call_args_list if c.args[0].endswith("/instance")
        )
        kwargs = create.kwargs
        self.assertEqual(create.args[0], "/cloud/project/proj-123/instance")
        self.assertEqual(kwargs["flavorId"], "flv-1")
        self.assertEqual(kwargs["imageId"], "img-1")
        self.assertEqual(kwargs["sshKeyId"], "key-1")
        self.assertEqual(kwargs["region"], "GRA9")
        self.assertFalse(kwargs["monthlyBilling"])
        self.assertTrue(kwargs["name"].startswith("gmab-"))
        self.assertIn("-45-", kwargs["name"])  # lifetime encoded in the name

        assert_instance_shape(self, result)
        self.assertEqual(result["instance_id"], "inst-123")
        self.assertEqual(result["lifetime_minutes"], 45)
        self.assertEqual(result["region"], "GRA9")
        self.assertEqual(result["image"], "Ubuntu 22.04")

    @patch.object(OVHProvider, "_read_ssh_key", return_value="ssh-ed25519 AAAA")
    def test_spawn_unknown_flavor_raises(self, _ssh):
        provider = make_provider()
        provider.client.get.side_effect = lambda target, **kw: (
            [{"id": "flv-x", "name": "b3-8"}] if target.endswith("/flavor") else []
        )
        with self.assertRaises(Exception) as ctx:
            provider.spawn_instance(region="GRA9", lifetime_minutes=10)
        self.assertIn("Flavor 'd2-2' not found", str(ctx.exception))


class TestOVHSshKey(unittest.TestCase):
    def test_reuses_existing_key(self):
        provider = make_provider()
        provider.client.get.return_value = [
            {"id": "key-1", "publicKey": "ssh-ed25519 AAAA"}
        ]
        key_id = provider._get_or_create_ssh_key("GRA9", "ssh-ed25519 AAAA")
        self.assertEqual(key_id, "key-1")
        provider.client.post.assert_not_called()

    def test_creates_key_when_missing(self):
        provider = make_provider()
        provider.client.get.return_value = []
        provider.client.post.return_value = {"id": "key-new"}
        key_id = provider._get_or_create_ssh_key("GRA9", "ssh-ed25519 NEW")
        self.assertEqual(key_id, "key-new")
        provider.client.post.assert_called_once()


class TestOVHList(unittest.TestCase):
    def _instances(self):
        now = int(time.time())
        old = now - 2 * 60 * 60
        return [
            {  # live gmab instance (lifetime 30, distinct so parsing has teeth)
                "id": "inst-live", "name": f"gmab-{now}-30-aaaa1111", "status": "ACTIVE",
                "region": "GRA9", "imageId": "img-1",
                "ipAddresses": [{"ip": "1.1.1.1", "type": "public", "version": 4}],
            },
            {  # expired gmab instance
                "id": "inst-old", "name": f"gmab-{old}-60-bbbb2222", "status": "ACTIVE",
                "region": "GRA9", "imageId": "img-1",
                "ipAddresses": [{"ip": "2.2.2.2", "type": "public", "version": 4}],
            },
            {  # not a gmab instance, must be filtered out
                "id": "inst-other", "name": "my-own-box", "status": "ACTIVE",
                "region": "GRA9", "imageId": "img-1", "ipAddresses": [],
            },
        ]

    def _wire_list(self, provider):
        def fake_get(target, **kwargs):
            if target.endswith("/instance"):
                return self._instances()
            if target.endswith("/image"):
                return [{"id": "img-1", "name": "Ubuntu 22.04"}]
            raise AssertionError(f"unexpected GET {target}")
        provider.client.get.side_effect = fake_get

    def test_list_filters_and_computes_expiry(self):
        provider = make_provider()
        self._wire_list(provider)

        instances = provider.list_instances()
        # Only the two gmab-prefixed instances survive (the non-gmab box is filtered).
        self.assertEqual(len(instances), 2)
        self.assertTrue(all(i["label"].startswith("gmab-") for i in instances))
        live = next(i for i in instances if i["instance_id"] == "inst-live")
        old = next(i for i in instances if i["instance_id"] == "inst-old")
        self.assertFalse(live["is_expired"])
        self.assertTrue(old["is_expired"])
        self.assertEqual(live["lifetime_minutes"], 30)  # parsed from the name
        self.assertEqual(live["status"], "running")  # OVH "ACTIVE" normalized
        self.assertEqual(old["status"], "running (expired)")
        self.assertEqual(live["ip"], "1.1.1.1")
        self.assertEqual(live["region"], "GRA9")
        self.assertEqual(live["image"], "Ubuntu 22.04")  # imageId resolved to name
        for inst in instances:
            assert_instance_shape(self, inst)

    def test_list_expired_only(self):
        provider = make_provider()
        self._wire_list(provider)
        expired = provider.list_expired_instances()
        self.assertEqual([i["instance_id"] for i in expired], ["inst-old"])


class TestOVHDetail(unittest.TestCase):
    def test_get_instance_details_calls_single_endpoint(self):
        provider = make_provider()
        provider.client.get.return_value = {"id": "i1", "planCode": "d2-2.consumption"}
        raw = provider.get_instance_details("i1")
        provider.client.get.assert_called_once_with("/cloud/project/proj-123/instance/i1")
        self.assertEqual(raw["planCode"], "d2-2.consumption")

    def test_detail_extras_curates_and_dedupes(self):
        provider = make_provider()
        raw = {"flavor": {"id": "flv-1", "name": "d2-2"}, "planCode": "pc",
               "monthlyBilling": None, "sshKeyId": "k1", "image": {"name": "Ubuntu 22.04"}}
        extras = dict(provider.detail_extras(raw))
        self.assertEqual(extras["Flavor"], "d2-2")
        self.assertEqual(extras["Plan code"], "pc")
        self.assertEqual(extras["SSH key"], "k1")
        # Image/Created live in the common rows and must not be duplicated here.
        self.assertNotIn("Image", extras)
        self.assertNotIn("Created", extras)

    def test_detail_extras_flavor_id_fallback(self):
        provider = make_provider()
        extras = dict(provider.detail_extras({"flavorId": "flv-x"}))
        self.assertEqual(extras["Flavor"], "flv-x")


class TestOVHTerminate(unittest.TestCase):
    def test_terminate_by_native_uuid(self):
        provider = make_provider()
        provider.terminate_instance("0e7b1c2d-1111-2222-3333-444455556666")
        provider.client.delete.assert_called_once_with(
            "/cloud/project/proj-123/instance/0e7b1c2d-1111-2222-3333-444455556666"
        )

    def test_terminate_by_label_resolves_then_deletes(self):
        provider = make_provider()
        with patch.object(provider, "find_instance_id_by_label", return_value="inst-xyz") as finder:
            provider.terminate_instance("gmab-123-60-aaaa1111")
            finder.assert_called_once_with("gmab-123-60-aaaa1111")
        provider.client.delete.assert_called_once_with(
            "/cloud/project/proj-123/instance/inst-xyz"
        )


if __name__ == "__main__":
    unittest.main()
