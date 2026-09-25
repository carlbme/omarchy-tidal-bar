from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_favorite_help_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["favorite", "--help"])
        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("on", help_text)
        self.assertIn("off", help_text)

    def test_shuffle_help_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["shuffle", "--help"])
        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("on", help_text)
        self.assertIn("off", help_text)
        self.assertIn("selector", help_text)

    def test_shuffle_request_params(self) -> None:
        cases = {
            ("shuffle",): {},
            ("shuffle", "on"): {"enabled": True},
            ("shuffle", "off"): {"enabled": False},
            ("shuffle", "favs"): {"selector": "favs"},
            ("shuffle", "on", "favs"): {"enabled": True, "selector": "favs"},
        }
        for argv, expected in cases.items():
            with patch(
                "omarchy_tidal.cli.request",
                return_value={"schema_version": 1, "shuffle": True},
            ) as mock_request:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main(list(argv))
            self.assertEqual(result, 0, argv)
            self.assertEqual(mock_request.call_args.args[0], "shuffle", argv)
            self.assertEqual(mock_request.call_args.args[1], expected, argv)
            self.assertTrue(mock_request.call_args.kwargs.get("start"), argv)

    def test_login_start_help_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["login", "start", "--help"])
        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("--no-browser", help_text)
        self.assertIn("--json", help_text)

    def test_login_finish_help_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["login", "finish", "--help"])
        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("--redirect", help_text)

    def test_logout_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["logout", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("logout", output.getvalue())

    def test_remove_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["remove", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("position", output.getvalue())

    def test_status_json_reports_logged_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_home = Path(directory)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main(["status", "--json"])
                self.assertEqual(result, 0)
                payload = json.loads(output.getvalue())
                self.assertFalse(payload["logged_in"])

            (config_home / "otidal").mkdir(parents=True)
            (config_home / "otidal" / "session.json").write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main(["status", "--json"])
                self.assertEqual(result, 0)
                payload = json.loads(output.getvalue())
                self.assertTrue(payload["logged_in"])

    def test_login_start_help_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["login", "start", "--help"])
        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("--no-browser", help_text)
        self.assertIn("--json", help_text)

    def test_login_finish_help_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["login", "finish", "--help"])
        self.assertEqual(raised.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("--redirect", help_text)

    def test_logout_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["logout", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("logout", output.getvalue())

    def test_remove_is_documented(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                main(["remove", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("position", output.getvalue())

    def test_status_json_reports_logged_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_home = Path(directory)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main(["status", "--json"])
                self.assertEqual(result, 0)
                payload = json.loads(output.getvalue())
                self.assertFalse(payload["logged_in"])

            (config_home / "otidal").mkdir(parents=True)
            (config_home / "otidal" / "session.json").write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main(["status", "--json"])
                self.assertEqual(result, 0)
                payload = json.loads(output.getvalue())
                self.assertTrue(payload["logged_in"])


if __name__ == "__main__":
    unittest.main()

