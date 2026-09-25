from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from omarchy_tidal.paths import AppPaths
from omarchy_tidal.tidal import (
    DEFAULT_QUALITY,
    LoginRequired,
    TidalClient,
    _artwork_url,
    first_playable_stream,
    format_quality_label,
    normalize_redirect_url,
    parse_selector,
    playback_source_from_stream,
    quality_fallback,
    stream_resolution,
)


class FakeStream:
    def __init__(
        self,
        mime: str,
        data: str,
        *,
        bts: bool = False,
        mpd: bool = False,
        bit_depth: int = 16,
        sample_rate: int = 44100,
    ) -> None:
        self.manifest_mime_type = mime
        self.is_bts = bts
        self.is_mpd = mpd
        self.bit_depth = bit_depth
        self.sample_rate = sample_rate
        self._data = data

    def get_manifest_data(self) -> str:
        return self._data


class FakeTrack:
    def __init__(self, results: list[object]) -> None:
        self.id = 42
        self._results = list(results)

    def get_stream(self) -> object:
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class SelectorTests(unittest.TestCase):
    def test_parse_selector_kinds(self) -> None:
        self.assertEqual(parse_selector("favs"), ("favorites", ""))
        self.assertEqual(parse_selector("t:56299935"), ("track", "56299935"))
        self.assertEqual(parse_selector("a:1"), ("album", "1"))
        self.assertEqual(parse_selector("p:abc"), ("playlist", "abc"))
        self.assertEqual(parse_selector("r:9"), ("artist", "9"))
        self.assertEqual(parse_selector("56299935"), ("track", "56299935"))
        self.assertEqual(parse_selector("coma white"), ("search", "coma white"))

    def test_artwork_url_from_album_cover(self) -> None:
        album = SimpleNamespace(image=lambda size: f"https://img.example/{size}.jpg")
        track = SimpleNamespace(album=album)
        self.assertEqual(_artwork_url(track), "https://img.example/320.jpg")


class StreamResolutionTests(unittest.TestCase):
    def test_quality_label_includes_resolution(self) -> None:
        self.assertEqual(
            format_quality_label("LOSSLESS", 16, 44100),
            "Lossless 16-bit / 44.1 kHz",
        )
        self.assertEqual(
            format_quality_label("HI_RES_LOSSLESS", 24, 96000),
            "Hi-Res Lossless 24-bit / 96 kHz",
        )

    def test_stream_resolution_from_dash_manifest(self) -> None:
        stream = FakeStream(
            "application/dash+xml",
            '<MPD><Representation id="FLAC,96000,24" audioSamplingRate="96000"/></MPD>',
            mpd=True,
            bit_depth=16,
            sample_rate=44100,
        )
        self.assertEqual(stream_resolution(stream), (24, 96000))

    def test_default_quality_is_hi_res(self) -> None:
        self.assertEqual(DEFAULT_QUALITY, "HI_RES_LOSSLESS")
        self.assertEqual(quality_fallback("LOSSLESS"), ("LOSSLESS", "HIGH", "LOW"))
        self.assertEqual(
            quality_fallback("HI_RES_LOSSLESS"),
            ("HI_RES_LOSSLESS", "LOSSLESS", "HIGH", "LOW"),
        )

    def test_bts_stream_becomes_direct_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "cache", root / "runtime")
            stream = FakeStream(
                "application/vnd.tidal.bts",
                json.dumps({"urls": ["https://cdn.example.test/track.flac"]}),
                bts=True,
            )
            source = playback_source_from_stream(
                stream, quality="LOSSLESS", track_id="42", paths=paths
            )
            self.assertEqual(source.kind, "url")
            self.assertEqual(source.target, "https://cdn.example.test/track.flac")
            self.assertFalse(paths.manifest_dir.exists())

    def test_dash_stream_writes_private_mpd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "cache", root / "runtime")
            stream = FakeStream(
                "application/dash+xml",
                "<MPD>dash</MPD>",
                mpd=True,
            )
            source = playback_source_from_stream(
                stream, quality="HI_RES_LOSSLESS", track_id="42", paths=paths
            )
            manifest = Path(source.target)
            self.assertEqual(source.kind, "dash")
            self.assertEqual(manifest, paths.manifest_dir / "42.mpd")
            self.assertEqual(manifest.read_text(encoding="utf-8"), "<MPD>dash</MPD>")
            self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)

    def test_quality_fallback_skips_failed_stream(self) -> None:
        track = FakeTrack(
            [
                RuntimeError("hi-res unavailable"),
                FakeStream(
                    "application/vnd.tidal.bts",
                    json.dumps({"urls": ["https://cdn.example.test/track.flac"]}),
                    bts=True,
                ),
            ]
        )
        session = SimpleNamespace(audio_quality=None)
        stream, quality = first_playable_stream(track, session, "HI_RES_LOSSLESS")
        self.assertEqual(quality, "LOSSLESS")
        self.assertTrue(stream.is_bts)


