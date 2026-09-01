from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from omarchy_tidal.mpv import MpvController, PlayerUnavailable
from omarchy_tidal.paths import AppPaths


class MpvControllerTests(unittest.TestCase):
    def test_json_ipc_command(self) -> None:
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.makefile.return_value = iter(
            [json.dumps({"request_id": 1, "error": "success", "data": False}) + "\n"]
        )
        socket_factory = MagicMock(return_value=connection)

        with patch("omarchy_tidal.mpv.socket.socket", socket_factory):
            result = MpvController().command(["get_property", "pause"])

        self.assertFalse(result)
        sent = json.loads(connection.sendall.call_args.args[0].decode())
        self.assertEqual(sent["command"], ["get_property", "pause"])
        self.assertEqual(sent["request_id"], 1)

    def test_absent_player_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "cache", root / "runtime")
            with self.assertRaisesRegex(PlayerUnavailable, "not running"):
                MpvController(paths).command(["stop"])


if __name__ == "__main__":
    unittest.main()
