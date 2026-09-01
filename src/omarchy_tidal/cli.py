from __future__ import annotations

import argparse
import json
import shutil
import sys

from . import __version__
from .mpv import MpvController, PlayerUnavailable
from .paths import AppPaths
from .status import PlayerStatus, TrackStatus
from .tidal import LoginRequired, TidalClient


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def _save_now_playing(paths: AppPaths, track: dict[str, object]) -> None:
    paths.prepare_private_dirs()
    temporary = paths.now_playing_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(track), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(paths.now_playing_file)


def _load_now_playing(paths: AppPaths) -> TrackStatus | None:
    try:
        payload = json.loads(paths.now_playing_file.read_text(encoding="utf-8"))
        return TrackStatus(
            id=str(payload["id"]),
            title=str(payload["title"]),
            artist=str(payload["artist"]),
            album=str(payload.get("album", "")),
            artwork_url=str(payload.get("artwork_url", "")),
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def cmd_status(args: argparse.Namespace) -> int:
    paths = AppPaths.from_environment()
    raw = MpvController(paths).status()
    status = PlayerStatus(
        available=bool(raw["available"]),
        state=raw["state"],
        track=_load_now_playing(paths) if raw["state"] != "stopped" else None,
        position=float(raw["position"]),
        duration=float(raw["duration"]),
        error=None if raw["available"] else "player is not running",
    )
    if args.json:
        _emit(status.to_dict())
    elif status.track:
        print(f"{status.state}: {status.track.artist} — {status.track.title}")
    else:
        print(f"{status.state}: nothing playing")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from importlib.util import find_spec

    paths = AppPaths.from_environment()
    report = {
        "schema_version": 1,
        "python": sys.version.split()[0],
        "mpv": shutil.which("mpv"),
        "tidalapi": find_spec("tidalapi") is not None,
        "session_file": str(paths.session_file),
        "logged_in": paths.session_file.is_file(),
        "existing_tidal_isolated": True,
    }
    if args.json:
        _emit(report)
    else:
        print(f"Python: {report['python']}")
        print(f"mpv: {report['mpv'] or 'not found'}")
        print(f"tidalapi: {'available' if report['tidalapi'] else 'not found'}")
        print(f"Own session: {'present' if report['logged_in'] else 'not created'}")
        print("Existing tidal CLI: isolated")
    return 0


def cmd_login(_args: argparse.Namespace) -> int:
    TidalClient().login()
    print("Logged in. Credentials are stored only in otidal's config directory.")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    tracks = TidalClient().search_tracks(" ".join(args.query), limit=args.limit)
    payload = {"schema_version": 1, "tracks": [track.to_dict() for track in tracks]}
    if args.json:
        _emit(payload)
    else:
        for index, track in enumerate(tracks, 1):
            print(f"{index:3}  {track.artist} — {track.title}  [t:{track.id}]")
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    client = TidalClient()
    track, metadata = client.resolve_track(" ".join(args.selector))
    manifest = client.write_manifest(track)
    MpvController(client.paths).load(manifest, f"{metadata.artist} — {metadata.title}")
    track_payload = metadata.to_dict()
    track_payload["artwork_url"] = ""
    _save_now_playing(client.paths, track_payload)
    payload = {"schema_version": 1, "state": "playing", "track": track_payload}
    if args.json:
        _emit(payload)
    else:
        print(f"Playing: {metadata.artist} — {metadata.title}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    MpvController().stop()
    if args.json:
        _emit({"schema_version": 1, "state": "stopped"})
    else:
        print("Stopped.")
    return 0


def cmd_toggle(args: argparse.Namespace) -> int:
    player = MpvController()
    player.toggle_pause()
    state = player.status()["state"]
    if args.json:
        _emit({"schema_version": 1, "state": state})
    else:
        print(f"{state}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="otidal",
        description="Independent, unofficial TIDAL player for Omarchy.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    login = commands.add_parser("login", help="Create an isolated TIDAL PKCE session")
    login.set_defaults(func=cmd_login)

    search = commands.add_parser("search", help="Search for tracks")
    search.add_argument("query", nargs="+")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=cmd_search)

    play = commands.add_parser("play", help="Resolve and play a track with mpv")
    play.add_argument("selector", nargs="+", help="search query, numeric ID, or t:ID")
    play.add_argument("--json", action="store_true")
    play.set_defaults(func=cmd_play)

    stop = commands.add_parser("stop", help="Stop playback")
    stop.add_argument("--json", action="store_true")
    stop.set_defaults(func=cmd_stop)

    toggle = commands.add_parser("toggle", help="Toggle pause/play")
    toggle.add_argument("--json", action="store_true")
    toggle.set_defaults(func=cmd_toggle)

    status = commands.add_parser("status", help="Show the versioned player state")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    doctor = commands.add_parser("doctor", help="Check prototype prerequisites")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (LoginRequired, LookupError, PlayerUnavailable, ValueError) as error:
        if getattr(args, "json", False):
            _emit({"schema_version": 1, "error": str(error)})
        else:
            print(f"otidal: {error}", file=sys.stderr)
        return 1