class FakePkceSession:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            code_verifier="verifier-123",
            code_challenge="challenge-456",
            client_unique_key="key-789",
        )
        self.redirects: list[str] = []
        self.saved_to: list[Path] = []

    def pkce_login_url(self) -> str:
        return "https://login.tidal.com/authorize?code_challenge=challenge-456"

    def pkce_get_auth_token(self, url_redirect: str) -> dict[str, object]:
        self.redirects.append(url_redirect)
        return {
            "access_token": "tok",
            "expires_in": 3600,
            "refresh_token": "ref",
            "token_type": "Bearer",
        }

    def process_auth_token(self, token: dict[str, object], is_pkce_token: bool = True) -> bool:
        return True

    def save_session_to_file(self, session_file: Path) -> None:
        session_file.write_text("session-data", encoding="utf-8")
        self.saved_to.append(session_file)


class LoginFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.paths = AppPaths(root / "config", root / "cache", root / "runtime")
        self.client = TidalClient(self.paths)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_login_start_saves_pending_state_and_opens_browser(self) -> None:
        with patch("tidalapi.Session", FakePkceSession), patch(
            "omarchy_tidal.tidal.webbrowser"
        ) as browser:
            payload = self.client.login_start()
        self.assertEqual(payload["state"], "pending")
        self.assertIn("login.tidal.com", str(payload["url"]))
        browser.open.assert_called_once_with(payload["url"])
        self.assertTrue(self.paths.login_pending_file.is_file())
        state = json.loads(self.paths.login_pending_file.read_text(encoding="utf-8"))
        self.assertEqual(state["code_verifier"], "verifier-123")
        self.assertEqual(state["client_unique_key"], "key-789")
        self.assertEqual(self.paths.login_pending_file.stat().st_mode & 0o777, 0o600)

    def test_login_start_without_browser_does_not_open(self) -> None:
        with patch("tidalapi.Session", FakePkceSession), patch(
            "omarchy_tidal.tidal.webbrowser"
        ) as browser:
            self.client.login_start(open_browser=False)
        browser.open.assert_not_called()

    def test_login_start_is_idempotent_while_pending(self) -> None:
        with patch("tidalapi.Session", FakePkceSession), patch(
            "omarchy_tidal.tidal.webbrowser"
        ) as browser:
            first = self.client.login_start(open_browser=False)
            second = self.client.login_start(open_browser=False)
        self.assertEqual(first["url"], second["url"])
        browser.open.assert_not_called()

    def test_login_start_reports_existing_session(self) -> None:
        self.paths.prepare_private_dirs()
        self.paths.session_file.write_text("{}", encoding="utf-8")
        with patch.object(self.client, "session", return_value=object()), patch(
            "omarchy_tidal.tidal.webbrowser"
        ) as browser:
            payload = self.client.login_start()
        self.assertEqual(payload["state"], "already_logged_in")
        self.assertTrue(payload["logged_in"])
        browser.open.assert_not_called()

    def test_login_finish_completes_session(self) -> None:
        with patch("tidalapi.Session", FakePkceSession):
            self.client.login_start(open_browser=False)
            payload = self.client.login_finish(
                "https://tidal.com/android/login/auth?code=abc"
            )
        self.assertEqual(payload["state"], "done")
        self.assertTrue(payload["logged_in"])
        self.assertTrue(self.paths.session_file.is_file())
        self.assertEqual(self.paths.session_file.stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.paths.login_pending_file.exists())

    def test_login_finish_without_pending_fails(self) -> None:
        with self.assertRaisesRegex(LookupError, "No login in progress"):
            self.client.login_finish("https://tidal.com/android/login/auth?code=abc")

    def test_login_finish_fails_when_session_not_saved(self) -> None:
        class NoSaveSession(FakePkceSession):
            def save_session_to_file(self, session_file: Path) -> None:
                return

        with patch("tidalapi.Session", NoSaveSession):
            self.client.login_start(open_browser=False)
            with self.assertRaisesRegex(LoginRequired, "session was not saved"):
                self.client.login_finish("https://tidal.com/android/login/auth?code=abc")
        self.assertFalse(self.paths.session_file.exists())
        self.assertFalse(self.paths.login_pending_file.exists())

    def test_login_finish_failure_drops_pending_state(self) -> None:
        class BrokenExchange(FakePkceSession):
            def pkce_get_auth_token(self, url_redirect: str) -> dict[str, object]:
                raise RuntimeError("boom")

        with patch("tidalapi.Session", BrokenExchange):
            self.client.login_start(open_browser=False)
            with self.assertRaisesRegex(LoginRequired, "TIDAL login failed"):
                self.client.login_finish("https://tidal.com/android/login/auth?code=abc")
        self.assertFalse(self.paths.login_pending_file.exists())

    def test_logout_removes_session_and_pending(self) -> None:
        self.paths.prepare_private_dirs()
        self.paths.session_file.write_text("{}", encoding="utf-8")
        self.paths.login_pending_file.write_text("{}", encoding="utf-8")
        self.client.logout()
        self.assertFalse(self.paths.session_file.exists())
        self.assertFalse(self.paths.login_pending_file.exists())


