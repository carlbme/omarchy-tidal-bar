from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from omarchy_tidal.paths import AppPaths
from omarchy_tidal.tidal import (
    DEFAULT_QUALITY,
    _artwork_url,
    first_playable_stream,
    format_quality_label,
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


if __name__ == "__main__":
    unittest.main()
