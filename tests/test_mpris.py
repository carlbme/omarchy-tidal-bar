from __future__ import annotations

import unittest

from omarchy_tidal.mpris import (
    BUS_NAME,
    IDENTITY,
    MprisAdapter,
    metadata_from_status,
    track_object_path,
)


class FakePlayer:
    def __init__(self) -> None:
        self.state: dict[str, object] = {
            "schema_version": 1,
            "available": True,
            "state": "playing",
            "track": {
                "id": "56299935",
                "title": "Coma White",
                "artist": "Marilyn Manson",
                "album": "Mechanical Animals",
                "artwork_url": "https://img.example/cover.jpg",
            },
            "position": 12.5,
            "duration": 338.0,
            "queue": [{"id": "56299935"}, {"id": "2"}],
            "index": 0,
            "volume": 0.4,
        }
        self.calls: list[tuple[str, dict[str, object]]] = []

    def handle(self, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append((method, params or {}))
        if method == "status":
            return self.state
        return {"schema_version": 1, "state": str(self.state["state"])}


class MprisAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.player = FakePlayer()
        self.adapter = MprisAdapter(self.player)

    def test_bus_identity(self) -> None:
        self.assertEqual(BUS_NAME, "org.mpris.MediaPlayer2.otidal")
        self.assertEqual(self.adapter.root_properties()["Identity"], IDENTITY)

    def test_numeric_track_path_is_valid_object_path(self) -> None:
        path = track_object_path("56299935")
        self.assertTrue(path.startswith("/"))
        self.assertNotRegex(path.split("/")[-1], r"^[0-9]")

    def test_metadata_and_status(self) -> None:
        metadata = self.adapter.metadata()
        self.assertEqual(metadata["xesam:title"], "Coma White")
        self.assertEqual(metadata["xesam:artist"], ["Marilyn Manson"])
        self.assertEqual(metadata["mpris:artUrl"], "https://img.example/cover.jpg")
        self.assertEqual(metadata["mpris:length"], 338_000_000)
        self.assertEqual(self.adapter.playback_status(), "Playing")
        self.assertTrue(self.adapter.can_go_next())
        self.assertTrue(self.adapter.can_go_previous())

    def test_stopped_metadata_uses_no_track(self) -> None:
        self.player.state["state"] = "stopped"
        self.player.state["track"] = None
        metadata = metadata_from_status(self.player.state)
        self.assertIn("NoTrack", str(metadata["mpris:trackid"]))

    def test_play_pause_toggles_while_playing(self) -> None:
        self.adapter.play_pause()
        self.assertEqual(self.player.calls[-1][0], "toggle")

    def test_play_pause_resumes_when_stopped(self) -> None:
        self.player.state["state"] = "stopped"
        self.adapter.play_pause()
        self.assertEqual(self.player.calls[-1][0], "resume")


if __name__ == "__main__":
    unittest.main()
