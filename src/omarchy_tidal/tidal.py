from __future__ import annotations

import json
import os
import re
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .paths import AppPaths


class LoginRequired(RuntimeError):
    pass


QUALITY_ORDER = ("HI_RES_LOSSLESS", "LOSSLESS", "HIGH", "LOW")
DEFAULT_QUALITY = "HI_RES_LOSSLESS"
BTS_MIME = "application/vnd.tidal.bts"
MPD_MIME = "application/dash+xml"


FAVORITE_SELECTORS = {"favs", "favorites", "liked"}
SELECTOR_PREFIXES = {
    "t:": "track",
    "a:": "album",
    "p:": "playlist",
    "r:": "artist",
}


@dataclass(frozen=True, slots=True)
class CatalogTrack:
    id: str
    title: str
    artist: str
    album: str
    duration: int
    artwork_url: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "artwork_url": self.artwork_url,
        }


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    kind: str
    id: str
    title: str
    artist: str = ""
    extra: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "extra": self.extra,
        }


def parse_selector(selector: str) -> tuple[str, str]:
    token = selector.strip()
    if not token:
        raise ValueError("selector required")
    lowered = token.lower()
    if lowered in FAVORITE_SELECTORS:
        return "favorites", ""
    for prefix, kind in SELECTOR_PREFIXES.items():
        if lowered.startswith(prefix):
            return kind, token[len(prefix) :]
    if token.isdigit():
        return "track", token
    return "search", token


@dataclass(frozen=True, slots=True)
class PlaybackSource:
    kind: Literal["url", "dash"]
    target: str
    quality: str
    bit_depth: int = 0
    sample_rate: int = 0

    def label(self) -> str:
        return format_quality_label(self.quality, self.bit_depth, self.sample_rate)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "quality": self.quality,
            "bit_depth": self.bit_depth,
            "sample_rate": self.sample_rate,
            "label": self.label(),
        }


def format_sample_rate(sample_rate: int) -> str:
    if sample_rate <= 0:
        return ""
    if sample_rate % 1000 == 0:
        return f"{sample_rate // 1000} kHz"
    return f"{sample_rate / 1000:.1f} kHz"


def format_quality_label(quality: str, bit_depth: int = 0, sample_rate: int = 0) -> str:
    names = {
        "HI_RES_LOSSLESS": "Hi-Res Lossless",
        "LOSSLESS": "Lossless",
        "HIGH": "High",
        "LOW": "Low",
    }
    name = names.get(quality, quality.replace("_", " ").title())
    if bit_depth > 0 and sample_rate > 0:
        return f"{name} {bit_depth}-bit / {format_sample_rate(sample_rate)}"
    if sample_rate > 0:
        return f"{name} {format_sample_rate(sample_rate)}"
    return name


def stream_resolution(stream: Any) -> tuple[int, int]:
    bit_depth = int(getattr(stream, "bit_depth", 0) or 0)
    sample_rate = int(getattr(stream, "sample_rate", 0) or 0)
    getter = getattr(stream, "get_audio_resolution", None)
    if callable(getter):
        try:
            depth, rate = getter()
            bit_depth = int(depth or bit_depth)
            sample_rate = int(rate or sample_rate)
        except Exception:
            pass
    try:
        data = stream.get_manifest_data()
    except Exception:
        data = ""
    if isinstance(data, str) and "<MPD" in data:
        match = re.search(r'audioSamplingRate="(\d+)"', data)
        if match:
            sample_rate = int(match.group(1))
        match = re.search(r'id="[^"]*,(\d+),(\d+)"', data)
        if match:
            sample_rate = int(match.group(1))
            bit_depth = int(match.group(2))
    return bit_depth, sample_rate


def normalize_quality_name(value: Any, fallback: str) -> str:
    raw = str(getattr(value, "value", value) or fallback).upper().replace("HIRES", "HI_RES")
    if "HI_RES" in raw:
        return "HI_RES_LOSSLESS"
    if "LOSSLESS" in raw:
        return "LOSSLESS"
    if raw in QUALITY_ORDER:
        return raw
    return fallback


