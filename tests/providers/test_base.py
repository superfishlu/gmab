import os
import re
import tempfile
import time
import unittest

from gmab.providers.hetzner import HetznerProvider
from gmab.providers.linode import LinodeProvider
from gmab.utils.naming import make_label, generate_random_string
from tests.support.fakes import FakeProvider, make_instance


class TestIsExpired(unittest.TestCase):
    def test_not_expired_when_within_lifetime(self):
        now = int(time.time())
        self.assertFalse(FakeProvider.is_expired(now, 60))

    def test_expired_when_past_lifetime(self):
        two_hours_ago = int(time.time()) - 2 * 60 * 60
        self.assertTrue(FakeProvider.is_expired(two_hours_ago, 60))

    def test_accepts_string_inputs(self):
        # Hetzner/AWS read these out of string tags/labels.
        two_hours_ago = int(time.time()) - 2 * 60 * 60
        self.assertTrue(FakeProvider.is_expired(str(two_hours_ago), "60"))


class TestReadSshKey(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider({})

    def test_reads_and_strips_contents(self):
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, "w") as f:
                f.write("ssh-ed25519 AAAA...\n")
            self.assertEqual(self.provider._read_ssh_key(path), "ssh-ed25519 AAAA...")
        finally:
            os.remove(path)

    def test_missing_key_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.provider._read_ssh_key("/nonexistent/path/to/key.pub")


class TestFindInstanceIdByLabel(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider({})
        self.provider.instances = [
            make_instance(instance_id="111", label="gmab-aaa"),
            make_instance(instance_id="222", label="gmab-bbb"),
        ]

    def test_found(self):
        self.assertEqual(self.provider.find_instance_id_by_label("gmab-bbb"), "222")

    def test_not_found(self):
        self.assertIsNone(self.provider.find_instance_id_by_label("gmab-zzz"))


class TestMakeLabel(unittest.TestCase):
    def test_default_format(self):
        label = make_label()
        self.assertTrue(re.fullmatch(r"gmab-[a-z0-9]{12}", label), label)

    def test_custom_prefix_and_length(self):
        label = make_label(prefix="gmab-key", length=8)
        self.assertTrue(re.fullmatch(r"gmab-key-[a-z0-9]{8}", label), label)

    def test_generate_random_string_charset(self):
        s = generate_random_string(20)
        self.assertTrue(re.fullmatch(r"[a-z0-9]{20}", s), s)


class TestSshUser(unittest.TestCase):
    def test_default_is_root(self):
        self.assertEqual(FakeProvider({}).ssh_user(), "root")

    def test_linode_and_hetzner_use_root(self):
        self.assertEqual(LinodeProvider({}).ssh_user(), "root")
        self.assertEqual(HetznerProvider({"api_key": "x"}).ssh_user(), "root")


if __name__ == "__main__":
    unittest.main()
