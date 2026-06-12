"""The instance-dict contract every provider must satisfy.

spawn_instance() and list_instances() return dicts with at least these keys; the
`list` command relies on creation_time + lifetime_minutes to compute lifetime.
"""

INSTANCE_KEYS = (
    "provider",
    "instance_id",
    "label",
    "ip",
    "status",
    "region",
    "image",
    "creation_time",
    "lifetime_minutes",
)


def assert_instance_shape(test, instance):
    """Assert `instance` is a contract-shaped dict (used across provider tests)."""
    for key in INSTANCE_KEYS:
        test.assertIn(key, instance, f"instance dict missing '{key}'")
    test.assertIsInstance(instance["instance_id"], str)
    test.assertIsInstance(instance["label"], str)
    test.assertIsInstance(instance["creation_time"], int)
    test.assertIsInstance(instance["lifetime_minutes"], int)
