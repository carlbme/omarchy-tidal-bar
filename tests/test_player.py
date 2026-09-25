from __future__ import annotations

import random
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from omarchy_tidal.ipc import PlayerError, call_player, encode_response
from omarchy_tidal.paths import AppPaths
from omarchy_tidal.player import Player
from omarchy_tidal.queue import PlayQueue
from omarchy_tidal.tidal import CatalogTrack, PlaybackSource, parse_selector


class FakeMpv:
    def __init__(self) -> None:
        self.loaded: tuple[str, str] | None = None
        self.paused = False
        self.quit_called = False
        self.position = 0.0
        self.volume = 1.0

    def load(self, source: str, title: str) -> None:
        self.loaded = (source, title)
        self.paused = False
        self.position = 0.0

    def stop(self) -> None:
        self.loaded = None
        self.position = 0.0

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def seek(self, position: float) -> None:
        self.position = position

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def quit(self) -> None:
        self.quit_called = True
        self.loaded = None

    def status(self) -> dict[str, object]:
        if not self.loaded:
            return {
                "available": True,
                "state": "stopped",
                "title": "",
                "position": 0.0,
                "duration": 0.0,
                "volume": self.volume,
            }
        return {
            "available": True,
            "state": "paused" if self.paused else "playing",
            "title": self.loaded[1],
            "position": self.position,
            "duration": 120.0,
            "volume": self.volume,
        }


class FakeTidal:
    def __init__(self) -> None:
        self.radio_calls = 0
        self.logged_out = False
        self.favorite_ids = {"1", "2"}
        self.catalog = {
            "1": CatalogTrack("1", "One", "Artist", "Album", 10),
            "2": CatalogTrack("2", "Two", "Artist", "Album", 10),
            "3": CatalogTrack("3", "Three", "Artist", "Album", 10),
            "56299935": CatalogTrack(
                "56299935", "Coma White", "Marilyn Manson", "Mechanical Animals", 338
            ),
        }

    def resolve_track(self, selector: str) -> tuple[object, CatalogTrack]:
        track_id = selector.removeprefix("t:")
        if "missing" in selector or track_id not in self.catalog:
            raise LookupError(f"No TIDAL tracks found for {selector!r}")
        return SimpleNamespace(id=track_id), self.catalog[track_id]

    def resolve_playback(self, track: object) -> PlaybackSource:
        track_id = str(getattr(track, "id"))
        return PlaybackSource(
            kind="url",
            target=f"https://cdn.example.test/{track_id}.flac",
            quality="LOSSLESS",
            bit_depth=16,
            sample_rate=44100,
        )

    def expand_tracks(self, selector: str, limit: int = 50) -> list[CatalogTrack]:
        kind, ident = parse_selector(selector)
        if kind == "favorites":
            return [self.catalog["1"], self.catalog["2"]]
        if kind == "album":
            return [self.catalog["1"], self.catalog["2"], self.catalog["3"]]
        if kind == "playlist":
            return [self.catalog["3"], self.catalog["1"]]
        if kind == "artist":
            return [self.catalog["2"], self.catalog["3"]]
        if kind == "track":
            return [self.resolve_track(f"t:{ident}")[1]]
        return [self.resolve_track(ident)[1]]

    def radio_tracks(self, selector: str, limit: int = 30) -> list[CatalogTrack]:
        self.radio_calls += 1
        seed = self.expand_tracks(selector, limit=1)[0]
        rest = [track for track in self.catalog.values() if track.id != seed.id]
        if self.radio_calls == 1:
            return [seed]
        return [seed, *rest[:limit]]

    def is_favorite_track(self, track_id: str) -> bool:
        return str(track_id) in self.favorite_ids

    def add_favorite_track(self, track_id: str) -> bool:
        self.favorite_ids.add(str(track_id))
        return True

    def remove_favorite_track(self, track_id: str) -> bool:
        self.favorite_ids.discard(str(track_id))
        return True

    def logout(self) -> None:
        self.logged_out = True


