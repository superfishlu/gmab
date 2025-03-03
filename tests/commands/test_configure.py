import unittest

from gmab.providers import *


class TestConfigure(unittest.TestCase):
    def assertAllIn(self, keys, dictionary):
        for key in keys:
            self.assertIn(key, dictionary)


    def test_provider_configs(self):
        # AWS
        aws_keys = ['access_key', 'secret_key', 'default_region', 'default_image', 'default_type']
        aws_config = AWSProvider.get_config_prompts({})
        self.assertAllIn(aws_keys, aws_config)

        # Linode
        linode_keys = ['api_key', 'default_region', 'default_image', 'default_type', 'default_root_pass']
        linode_config = LinodeProvider.get_config_prompts({})
        self.assertAllIn(linode_keys, linode_config)

        # Hetzner
        hetzner_keys = ['api_key', 'default_region', 'default_image', 'default_type']
        hetzner_config = HetznerProvider.get_config_prompts({})
        self.assertAllIn(hetzner_keys, hetzner_config)


    def test_provider_configurations(self):
        aws_provider = AWSProvider({})
        linode_provider = LinodeProvider({})
        hetzner_provider = HetznerProvider({"api_key": "yes"})
