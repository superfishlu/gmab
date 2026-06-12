import os
from pathlib import Path

from gmab.utils.paths import get_config_dir, get_config_file_path
from tests.support.config_env import ConfigDirTestCase


class TestPaths(ConfigDirTestCase):
    def test_env_override_wins(self):
        self.assertEqual(get_config_dir(), Path(os.environ["GMAB_CONFIG_DIR"]))
        self.assertEqual(get_config_dir(), Path(self.config_dir))

    def test_get_config_file_path_joins_filename(self):
        self.assertEqual(
            get_config_file_path("providers.json"),
            Path(self.config_dir) / "providers.json",
        )
