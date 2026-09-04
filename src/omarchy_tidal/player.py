from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from .ipc import call_player, decode_message, encode_response
from .mpris import start_mpris
from .mpv import MpvController, PlayerUnavailable
from .paths import AppPaths
from .queue import PlayQueue
from .status import PlayerStatus, TrackStatus
from .tidal import CatalogTrack, LoginRequired, TidalClient

RADIO_REMAINING = 4
RADIO_FETCH = 20
QUEUE_CAP = 80


def _load_now_playing(paths: AppPaths) -> dict[str, object] | None:
    try:
        payload = json.loads(paths.now_playing_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "id" not in payload:
            return None
        return payload
    except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _save_now_playing(paths: AppPaths, track: dict[str, object]) -> None:
    paths.prepare_private_dirs()
    temporary = paths.now_playing_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(track), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(paths.now_playing_file)


class Player:
    def __init__(
        self,
        paths: AppPaths | None = None,
        tidal: TidalClient | None = None,
        mpv: MpvController | None = None,
    ) -> None:
        self.paths = paths or AppPaths.from_environment()
        self.tidal = tidal or TidalClient(self.paths)
        self.mpv = mpv or MpvController(self.paths)
        self.play_queue = PlayQueue()
        self.track: dict[str, object] | None = _load_now_playing(self.paths)
        self.radio_seed_id: str | None = None
        self.shuffle_on = False
        self.track_favorite = False
        self._autoplay = False
        self._alive = True
        self._lock = threading.RLock()
        self._listeners: list[Callable[[], None]] = []
        self._mpris_loop: Any = None

    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                continue

    def handle(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        with self._lock:
            result = self._dispatch(method, params)
        if method != "status":
            self._notify()
        return result

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "status":
            return self.status()
        if method == "play":
            return self.play(str(params.get("selector") or ""))
        if method == "queue":
            return self.enqueue(str(params.get("selector") or ""))
        if method == "radio":
            return self.radio(str(params.get("selector") or ""))
        if method == "next":
            return self.next_track()
        if method == "previous":
            return self.previous_track()
        if method == "jump":
            return self.jump(int(params.get("index") or 0))
        if method == "stop":
            return self.stop()
        if method == "toggle":
            return self.toggle()
        if method == "shuffle":
            enabled = params.get("enabled")
            if enabled is None:
                return self.set_shuffle()
            return self.set_shuffle(bool(enabled))
        if method == "favorite":
            enabled = params.get("enabled")
            if enabled is None:
                return self.set_favorite()
            return self.set_favorite(bool(enabled))
        if method == "pause":
            return self.pause()
        if method == "resume":
            return self.resume()
        if method == "seek":
            return self.seek_by(float(params.get("seconds") or 0.0))
        if method == "seek_to":
            return self.seek_to(float(params.get("seconds") or 0.0))
        if method == "set_volume":
            return self.set_volume(float(params.get("volume") or 0.0))
        if method == "quit":
            self._alive = False
            self._autoplay = False
            self.radio_seed_id = None
            self.mpv.quit()
            if self._mpris_loop is not None:
                try:
                    self._mpris_loop.quit()
                except Exception:
                    pass
            return {"schema_version": 1, "state": "stopped"}
        raise ValueError(f"Unknown player method {method!r}")

    def status(self) -> dict[str, Any]:
        raw = self.mpv.status()
        state = raw["state"]
        track_payload = None if state == "stopped" else (self.track or _load_now_playing(self.paths))
        track = None
        if isinstance(track_payload, dict):
            try:
                track = TrackStatus(
                    id=str(track_payload["id"]),
                    title=str(track_payload.get("title") or ""),
                    artist=str(track_payload.get("artist") or ""),
                    album=str(track_payload.get("album") or ""),
                    artwork_url=str(track_payload.get("artwork_url") or ""),
                    quality=str(track_payload.get("quality") or ""),
                )
            except KeyError:
                track = None
        queue_tracks: list[TrackStatus] = []
        for item in self.play_queue.items:
            try:
                queue_tracks.append(
                    TrackStatus(
                        id=str(item["id"]),
                        title=str(item.get("title") or ""),
                        artist=str(item.get("artist") or ""),
                        album=str(item.get("album") or ""),
                        artwork_url=str(item.get("artwork_url") or ""),
                        quality=str(item.get("quality") or ""),
                    )
                )
            except KeyError:
                continue
        status = PlayerStatus(
            available=True,
            state=state,
            track=track,
            position=float(raw["position"]),
            duration=float(raw["duration"]),
            queue=queue_tracks,
            index=self.play_queue.index,
            error=None,
        )
        payload = status.to_dict()
        payload["radio"] = self.radio_seed_id is not None
        payload["shuffle"] = self.shuffle_on
        payload["favorite"] = self.track_favorite
        payload["volume"] = float(raw.get("volume") if raw.get("volume") is not None else 1.0)
        return payload

    def play(self, selector: str) -> dict[str, Any]:
        self.radio_seed_id = None
        items = self._items_from_selector(selector)
        self.play_queue.items = items
        self.play_queue.index = 0
        result = self._play_index(0)
        self._shuffle_if_enabled()
        return result

    def enqueue(self, selector: str) -> dict[str, Any]:
        items = self._items_from_selector(selector)
        was_empty = not self.play_queue.items
        for item in items:
            self.play_queue.append(item)
        playing = False
        try:
            playing = self.mpv.status()["state"] in {"playing", "paused"}
        except PlayerUnavailable:
            playing = False
        if was_empty and not playing:
            result = self._play_index(0)
            self._shuffle_if_enabled()
            result["added"] = len(items)
            return result
        self._shuffle_if_enabled()
        return {
            "schema_version": 1,
            "state": "queued",
            "track": items[-1],
            "added": len(items),
            "index": self.play_queue.index,
            "length": len(self.play_queue.items),
            "shuffle": self.shuffle_on,
        }

    def radio(self, selector: str) -> dict[str, Any]:
        tracks = self.tidal.radio_tracks(selector)
        if not tracks:
            raise LookupError(f"No radio tracks for {selector!r}")
        self.play_queue.items = [self._payload(track) for track in tracks]
        self.play_queue.index = 0
        self.radio_seed_id = str(tracks[0].id)
        result = self._play_index(0)
        self._shuffle_if_enabled()
        result["radio"] = True
        result["added"] = len(self.play_queue.items)
        return result

    def set_shuffle(self, enabled: bool | None = None) -> dict[str, Any]:
        self.shuffle_on = (not self.shuffle_on) if enabled is None else bool(enabled)
        if self.shuffle_on:
            self.play_queue.shuffle_remaining()
        return self.status()

    def set_favorite(self, enabled: bool | None = None) -> dict[str, Any]:
        track_id = str((self.track or {}).get("id") or "")
        if not track_id:
            raise LookupError("nothing playing")
        want = (not self.track_favorite) if enabled is None else bool(enabled)
        if want:
            if not self.tidal.add_favorite_track(track_id):
                raise LookupError("could not add favorite")
            self.track_favorite = True
        else:
            if not self.tidal.remove_favorite_track(track_id):
                raise LookupError("could not remove favorite")
            self.track_favorite = False
        return self.status()

    def next_track(self) -> dict[str, Any]:
        nxt = self.play_queue.next_index()
        if nxt is None:
            return self.stop()
        return self._play_index(nxt)

    def jump(self, index: int) -> dict[str, Any]:
        return self._play_index(index)

    def previous_track(self) -> dict[str, Any]:
        try:
            position = float(self.mpv.status()["position"])
        except (PlayerUnavailable, KeyError, TypeError):
            position = 0.0
        if position > 3.0 and self.play_queue.index >= 0:
            try:
                self.mpv.seek(0.0)
            except PlayerUnavailable:
                pass
            return self.status() | {"schema_version": 1, "state": "playing"}
        prev = self.play_queue.previous_index()
        if prev is None:
            if self.play_queue.current() is None:
                raise LookupError("queue is empty")
            return self._play_index(self.play_queue.index)
        return self._play_index(prev)

    def stop(self) -> dict[str, Any]:
        self._autoplay = False
        self.track_favorite = False
        try:
            self.mpv.stop()
        except PlayerUnavailable:
            pass
        return {"schema_version": 1, "state": "stopped", "favorite": False}

    def toggle(self) -> dict[str, Any]:
        self.mpv.toggle_pause()
        return {"schema_version": 1, "state": self.mpv.status()["state"]}

    def pause(self) -> dict[str, Any]:
        if self.mpv.status()["state"] == "playing":
            self.mpv.toggle_pause()
        return {"schema_version": 1, "state": self.mpv.status()["state"]}

    def resume(self) -> dict[str, Any]:
        state = self.mpv.status()["state"]
        if state == "paused":
            self.mpv.toggle_pause()
            return {"schema_version": 1, "state": self.mpv.status()["state"]}
        if self.play_queue.current() is not None:
            return self._play_index(self.play_queue.index)
        return self.status()

    def seek_by(self, seconds: float) -> dict[str, Any]:
        position = float(self.mpv.status()["position"]) + seconds
        self.mpv.seek(max(0.0, position))
        return self.status()

    def seek_to(self, seconds: float) -> dict[str, Any]:
        self.mpv.seek(max(0.0, seconds))
        return self.status()

    def set_volume(self, volume: float) -> dict[str, Any]:
        self.mpv.set_volume(max(0.0, min(1.0, volume)))
        return self.status()

    def serve_forever(self) -> None:
        self.paths.prepare_private_dirs()
        socket_path = self.paths.player_socket
        if socket_path.exists():
            try:
                call_player(self.paths, "status", timeout=0.4)
            except PlayerUnavailable:
                socket_path.unlink(missing_ok=True)
            else:
                raise PlayerUnavailable("player is already running")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        server.listen(8)
        server.settimeout(0.5)
        try:
            self._mpris_loop = start_mpris(self)
        except Exception as error:
            print(f"mpris unavailable: {error}", flush=True)
        try:
            while self._alive:
                try:
                    connection, _ignored = server.accept()
                except TimeoutError:
                    self._maybe_auto_advance()
                    continue
                with connection:
                    self._serve_connection(connection)
        finally:
            if self._mpris_loop is not None:
                try:
                    self._mpris_loop.quit()
                except Exception:
                    pass
            server.close()
            socket_path.unlink(missing_ok=True)

    def _serve_connection(self, connection: socket.socket) -> None:
        try:
            reader = connection.makefile("r", encoding="utf-8")
            line = reader.readline()
            if not line:
                return
            message = decode_message(line)
            request_id = int(message.get("id") or 0)
            method = str(message.get("method") or "")
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            try:
                result = self.handle(method, params)
            except (LoginRequired, LookupError, PlayerUnavailable, ValueError) as error:
                connection.sendall(encode_response(request_id, error=str(error)))
                return
            connection.sendall(encode_response(request_id, result=result))
        except (OSError, ValueError, json.JSONDecodeError):
            return

    def _payload(self, track: CatalogTrack) -> dict[str, object]:
        return track.to_dict()

    def _items_from_selector(self, selector: str) -> list[dict[str, object]]:
        tracks = self.tidal.expand_tracks(selector)
        if not tracks:
            raise LookupError(f"Nothing to play for {selector!r}")
        return [self._payload(track) for track in tracks]

    def _play_index(self, index: int) -> dict[str, Any]:
        if index < 0 or index >= len(self.play_queue.items):
            return self.stop()
        self.play_queue.index = index
        item = self.play_queue.items[index]
        track, metadata = self.tidal.resolve_track(f"t:{item['id']}")
        source = self.tidal.resolve_playback(track)
        self.mpv.load(source.target, f"{metadata.artist} — {metadata.title}")
        payload = metadata.to_dict()
        if not payload.get("artwork_url"):
            payload["artwork_url"] = str(item.get("artwork_url") or "")
        payload["quality"] = source.label()
        payload["bit_depth"] = source.bit_depth
        payload["sample_rate"] = source.sample_rate
        self.play_queue.items[index] = payload
        self.track = payload
        self._autoplay = True
        _save_now_playing(self.paths, payload)
        self._refresh_favorite(str(payload["id"]))
        self._maybe_replenish_radio()
        return {
            "schema_version": 1,
            "state": "playing",
            "track": payload,
            "source": source.to_dict(),
            "index": index,
            "length": len(self.play_queue.items),
            "favorite": self.track_favorite,
        }

    def _maybe_auto_advance(self) -> None:
        with self._lock:
            changed = self._auto_advance_locked()
        if changed:
            self._notify()

    def _auto_advance_locked(self) -> bool:
        if not self._autoplay:
            return False
        try:
            state = self.mpv.status()["state"]
        except PlayerUnavailable:
            return False
        if state != "stopped":
            return False
        nxt = self.play_queue.next_index()
        while nxt is not None:
            try:
                self._play_index(nxt)
                return True
            except (LoginRequired, LookupError, PlayerUnavailable, ValueError):
                nxt += 1
                if nxt >= len(self.play_queue.items):
                    break
        self._autoplay = False
        self.track = None
        return False

    def _maybe_replenish_radio(self) -> None:
        if not self.radio_seed_id:
            return
        remaining = len(self.play_queue.items) - self.play_queue.index - 1
        if remaining >= RADIO_REMAINING:
            return
        seed_id = str((self.play_queue.current() or {}).get("id") or self.radio_seed_id)
        try:
            more = self.tidal.radio_tracks(f"t:{seed_id}", limit=RADIO_FETCH)
        except (LoginRequired, LookupError, ValueError):
            return
        known = {str(item.get("id")) for item in self.play_queue.items}
        added = False
        for track in more:
            if track.id in known:
                continue
            self.play_queue.append(self._payload(track))
            known.add(track.id)
            added = True
            if len(self.play_queue.items) >= QUEUE_CAP:
                break
        if added:
            self._shuffle_if_enabled()

    def _shuffle_if_enabled(self) -> None:
        if self.shuffle_on:
            self.play_queue.shuffle_remaining()

    def _refresh_favorite(self, track_id: str) -> None:
        try:
            self.track_favorite = bool(self.tidal.is_favorite_track(track_id))
        except (LoginRequired, LookupError, TypeError, ValueError):
            self.track_favorite = False


def spawn_player(paths: AppPaths, timeout: float = 5.0) -> None:
    paths.prepare_private_dirs()
    log_file = paths.runtime_dir / "player.log"
    with log_file.open("ab") as log:
        subprocess.Popen(
            [sys.executable, "-m", "omarchy_tidal", "daemon"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=os.environ.copy(),
        )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            call_player(paths, "status", timeout=0.4)
            return
        except PlayerUnavailable:
            time.sleep(0.05)
    raise PlayerUnavailable("player process did not start")


def request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    start: bool = False,
    timeout: float = 20.0,
    paths: AppPaths | None = None,
) -> dict[str, Any]:
    paths = paths or AppPaths.from_environment()
    try:
        return call_player(paths, method, params, timeout=timeout)
    except PlayerUnavailable:
        if not start:
            raise
        if paths.player_socket.exists():
            try:
                call_player(paths, "status", timeout=0.3)
            except PlayerUnavailable:
                paths.player_socket.unlink(missing_ok=True)
        spawn_player(paths)
        return call_player(paths, method, params, timeout=timeout)


def run_daemon() -> int:
    Player().serve_forever()
    return 0
