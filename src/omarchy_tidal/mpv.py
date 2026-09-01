from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from .paths import AppPaths


class PlayerUnavailable(RuntimeError):
    pass


class MpvController:
    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or AppPaths.from_environment()
        self._request_id = 0

    def is_running(self) -> bool:
        if not self.paths.mpv_socket.exists():
            return False
        try:
            self.command(["get_property", "idle-active"])
            return True
        except (OSError, PlayerUnavailable):
            return False

    def start(self, timeout: float = 5.0) -> None:
        if self.is_running():
            return
        mpv = shutil.which("mpv")
        if not mpv:
            raise PlayerUnavailable("mpv is not installed")
        self.paths.prepare_private_dirs()
        self.paths.mpv_socket.unlink(missing_ok=True)
        subprocess.Popen(
            [
                mpv,
                "--idle=yes",
                "--no-terminal",
                "--no-video",
                "--audio-display=no",
                "--input-ipc-server=" + str(self.paths.mpv_socket),
                "--script-opts=osc-visibility=never",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.paths.mpv_socket.exists():
                try:
                    self.command(["get_property", "idle-active"])
                    return
                except (OSError, PlayerUnavailable):
                    pass
            time.sleep(0.05)
        raise PlayerUnavailable("mpv did not create its IPC socket")

    def command(self, command: list[Any]) -> Any:
        self._request_id += 1
        request_id = self._request_id
        payload = json.dumps({"command": command, "request_id": request_id}) + "\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(2)
                connection.connect(str(self.paths.mpv_socket))
                connection.sendall(payload.encode())
                reader = connection.makefile("r", encoding="utf-8")
                for line in reader:
                    response = json.loads(line)
                    if response.get("request_id") != request_id:
                        continue
                    if response.get("error") != "success":
                        raise PlayerUnavailable(str(response.get("error")))
                    return response.get("data")
        except OSError as error:
            raise PlayerUnavailable("player is not running") from error
        raise PlayerUnavailable("mpv returned no response")

    def load(self, manifest: Path, title: str) -> None:
        self.start()
        self.command(["loadfile", str(manifest), "replace"])
        self.command(["set_property", "media-title", title])

    def stop(self) -> None:
        self.command(["stop"])

    def toggle_pause(self) -> None:
        paused = bool(self.command(["get_property", "pause"]))
        self.command(["set_property", "pause", not paused])

    def status(self) -> dict[str, Any]:
        if not self.is_running():
            return {"available": False, "state": "stopped", "title": "", "position": 0.0, "duration": 0.0}
        idle = bool(self.command(["get_property", "idle-active"]))
        paused = bool(self.command(["get_property", "pause"]))
        return {
            "available": True,
            "state": "stopped" if idle else ("paused" if paused else "playing"),
            "title": self._property("media-title", ""),
            "position": float(self._property("time-pos", 0.0) or 0.0),
            "duration": float(self._property("duration", 0.0) or 0.0),
        }

    def _property(self, name: str, default: Any) -> Any:
        try:
            return self.command(["get_property", name])
        except PlayerUnavailable:
            return default