class RedirectNormalizationTests(unittest.TestCase):
    def test_full_url_is_unchanged(self) -> None:
        url = "https://tidal.com/android/login/auth?code=abc"
        self.assertEqual(normalize_redirect_url(url), url)

    def test_raw_code_is_wrapped(self) -> None:
        self.assertEqual(
            normalize_redirect_url("abc"),
            "https://tidal.com/android/login/auth?code=abc",
        )

    def test_query_fragment_is_wrapped(self) -> None:
        self.assertEqual(
            normalize_redirect_url("?code=abc&other=1"),
            "https://tidal.com/android/login/auth?code=abc&other=1",
        )


class FakeFavorites:
    def __init__(self, ids: set[str]) -> None:
        self._ids = set(ids)
        self.list_calls = 0

    def tracks(self, limit: int = 50) -> list[object]:
        self.list_calls += 1
        return [
            SimpleNamespace(
                id=ident,
                full_name=f"track {ident}",
                name=f"track {ident}",
                artists=[SimpleNamespace(name="Artist")],
                album=None,
                duration=100,
                image=None,
            )
            for ident in list(self._ids)[:limit]
        ]

    def add_track(self, track_id: str) -> bool:
        self._ids.add(str(track_id))
        return True

    def remove_track(self, track_id: str) -> bool:
        self._ids.discard(str(track_id))
        return True


class FavoritesCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.paths = AppPaths(root / "config", root / "cache", root / "runtime")
        self.client = TidalClient(self.paths)
        self.favorites = FakeFavorites({"1", "2"})
        session = SimpleNamespace(user=SimpleNamespace(favorites=self.favorites))
        self.patcher = patch.object(self.client, "session", return_value=session)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.directory.cleanup()

    def test_membership_from_cached_list(self) -> None:
        self.assertTrue(self.client.is_favorite_track("1"))
        self.assertTrue(self.client.is_favorite_track("2"))
        self.assertFalse(self.client.is_favorite_track("3"))

    def test_list_is_fetched_once(self) -> None:
        for ident in ("1", "2", "3", "1"):
            self.client.is_favorite_track(ident)
        self.assertEqual(self.favorites.list_calls, 1)

    def test_add_updates_cache_without_refetch(self) -> None:
        self.client.is_favorite_track("1")
        self.assertTrue(self.client.add_favorite_track("3"))
        self.assertTrue(self.client.is_favorite_track("3"))
        self.assertEqual(self.favorites.list_calls, 1)

    def test_remove_updates_cache_without_refetch(self) -> None:
        self.client.is_favorite_track("1")
        self.assertTrue(self.client.remove_favorite_track("1"))
        self.assertFalse(self.client.is_favorite_track("1"))
        self.assertEqual(self.favorites.list_calls, 1)


if __name__ == "__main__":
    unittest.main()
