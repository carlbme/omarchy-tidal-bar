from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omarchy_tidal.paths import AppPaths
from omarchy_tidal.tidal import LoginRequired, TidalClient


class PathIsolationTests(unittest.TestCase):
    def test_all_paths_use_otidal_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_CACHE_HOME": str(root / "cache"),
                "XDG_RUNTIME_DIR": str(root / "runtime"),
            }
            with patch.dict(os.environ, environment, clear=False):
                paths = AppPaths.from_environment()

            self.assertEqual(paths.session_file, root / "config/otidal/session.json")
            self.assertEqual(paths.manifest_dir, root / "cache/otidal/manifests")
            self.assertEqual(paths.mpv_socket, root / "runtime/otidal/mpv.sock")
            for path in (paths.session_file, paths.manifest_dir, paths.mpv_socket):
                self.assertNotIn("upmpdcli", str(path))
                self.assertNotIn("tidal-cli", str(path))

    def test_missing_own_session_never_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "cache", root / "runtime")
            with self.assertRaisesRegex(LoginRequired, "otidal login"):
                TidalClient(paths).session()


if __name__ == "__main__":
    unittest.main()

