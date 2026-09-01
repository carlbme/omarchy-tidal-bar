from __future__ import annotations

import contextlib
import io
import json
import unittest

from omarchy_tidal.cli import main


class CliTests(unittest.TestCase):
    def test_status_json_contract(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["status", "--json"])

        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertFalse(payload["available"])
        self.assertEqual(payload["state"], "stopped")
        self.assertIsNone(payload["track"])

    def test_command_name_does_not_claim_tidal(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("usage: otidal", output.getvalue())


if __name__ == "__main__":
    unittest.main()

