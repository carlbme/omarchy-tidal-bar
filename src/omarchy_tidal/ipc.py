from __future__ import annotations

import json
import socket
from typing import Any

from .mpv import PlayerUnavailable
from .paths import AppPaths


class PlayerError(RuntimeError):
    pass


def encode_request(request_id: int, method: str, params: dict[str, Any] | None = None) -> bytes:
    payload = {"id": request_id, "method": method, "params": params or {}}
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


def encode_response(request_id: int, result: Any = None, error: str | None = None) -> bytes:
    if error:
        payload = {"id": request_id, "ok": False, "error": error}
    else:
        payload = {"id": request_id, "ok": True, "result": result}
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


def decode_message(line: str) -> dict[str, Any]:
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise ValueError("player IPC message must be an object")
    return payload


def call_player(
    paths: AppPaths,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    if not paths.player_socket.exists():
        raise PlayerUnavailable("player is not running")
    payload = encode_request(1, method, params)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(str(paths.player_socket))
            connection.sendall(payload)
            reader = connection.makefile("r", encoding="utf-8")
            line = reader.readline()
            if not line:
                raise PlayerUnavailable("player returned no response")
            response = decode_message(line)
    except OSError as error:
        raise PlayerUnavailable("player is not running") from error
    if not response.get("ok"):
        raise PlayerError(str(response.get("error") or "player request failed"))
    result = response.get("result")
    if not isinstance(result, dict):
        raise PlayerUnavailable("player returned an invalid result")
    return result
