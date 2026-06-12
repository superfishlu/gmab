import time
import unittest
from unittest.mock import MagicMock, patch

from botocore.stub import Stubber

from gmab.providers.aws import AWSProvider
from tests.support.contracts import assert_instance_shape


def make_provider():
    p = AWSProvider({
        "access_key": "AKIAFAKE",
        "secret_key": "secretfake",
        "default_region": "eu-west-1",
        "default_image": "ami-123",
        "default_type": "t3.micro",
    })
    p.provider_name = "aws"
    return p


def _instance(instance_id, name, ip, created, life, key_name=None):
    inst = {
        "InstanceId": instance_id,
        "State": {"Name": "running"},
        "PublicIpAddress": ip,
        "Placement": {"AvailabilityZone": "eu-west-1a"},
        "ImageId": "ami-123",
        "Tags": [
            {"Key": "Name", "Value": name},
            {"Key": "gmab", "Value": "true"},
            {"Key": "gmab-creation-time", "Value": str(created)},
            {"Key": "gmab-lifetime", "Value": str(life)},
        ],
    }
    if key_name:
        inst["KeyName"] = key_name
    return inst


class TestAWSClaimsIdentifier(unittest.TestCase):
    def test_claims_aws_ids_only(self):
        self.assertTrue(AWSProvider.claims_identifier("i-0abc"))
        self.assertFalse(AWSProvider.claims_identifier("gmab-foo"))
        self.assertFalse(AWSProvider.claims_identifier("12345"))


class TestAWSList(unittest.TestCase):
    def test_list_parses_and_computes_expiry(self):
        now = int(time.time())
        old = now - 2 * 60 * 60
        provider = make_provider()
        stub = Stubber(provider.ec2)
        stub.add_response(
            "describe_instances",
            {"Reservations": [{"Instances": [
                _instance("i-1", "gmab-live", "1.1.1.1", now, 60),
                _instance("i-2", "gmab-old", "2.2.2.2", old, 60),
            ]}]},
        )
        with stub:
            instances = provider.list_instances()

        by_label = {i["label"]: i for i in instances}
        self.assertEqual(set(by_label), {"gmab-live", "gmab-old"})
        self.assertFalse(by_label["gmab-live"]["is_expired"])
        self.assertTrue(by_label["gmab-old"]["is_expired"])
        self.assertIn("(expired)", by_label["gmab-old"]["status"])
        self.assertEqual(by_label["gmab-live"]["region"], "eu-west-1")
        for inst in instances:
            assert_instance_shape(self, inst)


class TestAWSTerminate(unittest.TestCase):
    def test_terminate_deletes_keypair_then_instance(self):
        now = int(time.time())
        provider = make_provider()
        stub = Stubber(provider.ec2)
        stub.add_response(
            "describe_instances",
            {"Reservations": [{"Instances": [
                _instance("i-1", "gmab-live", "1.1.1.1", now, 60, key_name="gmab-key-abc")
            ]}]},
        )
        stub.add_response("delete_key_pair", {})
        stub.add_response("terminate_instances", {})
        with stub:
            provider.terminate_instance("i-1")
        stub.assert_no_pending_responses()

    def test_find_instance_id_by_label(self):
        now = int(time.time())
        provider = make_provider()
        stub = Stubber(provider.ec2)
        stub.add_response(
            "describe_instances",
            {"Reservations": [{"Instances": [
                _instance("i-7", "gmab-target", "1.1.1.1", now, 60)
            ]}]},
        )
        with stub:
            self.assertEqual(provider.find_instance_id_by_label("gmab-target"), "i-7")


class TestAWSSpawn(unittest.TestCase):
    @patch.object(AWSProvider, "_read_ssh_key", return_value="ssh-ed25519 AAAA")
    def test_spawn_tags_and_returns_contract(self, _ssh):
        provider = make_provider()
        # Bypass the VPC/SG/subnet creation dance.
        provider.get_or_create_vpc = lambda: "vpc-1"
        provider.get_or_create_security_group = lambda vpc_id: "sg-1"
        provider.get_subnet_id = lambda vpc_id: "subnet-1"
        # Replace the EC2 client with a mock so we can assert run_instances payload.
        provider.ec2 = MagicMock()
        provider.ec2.run_instances.return_value = {"Instances": [{"InstanceId": "i-99"}]}
        provider.ec2.describe_instances.return_value = {
            "Reservations": [{"Instances": [
                {"State": {"Name": "running"}, "PublicIpAddress": "9.9.9.9"}
            ]}]
        }
        provider.ec2.get_waiter.return_value = MagicMock()

        result = provider.spawn_instance(image="ami-123", region="eu-west-1", lifetime_minutes=15)

        kwargs = provider.ec2.run_instances.call_args.kwargs
        self.assertEqual(kwargs["ImageId"], "ami-123")
        self.assertEqual(kwargs["InstanceType"], "t3.micro")
        tags = {t["Key"]: t["Value"] for t in kwargs["TagSpecifications"][0]["Tags"]}
        self.assertEqual(tags["gmab"], "true")
        self.assertEqual(tags["gmab-lifetime"], "15")
        self.assertIn("gmab-creation-time", tags)
        self.assertTrue(tags["Name"].startswith("gmab-"))

        assert_instance_shape(self, result)
        self.assertEqual(result["instance_id"], "i-99")
        self.assertEqual(result["ip"], "9.9.9.9")
        self.assertEqual(result["lifetime_minutes"], 15)


if __name__ == "__main__":
    unittest.main()
