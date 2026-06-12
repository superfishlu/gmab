"""Reusable contract checks for GMAB providers.

Any provider can be validated against the static side of the ProviderBase
contract by mixing ProviderContractMixin into a unittest.TestCase and setting
``provider_cls``. The mixin deliberately does NOT inherit from TestCase, so it is
never collected on its own — only the concrete subclasses run.
"""

from gmab.providers import get_registry


class ProviderContractMixin:
    # Subclasses must set this to the provider class under test.
    provider_cls = None

    def test_name_is_set_and_registered(self):
        name = self.provider_cls.name
        self.assertTrue(name, "Provider must set a non-empty `name`")
        self.assertIs(
            get_registry().get(name),
            self.provider_cls,
            f"Provider '{name}' is not auto-registered",
        )

    def test_config_schema_non_empty(self):
        self.assertTrue(
            self.provider_cls.CONFIG_SCHEMA,
            "Provider must declare a non-empty CONFIG_SCHEMA",
        )

    def test_default_config_matches_schema(self):
        schema_keys = [f.key for f in self.provider_cls.CONFIG_SCHEMA]
        self.assertEqual(list(self.provider_cls.get_default_config().keys()), schema_keys)

    def test_prompts_cover_every_field(self):
        prompts = self.provider_cls.get_config_prompts({})
        for field in self.provider_cls.CONFIG_SCHEMA:
            self.assertIn(field.key, prompts)

    def test_validate_flags_exactly_required_fields(self):
        required = [f.key for f in self.provider_cls.CONFIG_SCHEMA if f.required]
        # An empty config is missing exactly the required fields...
        self.assertEqual(
            sorted(self.provider_cls.validate_config({})),
            sorted(required),
        )
        # ...and a config with every required field filled is fully valid.
        filled = {key: "x" for key in required}
        self.assertEqual(self.provider_cls.validate_config(filled), [])
