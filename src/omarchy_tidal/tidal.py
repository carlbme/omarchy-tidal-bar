from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import AppPaths


class LoginRequired(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CatalogTrack:
    id: str
    title: str
    artist: str
    album: str
    duration: int

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
        }


def _track_artist(track: Any) -> str:
    artist = getattr(track, "artist", None)
    if artist and getattr(artist, "name", None):
        return str(artist.name)
    return ", ".join(
        str(item.name)
        for item in (getattr(track, "artists", None) or [])
        if getattr(item, "name", None)
    )


def _catalog_track(track: Any) -> CatalogTrack:
    album = getattr(track, "album", None)
    return CatalogTrack(
        id=str(track.id),
        title=str(getattr(track, "full_name", None) or track.name),
        artist=_track_artist(track),
        album=str(getattr(album, "name", "") or ""),
        duration=int(getattr(track, "duration", 0) or 0),
    )


class TidalClient:
    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or AppPaths.from_environment()

    @staticmethod
    def _new_session() -> Any:
        from tidalapi import Quality, Session

        session = Session()
        quality_name = os.environ.get("OTIDAL_QUALITY", "HI_RES_LOSSLESS").upper()
        qualities = {
            "HI_RES_LOSSLESS": Quality.hi_res_lossless,
            "LOSSLESS": Quality.high_lossless,
            "HIGH": Quality.low_320k,
            "LOW": Quality.low_96k,
        }
        if quality_name not in qualities:
            raise ValueError(f"Unknown OTIDAL_QUALITY={quality_name!r}")
        session.audio_quality = qualities[quality_name]
        return session

    def login(self) -> None:
        self.paths.prepare_private_dirs()
        session = self._new_session()
        if not session.login_session_file(self.paths.session_file, do_pkce=True):
            raise LoginRequired("TIDAL login failed")
        self.paths.session_file.chmod(0o600)

    def session(self) -> Any:
        if not self.paths.session_file.is_file():
            raise LoginRequired("Not logged in. Run: otidal login")
        session = self._new_session()
        if not session.load_session_from_file(self.paths.session_file) or not session.check_login():
            raise LoginRequired("TIDAL session expired. Run: otidal login")
        return session

    def search_tracks(self, query: str, limit: int = 10) -> list[CatalogTrack]:
        from tidalapi import Track

        result = self.session().search(query, models=[Track], limit=limit)
        return [_catalog_track(track) for track in (result.get("tracks") or [])]

    def resolve_track(self, selector: str) -> tuple[Any, CatalogTrack]:
        session = self.session()
        if selector.startswith("t:") or selector.isdigit():
            track_id = selector.removeprefix("t:")
            track = session.track(track_id)
        else:
            from tidalapi import Track

            result = session.search(selector, models=[Track], limit=1)
            tracks = result.get("tracks") or []
            if not tracks:
                raise LookupError(f"No TIDAL tracks found for {selector!r}")
            track = tracks[0]
        return track, _catalog_track(track)

    def write_manifest(self, track: Any) -> Path:
        self.paths.prepare_private_dirs()
        manifest = track.get_stream().get_manifest_data()
        destination = self.paths.manifest_dir / f"{track.id}.mpd"
        temporary = destination.with_suffix(".mpd.tmp")
        temporary.write_text(manifest, encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(destination)
        return destination

