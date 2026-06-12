"""Test base that isolates all config I/O into a throwaway directory.

GMAB resolves its config dir from $GMAB_CONFIG_DIR first (see
gmab/utils/paths.py:get_config_dir), so pointing that env var at a tempdir keeps
every test off the user's real ~/.config/gmab / %APPDATA%\\gmab. Any test that
loads or saves config must subclass ConfigDirTestCase.
"""

import os
import tempfile
import unittest

from gmab.utils.config_loader import save_config


class ConfigDirTestCase(unittest.TestCase):
    def setUp(self):
        self._prev_config_dir = os.environ.get("GMAB_CONFIG_DIR")
        self._tmp = tempfile.mkdtemp(prefix="gmab-test-")
        os.environ["GMAB_CONFIG_DIR"] = self._tmp

    def tearDown(self):
        if self._prev_config_dir is None:
            os.environ.pop("GMAB_CONFIG_DIR", None)
        else:
            os.environ["GMAB_CONFIG_DIR"] = self._prev_config_dir
        # Best-effort cleanup of the temp config dir.
        for root, _dirs, files in os.walk(self._tmp, topdown=False):
            for name in files:
                try:
                    os.remove(os.path.join(root, name))
                except OSError:
                    pass
            try:
                os.rmdir(root)
            except OSError:
                pass

    @property
    def config_dir(self):
        return self._tmp

    def write_configs(self, general=None, providers=None):
        """Write config.json / providers.json into the temp dir via the real saver."""
        if general is not None:
            save_config(general, "config.json")
        if providers is not None:
            save_config(providers, "providers.json")
