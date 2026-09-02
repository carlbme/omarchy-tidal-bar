from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

from . import __version__
from .ipc import PlayerError
from .mpv import PlayerUnavailable
from .paths import AppPaths
from .player import request, run_daemon
from .status import PlayerStatus
from .tidal import LoginRequired, TidalClient, requested_quality


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def _mpris_available() -> bool:
    try:
        completed = subprocess.run(
            ["busctl", "--user", "status", "org.mpris.MediaPlayer2.otidal"],
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def cmd_status(args: argparse.Namespace) -> int:
    try:
        payload = request("status")
    except PlayerUnavailable as error:
        payload = PlayerStatus(error=str(error)).to_dict()
        payload["error"] = str(error)
    if args.json:
        _emit(payload)
        return 0
    track = payload.get("track") if isinstance(payload.get("track"), dict) else None
    state = str(payload.get("state") or "stopped")
    index = payload.get("index")
    length = len(payload.get("queue") or []) if isinstance(payload.get("queue"), list) else 0
    suffix = ""
    if track and isinstance(index, int) and index >= 0 and length:
        suffix = f"  [{index + 1}/{length}]"
    if track:
        print(f"{state}: {track.get('artist')} — {track.get('title')}{suffix}")
    else:
        print(f"{state}: nothing playing")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from importlib.util import find_spec

    paths = AppPaths.from_environment()
    player_running = False
    try:
        request("status")
        player_running = True
    except PlayerUnavailable:
        player_running = False
    report = {
        "schema_version": 1,
        "python": sys.version.split()[0],
        "mpv": shutil.which("mpv"),
        "tidalapi": find_spec("tidalapi") is not None,
        "session_file": str(paths.session_file),
        "logged_in": paths.session_file.is_file(),
        "quality": requested_quality(),
        "player_running": player_running,
        "mpris": _mpris_available(),
        "existing_tidal_isolated": True,
    }
    if args.json:
        _emit(report)
    else:
        print(f"Python: {report['python']}")
        print(f"mpv: {report['mpv'] or 'not found'}")
        print(f"tidalapi: {'available' if report['tidalapi'] else 'not found'}")
        print(f"Own session: {'present' if report['logged_in'] else 'not created'}")
        print(f"Quality: {report['quality']}")
        print(f"Player process: {'running' if player_running else 'not running'}")
        print(f"MPRIS: {'org.mpris.MediaPlayer2.otidal' if report['mpris'] else 'not exported'}")
        print("Existing tidal CLI: isolated")
    return 0


def cmd_login(_args: argparse.Namespace) -> int:
    TidalClient().login()
    print("Logged in. Credentials are stored only in otidal's config directory.")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    tracks, albums, playlists, artists = TidalClient().search(" ".join(args.query), limit=args.limit)
    payload = {
        "schema_version": 1,
        "tracks": [track.to_dict() for track in tracks],
        "albums": [entry.to_dict() for entry in albums],
        "playlists": [entry.to_dict() for entry in playlists],
        "artists": [entry.to_dict() for entry in artists],
    }
    if args.json:
        _emit(payload)
        return 0
    printed = 0
    for track in tracks:
        printed += 1
        print(f"{printed:3}  track     {track.artist} — {track.title}  [t:{track.id}]")
    for entry in albums + playlists + artists:
        printed += 1
        label = entry.title if entry.kind != "artist" else entry.artist
        print(f"{printed:3}  {entry.kind:<8}  {label}  [{entry.extra}]")
    if printed == 0:
        print("No results.")
    return 0


def cmd_favs(args: argparse.Namespace) -> int:
    tracks = TidalClient().favorite_tracks(limit=args.limit)
    payload = {"schema_version": 1, "tracks": [track.to_dict() for track in tracks]}
    if args.json:
        _emit(payload)
        return 0
    if not tracks:
        print("No favorite tracks.")
        return 0
    for index, track in enumerate(tracks, 1):
        print(f"{index:3}  {track.artist} — {track.title}  [t:{track.id}]")
    print("\nPlay with:  otidal play favs")
    return 0


def _print_play_result(payload: dict[str, object]) -> None:
    track = payload.get("track") if isinstance(payload.get("track"), dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    index = payload.get("index")
    length = payload.get("length")
    extra = ""
    if isinstance(index, int) and isinstance(length, int) and length:
        extra = f"  [{index + 1}/{length}]"
    quality = source.get("label") or source.get("quality")
    kind = source.get("kind")
    suffix = f" ({quality} {kind})" if quality and kind else ""
    print(f"Playing: {track.get('artist')} — {track.get('title')}{suffix}{extra}")


def cmd_play(args: argparse.Namespace) -> int:
    payload = request("play", {"selector": " ".join(args.selector)}, start=True)
    if args.json:
        _emit(payload)
    else:
        _print_play_result(payload)
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    payload = request("queue", {"selector": " ".join(args.selector)}, start=True)
    if args.json:
        _emit(payload)
        return 0
    added = int(payload.get("added") or 1)
    if payload.get("state") == "playing":
        _print_play_result(payload)
        if added > 1:
            print(f"Queued {added - 1} more.")
        return 0
    track = payload.get("track") if isinstance(payload.get("track"), dict) else {}
    if added == 1:
        print(
            f"Queued: {track.get('artist')} — {track.get('title')}  "
            f"[{payload.get('length')} in queue]"
        )
    else:
        print(f"Queued {added} tracks  [{payload.get('length')} in queue]")
    return 0


def cmd_radio(args: argparse.Namespace) -> int:
    payload = request("radio", {"selector": " ".join(args.selector)}, start=True)
    if args.json:
        _emit(payload)
        return 0
    _print_play_result(payload)
    added = payload.get("added")
    if isinstance(added, int) and added:
        print(f"Radio station ({added} tracks).")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    payload = request("next")
    if args.json:
        _emit(payload)
    elif payload.get("state") == "stopped":
        print("End of queue.")
    else:
        _print_play_result(payload)
    return 0


def cmd_jump(args: argparse.Namespace) -> int:
    if args.index < 1:
        raise ValueError("jump index must be 1 or greater")
    payload = request("jump", {"index": args.index - 1})
    if args.json:
        _emit(payload)
    else:
        _print_play_result(payload)
    return 0


def cmd_previous(args: argparse.Namespace) -> int:
    payload = request("previous")
    if args.json:
        _emit(payload)
    elif payload.get("state") == "stopped":
        print("Nothing in queue.")
    else:
        _print_play_result(payload)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    payload = request("stop")
    if args.json:
        _emit(payload)
    else:
        print("Stopped.")
    return 0


def cmd_toggle(args: argparse.Namespace) -> int:
    payload = request("toggle")
    if args.json:
        _emit(payload)
    else:
        print(f"{payload.get('state')}.")
    return 0


def cmd_quit(args: argparse.Namespace) -> int:
    try:
        payload = request("quit")
    except PlayerUnavailable:
        payload = {"schema_version": 1, "state": "stopped"}
    if args.json:
        _emit(payload)
    else:
        print("Player stopped.")
    return 0


def cmd_daemon(_args: argparse.Namespace) -> int:
    return run_daemon()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="otidal",
        description="Independent, unofficial TIDAL player for Omarchy.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    login = commands.add_parser("login", help="Create an isolated TIDAL PKCE session")
    login.set_defaults(func=cmd_login)

    search = commands.add_parser("search", help="Search tracks, albums, playlists, and artists")
    search.add_argument("query", nargs="+")
    search.add_argument("--limit", type=int, default=15)
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=cmd_search)

    favs = commands.add_parser("favs", aliases=["favorites"], help="List favorite tracks")
    favs.add_argument("--limit", type=int, default=50)
    favs.add_argument("--json", action="store_true")
    favs.set_defaults(func=cmd_favs)

    play = commands.add_parser("play", help="Replace the queue and play a selector")
    play.add_argument(
        "selector",
        nargs="+",
        help="search query, favs, or t:/a:/p:/r: plus an id",
    )
    play.add_argument("--json", action="store_true")
    play.set_defaults(func=cmd_play)

    queue = commands.add_parser("queue", help="Append a selector to the queue")
    queue.add_argument(
        "selector",
        nargs="+",
        help="search query, favs, or t:/a:/p:/r: plus an id",
    )
    queue.add_argument("--json", action="store_true")
    queue.set_defaults(func=cmd_queue)

    radio = commands.add_parser("radio", help="Play a replenishing station from a seed track")
    radio.add_argument("selector", nargs="+")
    radio.add_argument("--json", action="store_true")
    radio.set_defaults(func=cmd_radio)

    nxt = commands.add_parser("next", help="Skip to the next queued track")
    nxt.add_argument("--json", action="store_true")
    nxt.set_defaults(func=cmd_next)

    jump = commands.add_parser("jump", help="Play a specific queue position (1-based)")
    jump.add_argument("index", type=int)
    jump.add_argument("--json", action="store_true")
    jump.set_defaults(func=cmd_jump)

    prev = commands.add_parser("prev", aliases=["previous"], help="Restart or go to the previous track")
    prev.add_argument("--json", action="store_true")
    prev.set_defaults(func=cmd_previous)

    stop = commands.add_parser("stop", help="Stop playback")
    stop.add_argument("--json", action="store_true")
    stop.set_defaults(func=cmd_stop)

    toggle = commands.add_parser("toggle", help="Toggle pause/play")
    toggle.add_argument("--json", action="store_true")
    toggle.set_defaults(func=cmd_toggle)

    quit_cmd = commands.add_parser("quit", help="Stop playback and shut down the player process")
    quit_cmd.add_argument("--json", action="store_true")
    quit_cmd.set_defaults(func=cmd_quit)

    status = commands.add_parser("status", help="Show the versioned player state")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    doctor = commands.add_parser("doctor", help="Check prototype prerequisites")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    daemon = commands.add_parser("daemon", help="Run the persistent player process")
    daemon.set_defaults(func=cmd_daemon)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (LoginRequired, LookupError, PlayerUnavailable, PlayerError, ValueError) as error:
        if getattr(args, "json", False):
            _emit({"schema_version": 1, "error": str(error)})
        else:
            print(f"otidal: {error}", file=sys.stderr)
        return 1