def requested_quality() -> str:
    name = os.environ.get("OTIDAL_QUALITY", DEFAULT_QUALITY).upper()
    if name not in QUALITY_ORDER:
        raise ValueError(f"Unknown OTIDAL_QUALITY={name!r}")
    return name


def quality_fallback(wanted: str) -> tuple[str, ...]:
    if wanted not in QUALITY_ORDER:
        raise ValueError(f"Unknown OTIDAL_QUALITY={wanted!r}")
    return QUALITY_ORDER[QUALITY_ORDER.index(wanted) :]


def _quality_map() -> dict[str, Any]:
    from tidalapi import Quality

    return {
        "HI_RES_LOSSLESS": Quality.hi_res_lossless,
        "LOSSLESS": Quality.high_lossless,
        "HIGH": Quality.low_320k,
        "LOW": Quality.low_96k,
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


def _artwork_url(track: Any) -> str:
    album = getattr(track, "album", None)
    if album is not None:
        image = getattr(album, "image", None)
        if callable(image):
            try:
                return str(image(320))
            except Exception:
                pass
    image = getattr(track, "image", None)
    if callable(image):
        try:
            return str(image(480, 320))
        except Exception:
            return ""
    return ""


def _catalog_track(track: Any) -> CatalogTrack:
    album = getattr(track, "album", None)
    return CatalogTrack(
        id=str(track.id),
        title=str(getattr(track, "full_name", None) or track.name),
        artist=_track_artist(track),
        album=str(getattr(album, "name", "") or ""),
        duration=int(getattr(track, "duration", 0) or 0),
        artwork_url=_artwork_url(track),
    )


def _stream_is_bts(stream: Any) -> bool:
    mime = str(getattr(stream, "manifest_mime_type", "") or "")
    if getattr(stream, "is_bts", False):
        return True
    return BTS_MIME in mime


def _stream_is_mpd(stream: Any) -> bool:
    mime = str(getattr(stream, "manifest_mime_type", "") or "")
    if getattr(stream, "is_mpd", False):
        return True
    return MPD_MIME in mime


def first_playable_stream(track: Any, session: Any, wanted: str) -> tuple[Any, str]:
    qualities = _quality_map()
    last_error: Exception | None = None
    # get_stream() reads quality from the session attached to the track object,
    # not from a newly loaded Session. Mutate that session so fallback works.
    target = getattr(track, "session", None) or session
    for name in quality_fallback(wanted):
        target.audio_quality = qualities[name]
        if session is not None and session is not target:
            session.audio_quality = qualities[name]
        try:
            stream = track.get_stream()
            actual = normalize_quality_name(getattr(stream, "audio_quality", None), name)
            return stream, actual
        except Exception as error:  # tidalapi raises several stream errors
            last_error = error
    raise LookupError(f"No playable TIDAL stream: {last_error}")


def playback_source_from_stream(
    stream: Any,
    *,
    quality: str,
    track_id: str,
    paths: AppPaths,
) -> PlaybackSource:
    bit_depth, sample_rate = stream_resolution(stream)
    if _stream_is_bts(stream):
        payload = json.loads(stream.get_manifest_data())
        urls = payload.get("urls") or []
        if not urls:
            raise LookupError(f"BTS manifest for {track_id} has no URLs")
        return PlaybackSource(
            kind="url",
            target=str(urls[0]),
            quality=quality,
            bit_depth=bit_depth,
            sample_rate=sample_rate,
        )
    if _stream_is_mpd(stream):
        return PlaybackSource(
            kind="dash",
            target=str(_write_manifest_file(paths, track_id, stream.get_manifest_data())),
            quality=quality,
            bit_depth=bit_depth,
            sample_rate=sample_rate,
        )
    raise LookupError(
        f"Unknown TIDAL manifest type {getattr(stream, 'manifest_mime_type', None)!r}"
    )


def _write_manifest_file(paths: AppPaths, track_id: str, manifest: str) -> Path:
    paths.prepare_private_dirs()
    destination = paths.manifest_dir / f"{track_id}.mpd"
    temporary = destination.with_suffix(".mpd.tmp")
    temporary.write_text(manifest, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(destination)
    return destination


def normalize_redirect_url(redirect_url: str) -> str:
    """Accept the full 'Oops' page URL, a raw code, or a ?query fragment."""
    redirect = str(redirect_url).strip()
    if "://" in redirect:
        return redirect
    if redirect.startswith("?"):
        return "https://tidal.com/android/login/auth" + redirect
    return "https://tidal.com/android/login/auth?code=" + redirect


class TidalClient:
    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or AppPaths.from_environment()
        self._favorite_ids: set[str] | None = None

    @staticmethod
    def _new_session() -> Any:
        from tidalapi import Session

        session = Session()
        session.audio_quality = _quality_map()[requested_quality()]
        return session

    def login(self) -> None:
        self.paths.prepare_private_dirs()
        session = self._new_session()
        if not session.login_session_file(self.paths.session_file, do_pkce=True):
            raise LoginRequired("TIDAL login failed")
        self.paths.session_file.chmod(0o600)

    def _load_pending_login(self) -> dict[str, object] | None:
        try:
            payload = json.loads(self.paths.login_pending_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return None
        if not isinstance(payload, dict) or not str(payload.get("url") or ""):
            return None
        return payload

    def _save_pending_login(self, state: dict[str, object]) -> None:
        self.paths.prepare_private_dirs()
        destination = self.paths.login_pending_file
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(destination)

    def login_start(self, open_browser: bool = True) -> dict[str, object]:
        self.paths.prepare_private_dirs()
        if self.paths.session_file.is_file():
            try:
                self.session()
            except LoginRequired:
                self.paths.session_file.unlink(missing_ok=True)
            else:
                self.paths.login_pending_file.unlink(missing_ok=True)
                return {"state": "already_logged_in", "logged_in": True}
        pending = self._load_pending_login()
        if pending is not None:
            return {"state": "pending", "url": str(pending["url"])}
        session = self._new_session()
        url = session.pkce_login_url()
        self._save_pending_login(
            {
                "code_verifier": str(session.config.code_verifier),
                "client_unique_key": str(session.config.client_unique_key),
                "url": url,
            }
        )
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return {"state": "pending", "url": url}

    def login_finish(self, redirect_url: str) -> dict[str, object]:
        pending = self._load_pending_login()
        if pending is None:
            raise LookupError("No login in progress. Run: otidal login start")
        session = self._new_session()
        session.config.code_verifier = str(pending["code_verifier"])
        session.config.client_unique_key = str(
            pending.get("client_unique_key") or session.config.client_unique_key
        )
        try:
            token = session.pkce_get_auth_token(normalize_redirect_url(redirect_url))
            session.process_auth_token(token, is_pkce_token=True)
            session.save_session_to_file(self.paths.session_file)
        except Exception as error:
            # The code exchange is consumed; drop the pending state so the next
            # `login start` issues a fresh challenge.
            self.paths.login_pending_file.unlink(missing_ok=True)
            message = str(error)
            if getattr(error, "response", None) is not None:
                message = "TIDAL rejected the code (expired or wrong 'Oops' URL)"
            raise LoginRequired(f"TIDAL login failed: {message}") from error
        if not self.paths.session_file.is_file():
            self.paths.login_pending_file.unlink(missing_ok=True)
            raise LoginRequired("TIDAL login failed: session was not saved")
        self.paths.session_file.chmod(0o600)
        self.paths.login_pending_file.unlink(missing_ok=True)
        return {"state": "done", "logged_in": True}

    def logout(self) -> None:
        self.paths.session_file.unlink(missing_ok=True)
        self.paths.login_pending_file.unlink(missing_ok=True)

    def session(self) -> Any:
        if not self.paths.session_file.is_file():
            raise LoginRequired("Not logged in. Run: otidal login start")
        session = self._new_session()
        if not session.load_session_from_file(self.paths.session_file) or not session.check_login():
            raise LoginRequired("TIDAL session expired. Run: otidal login start")
        return session

    def search_tracks(self, query: str, limit: int = 10) -> list[CatalogTrack]:
        from tidalapi import Track

        result = self.session().search(query, models=[Track], limit=limit)
        return [_catalog_track(track) for track in (result.get("tracks") or [])]

    def search(
        self, query: str, limit: int = 15
    ) -> tuple[list[CatalogTrack], list[CatalogEntry], list[CatalogEntry], list[CatalogEntry]]:
        from tidalapi import Album, Artist, Playlist, Track

        result = self.session().search(
            query, models=[Track, Album, Playlist, Artist], limit=limit
        )
        tracks = [_catalog_track(track) for track in (result.get("tracks") or [])]
        albums = [
            CatalogEntry(
                "album",
                str(album.id),
                str(album.name),
                _track_artist(album),
                f"a:{album.id}",
            )
            for album in (result.get("albums") or [])[:5]
        ]
        playlists = [
            CatalogEntry(
                "playlist",
                str(playlist.id),
                str(playlist.name),
                _track_artist(playlist),
                f"p:{playlist.id}",
            )
            for playlist in (result.get("playlists") or [])[:5]
        ]
        artists = [
            CatalogEntry("artist", str(artist.id), str(artist.name), str(artist.name), f"r:{artist.id}")
            for artist in (result.get("artists") or [])[:3]
        ]
        return tracks, albums, playlists, artists

    def _favorites(self) -> Any:
        user = getattr(self.session(), "user", None)
        favorites = getattr(user, "favorites", None)
        if favorites is None:
            raise LookupError("Favorites are not available for this session")
        return favorites

    def favorite_tracks(self, limit: int = 50) -> list[CatalogTrack]:
        return [_catalog_track(track) for track in self._favorites().tracks(limit=limit)]

    def _favorite_id_set(self) -> set[str]:
        if self._favorite_ids is None:
            self._favorite_ids = {
                str(track.id) for track in self._favorites().tracks(limit=1000)
            }
        return self._favorite_ids

    def is_favorite_track(self, track_id: str) -> bool:
        return str(track_id) in self._favorite_id_set()

    def add_favorite_track(self, track_id: str) -> bool:
        if not bool(self._favorites().add_track(str(track_id))):
            return False
        self._favorite_id_set().add(str(track_id))
        return True

    def remove_favorite_track(self, track_id: str) -> bool:
        if not bool(self._favorites().remove_track(str(track_id))):
            return False
        self._favorite_id_set().discard(str(track_id))
        return True

    def album_tracks(self, album_id: str) -> list[CatalogTrack]:
        album = self.session().album(album_id)
        return [_catalog_track(track) for track in album.tracks()]

    def playlist_tracks(self, playlist_id: str) -> list[CatalogTrack]:
        playlist = self.session().playlist(playlist_id)
        return [_catalog_track(track) for track in playlist.tracks()]

    def artist_tracks(self, artist_id: str, limit: int = 20) -> list[CatalogTrack]:
        artist = self.session().artist(artist_id)
        return [_catalog_track(track) for track in artist.get_top_tracks(limit=limit)]

    def expand_tracks(self, selector: str, limit: int = 50) -> list[CatalogTrack]:
        kind, ident = parse_selector(selector)
        if kind == "favorites":
            return self.favorite_tracks(limit=limit)
        if kind == "track":
            _track, metadata = self.resolve_track(f"t:{ident}")
            return [metadata]
        if kind == "album":
            return self.album_tracks(ident)
        if kind == "playlist":
            return self.playlist_tracks(ident)
        if kind == "artist":
            return self.artist_tracks(ident)
        _track, metadata = self.resolve_track(ident)
        return [metadata]

    def radio_tracks(self, selector: str, limit: int = 30) -> list[CatalogTrack]:
        expanded = self.expand_tracks(selector, limit=1)
        if not expanded:
            raise LookupError("Need a track for radio")
        seed_id = expanded[0].id
        session = self.session()
        seed = session.track(seed_id)
        try:
            related = list(seed.get_track_radio(limit=limit))
        except Exception as error:
            raise LookupError(f"Track radio unavailable: {error}") from error
        tracks = [_catalog_track(seed)]
        seen = {seed_id}
        for track in related:
            item = _catalog_track(track)
            if item.id in seen:
                continue
            seen.add(item.id)
            tracks.append(item)
        return tracks

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

    def resolve_playback(self, track: Any, wanted: str | None = None) -> PlaybackSource:
        stream, quality = first_playable_stream(
            track, self.session(), wanted or requested_quality()
        )
        return playback_source_from_stream(
            stream,
            quality=quality,
            track_id=str(track.id),
            paths=self.paths,
        )