class PlayQueueTests(unittest.TestCase):
    def test_replace_append_and_neighbors(self) -> None:
        queue = PlayQueue()
        queue.replace({"id": "1"})
        queue.append({"id": "2"})
        self.assertEqual(queue.index, 0)
        self.assertEqual(queue.next_index(), 1)
        self.assertIsNone(queue.previous_index())
        queue.index = 1
        self.assertEqual(queue.previous_index(), 0)
        self.assertIsNone(queue.next_index())

    def test_shuffle_remaining_keeps_current_and_played(self) -> None:
        queue = PlayQueue()
        for ident in ("a", "b", "c", "d", "e"):
            queue.append({"id": ident})
        queue.index = 1
        queue.shuffle_remaining(random.Random(0))
        self.assertEqual(queue.items[0]["id"], "a")
        self.assertEqual(queue.items[1]["id"], "b")
        self.assertEqual({item["id"] for item in queue.items[2:]}, {"c", "d", "e"})
        self.assertEqual(len(queue.items), 5)


class PlayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.paths = AppPaths(root / "config", root / "cache", root / "runtime")
        self.mpv = FakeMpv()
        self.player = Player(self.paths, tidal=FakeTidal(), mpv=self.mpv)  # type: ignore[arg-type]

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_play_stop_toggle_status(self) -> None:
        played = self.player.play("t:56299935")
        self.assertEqual(played["state"], "playing")
        self.assertEqual(played["source"]["kind"], "url")
        self.assertEqual(self.mpv.loaded[0], "https://cdn.example.test/56299935.flac")

        status = self.player.status()
        self.assertTrue(status["available"])
        self.assertEqual(status["state"], "playing")
        self.assertEqual(status["track"]["title"], "Coma White")
        self.assertEqual(status["track"]["quality"], "Lossless 16-bit / 44.1 kHz")
        self.assertEqual(status["index"], 0)
        self.assertEqual(len(status["queue"]), 1)

        toggled = self.player.toggle()
        self.assertEqual(toggled["state"], "paused")
        self.assertEqual(self.player.stop()["state"], "stopped")
        self.assertIsNone(self.mpv.loaded)

    def test_play_replaces_queue_append_does_not(self) -> None:
        self.player.play("t:1")
        queued = self.player.enqueue("t:2")
        self.assertEqual(queued["state"], "queued")
        self.assertEqual(queued["length"], 2)
        self.assertEqual(self.mpv.loaded[0], "https://cdn.example.test/1.flac")

        self.player.play("t:3")
        self.assertEqual(len(self.player.play_queue.items), 1)
        self.assertEqual(self.player.play_queue.current()["id"], "3")

    def test_jump_plays_queue_position(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.player.enqueue("t:3")
        jumped = self.player.jump(2)
        self.assertEqual(jumped["track"]["id"], "3")
        self.assertEqual(self.mpv.loaded[0], "https://cdn.example.test/3.flac")

    def test_next_and_previous(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.player.enqueue("t:3")
        nxt = self.player.next_track()
        self.assertEqual(nxt["track"]["id"], "2")
        self.mpv.position = 1.0
        prev = self.player.previous_track()
        self.assertEqual(prev["track"]["id"], "1")

    def test_previous_rewinds_when_late_in_track(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.mpv.position = 12.0
        self.player.previous_track()
        self.assertEqual(self.mpv.position, 0.0)
        self.assertEqual(self.player.play_queue.index, 0)

    def test_auto_advance_on_end(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.mpv.loaded = None
        self.player._maybe_auto_advance()
        self.assertEqual(self.player.play_queue.index, 1)
        self.assertEqual(self.mpv.loaded[0], "https://cdn.example.test/2.flac")

    def test_stop_does_not_auto_advance(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.player.stop()
        self.player._maybe_auto_advance()
        self.assertIsNone(self.mpv.loaded)
        self.assertEqual(self.player.play_queue.index, 0)

    def test_play_unknown_track(self) -> None:
        with self.assertRaisesRegex(LookupError, "missing"):
            self.player.play("missing song")

    def test_play_album_expands_queue(self) -> None:
        played = self.player.play("a:99")
        self.assertEqual(played["track"]["id"], "1")
        self.assertEqual(played["length"], 3)

    def test_radio_replenishes_before_end(self) -> None:
        started = self.player.radio("t:1")
        self.assertEqual(self.player.radio_seed_id, "1")
        self.assertGreater(started["length"], 1)
        self.assertGreater(self.player.tidal.radio_calls, 1)  # type: ignore[attr-defined]

    def test_shuffle_toggle_reorders_tail(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.player.enqueue("t:3")
        with patch("omarchy_tidal.queue.random.shuffle", side_effect=lambda xs: xs.reverse()):
            payload = self.player.handle("shuffle")
        self.assertTrue(payload["shuffle"])
        ids = [item["id"] for item in self.player.play_queue.items]
        self.assertEqual(ids[0], "1")
        self.assertEqual(ids, ["1", "3", "2"])
        off = self.player.handle("shuffle", {"enabled": False})
        self.assertFalse(off["shuffle"])
        self.assertEqual([item["id"] for item in self.player.play_queue.items], ["1", "3", "2"])

    def test_enqueue_while_shuffled_mixes_into_tail(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        with patch("omarchy_tidal.queue.random.shuffle", side_effect=lambda xs: xs.reverse()):
            self.player.handle("shuffle", {"enabled": True})
            self.player.enqueue("t:3")
        ids = [item["id"] for item in self.player.play_queue.items]
        self.assertEqual(ids[0], "1")
        self.assertEqual(ids, ["1", "3", "2"])
        self.assertTrue(self.player.status()["shuffle"])

    def test_shuffle_with_selector_queues_favorites_and_starts(self) -> None:
        with patch("omarchy_tidal.queue.random.shuffle", side_effect=lambda xs: xs.reverse()):
            payload = self.player.handle("shuffle", {"selector": "favs"})
        self.assertEqual(payload["state"], "playing")
        self.assertTrue(payload["shuffle"])
        self.assertEqual(payload["added"], 2)
        self.assertEqual(self.player.play_queue.index, 0)
        self.assertEqual(self.player.play_queue.current()["id"], "2")
        self.assertEqual(self.mpv.loaded[0], "https://cdn.example.test/2.flac")
        self.assertTrue(self.player.shuffle_on)

    def test_shuffle_with_selector_appends_deduped_and_keeps_current(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:3")
        with patch("omarchy_tidal.queue.random.shuffle", side_effect=lambda xs: xs.reverse()):
            payload = self.player.handle("shuffle", {"selector": "favs"})
        self.assertEqual(payload["state"], "playing")
        self.assertEqual(payload["added"], 1)
        self.assertEqual(payload["length"], 3)
        self.assertEqual(self.player.play_queue.current()["id"], "1")
        self.assertEqual([item["id"] for item in self.player.play_queue.items], ["1", "2", "3"])
        self.assertTrue(self.player.shuffle_on)

    def test_shuffle_with_selector_unknown_raises(self) -> None:
        with self.assertRaisesRegex(LookupError, "missing"):
            self.player.handle("shuffle", {"selector": "missing"})

    def test_status_includes_shuffle(self) -> None:
        self.assertFalse(self.player.status()["shuffle"])
        self.player.handle("shuffle", {"enabled": True})
        self.assertTrue(self.player.status()["shuffle"])

    def test_play_reports_favorite_from_catalog(self) -> None:
        played = self.player.play("t:1")
        self.assertTrue(played["favorite"])
        self.assertTrue(self.player.status()["favorite"])
        other = self.player.play("t:3")
        self.assertFalse(other["favorite"])

    def test_favorite_toggle_adds_and_removes(self) -> None:
        self.player.play("t:3")
        added = self.player.handle("favorite")
        self.assertTrue(added["favorite"])
        self.assertIn("3", self.player.tidal.favorite_ids)  # type: ignore[attr-defined]
        removed = self.player.handle("favorite")
        self.assertFalse(removed["favorite"])
        self.assertNotIn("3", self.player.tidal.favorite_ids)  # type: ignore[attr-defined]

    def test_handle_unknown_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown player method"):
            self.player.handle("explode")

    def test_remove_future_queue_item(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.player.enqueue("t:3")
        payload = self.player.handle("remove", {"index": 2})
        self.assertEqual([item["id"] for item in self.player.play_queue.items], ["1", "2"])
        self.assertEqual(payload["length"], 2)
        self.assertEqual(self.player.play_queue.index, 0)

    def test_remove_item_before_current_shifts_index(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.player.enqueue("t:3")
        self.player.handle("next")
        self.player.handle("remove", {"index": 0})
        self.assertEqual(self.player.play_queue.current()["id"], "2")
        self.assertEqual(self.player.play_queue.index, 0)

    def test_remove_current_track_stops_playback(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        payload = self.player.handle("remove", {"index": 0})
        self.assertEqual(payload["state"], "stopped")
        self.assertIsNone(self.mpv.loaded)
        self.assertEqual(payload["length"], 1)
        self.assertFalse(self.player._autoplay)
        self.assertFalse(self.paths.now_playing_file.exists())

    def test_remove_unknown_position_fails(self) -> None:
        self.player.play("t:1")
        with self.assertRaisesRegex(LookupError, "No queue item"):
            self.player.handle("remove", {"index": 5})

    def test_logout_stops_playback_and_clears_session(self) -> None:
        self.player.play("t:1")
        self.player.enqueue("t:2")
        self.player.handle("shuffle", {"enabled": True})
        self.paths.session_file.write_text("{}", encoding="utf-8")
        payload = self.player.handle("logout")
        self.assertEqual(payload["state"], "stopped")
        self.assertFalse(payload["logged_in"])
        self.assertFalse(self.player._alive)
        self.assertIsNone(self.mpv.loaded)
        self.assertEqual(len(self.player.play_queue.items), 0)
        self.assertFalse(self.player.shuffle_on)
        self.assertFalse(self.paths.now_playing_file.exists())
        self.assertTrue(self.player.tidal.logged_out)  # type: ignore[attr-defined]


class IpcTests(unittest.TestCase):
    def test_call_player_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "cache", root / "runtime")
            paths.prepare_private_dirs()
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(paths.player_socket))
            server.listen(1)

            def serve() -> None:
                connection, _ignored = server.accept()
                with connection:
                    connection.makefile("r", encoding="utf-8").readline()
                    connection.sendall(encode_response(1, result={"schema_version": 1, "state": "stopped"}))

            thread = threading.Thread(target=serve)
            thread.start()
            try:
                result = call_player(paths, "status", timeout=2)
                self.assertEqual(result["state"], "stopped")
            finally:
                thread.join(timeout=2)
                server.close()

    def test_call_player_surfaces_remote_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "cache", root / "runtime")
            paths.prepare_private_dirs()
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(paths.player_socket))
            server.listen(1)

            def serve() -> None:
                connection, _ignored = server.accept()
                with connection:
                    connection.makefile("r", encoding="utf-8").readline()
                    connection.sendall(encode_response(1, error="No TIDAL tracks found"))

            thread = threading.Thread(target=serve)
            thread.start()
            try:
                with self.assertRaisesRegex(PlayerError, "No TIDAL tracks"):
                    call_player(paths, "play", {"selector": "x"}, timeout=2)
            finally:
                thread.join(timeout=2)
                server.close()


if __name__ == "__main__":
    unittest.main()
