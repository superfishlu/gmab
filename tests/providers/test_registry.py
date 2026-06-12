import unittest

from gmab.providers import (
    get_registry,
    get_available_providers,
    get_provider,
    AWSProvider,
    LinodeProvider,
    HetznerProvider,
    OVHProvider,
)
from tests.providers.provider_contract import ProviderContractMixin


class TestRegistry(unittest.TestCase):
    def test_shipped_providers_auto_register(self):
        # Subset (not exact equality) so adding a provider later doesn't break this.
        self.assertTrue({"aws", "hetzner", "linode"}.issubset(get_available_providers()))

    def test_registry_maps_to_classes(self):
        registry = get_registry()
        self.assertIs(registry["linode"], LinodeProvider)
        self.assertIs(registry["aws"], AWSProvider)
        self.assertIs(registry["hetzner"], HetznerProvider)

    def test_template_is_not_registered(self):
        # The underscore-prefixed reference template must never register.
        self.assertNotIn(None, get_registry())
        self.assertNotIn("template", get_registry())

    def test_get_provider_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_provider("nope", {"api_key": "x"})

    def test_get_provider_empty_config_raises(self):
        with self.assertRaises(ValueError):
            get_provider("linode", {})

    def test_get_provider_sets_provider_name(self):
        provider = get_provider("linode", {"api_key": "x"})
        self.assertEqual(provider.provider_name, "linode")


# Concrete contract tests for each shipped provider, driven by the shared mixin.

class TestLinodeContract(ProviderContractMixin, unittest.TestCase):
    provider_cls = LinodeProvider


class TestAWSContract(ProviderContractMixin, unittest.TestCase):
    provider_cls = AWSProvider


class TestHetznerContract(ProviderContractMixin, unittest.TestCase):
    provider_cls = HetznerProvider


class TestOVHContract(ProviderContractMixin, unittest.TestCase):
    provider_cls = OVHProvider


if __name__ == "__main__":
    unittest.main()
