from __future__ import annotations

import re
from typing import Any, Callable

BUS_NAME = "org.mpris.MediaPlayer2.otidal"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"
IDENTITY = "otidal"

_PLAYBACK = {"playing": "Playing", "paused": "Paused", "stopped": "Stopped"}


def track_object_path(track_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", str(track_id))
    if not safe:
        return NO_TRACK
    if safe[0].isdigit():
        safe = "t" + safe
    return f"/org/mpris/MediaPlayer2/track/{safe}"


def metadata_from_status(status: dict[str, Any]) -> dict[str, Any]:
    track = status.get("track")
    if not isinstance(track, dict) or not track.get("id"):
        return {"mpris:trackid": NO_TRACK}
    length = int(float(status.get("duration") or 0.0) * 1_000_000)
    metadata: dict[str, Any] = {
        "mpris:trackid": track_object_path(str(track["id"])),
        "mpris:length": length,
        "xesam:title": str(track.get("title") or ""),
        "xesam:artist": [str(track.get("artist") or "")],
        "xesam:album": str(track.get("album") or ""),
    }
    art = str(track.get("artwork_url") or "")
    if art:
        metadata["mpris:artUrl"] = art
    return metadata


class MprisAdapter:
    def __init__(self, player: Any) -> None:
        self.player = player

    def _status(self) -> dict[str, Any]:
        return self.player.handle("status")

    def playback_status(self) -> str:
        return _PLAYBACK.get(str(self._status().get("state") or "stopped"), "Stopped")

    def metadata(self) -> dict[str, Any]:
        return metadata_from_status(self._status())

    def position_us(self) -> int:
        return int(float(self._status().get("position") or 0.0) * 1_000_000)

    def volume(self) -> float:
        value = self._status().get("volume")
        return float(value) if value is not None else 1.0

    def can_go_next(self) -> bool:
        status = self._status()
        queue = status.get("queue") if isinstance(status.get("queue"), list) else []
        index = int(status.get("index") if status.get("index") is not None else -1)
        return 0 <= index + 1 < len(queue)

    def can_go_previous(self) -> bool:
        status = self._status()
        index = int(status.get("index") if status.get("index") is not None else -1)
        return index > 0 or float(status.get("position") or 0.0) > 0.0

    def player_properties(self) -> dict[str, Any]:
        return {
            "PlaybackStatus": self.playback_status(),
            "LoopStatus": "None",
            "Rate": 1.0,
            "Shuffle": False,
            "Metadata": self.metadata(),
            "Volume": self.volume(),
            "Position": self.position_us(),
            "MinimumRate": 1.0,
            "MaximumRate": 1.0,
            "CanGoNext": self.can_go_next(),
            "CanGoPrevious": self.can_go_previous(),
            "CanPlay": True,
            "CanPause": True,
            "CanSeek": True,
            "CanControl": True,
        }

    def root_properties(self) -> dict[str, Any]:
        return {
            "CanQuit": True,
            "CanRaise": False,
            "HasTrackList": False,
            "Identity": IDENTITY,
            "DesktopEntry": "otidal",
            "SupportedUriSchemes": ["https", "http"],
            "SupportedMimeTypes": ["audio/flac", "audio/mpeg", "application/dash+xml"],
        }

    def next(self) -> None:
        self.player.handle("next")

    def previous(self) -> None:
        self.player.handle("previous")

    def pause(self) -> None:
        self.player.handle("pause")

    def play_pause(self) -> None:
        if str(self._status().get("state") or "stopped") == "stopped":
            self.player.handle("resume")
            return
        self.player.handle("toggle")

    def stop(self) -> None:
        self.player.handle("stop")

    def play(self) -> None:
        self.player.handle("resume")

    def seek(self, offset_us: int) -> None:
        self.player.handle("seek", {"seconds": offset_us / 1_000_000})

    def set_position(self, _track_id: str, position_us: int) -> None:
        self.player.handle("seek_to", {"seconds": max(0.0, position_us / 1_000_000)})

    def set_volume(self, volume: float) -> None:
        self.player.handle("set_volume", {"volume": volume})

    def quit(self) -> None:
        self.player.handle("quit")


def _dbus_metadata(metadata: dict[str, Any]) -> Any:
    import dbus

    converted: dict[str, Any] = {
        "mpris:trackid": dbus.ObjectPath(str(metadata.get("mpris:trackid") or NO_TRACK)),
    }
    if "mpris:length" in metadata:
        converted["mpris:length"] = dbus.Int64(int(metadata["mpris:length"]))
    if "xesam:title" in metadata:
        converted["xesam:title"] = dbus.String(str(metadata["xesam:title"]))
    if "xesam:album" in metadata:
        converted["xesam:album"] = dbus.String(str(metadata["xesam:album"]))
    if "xesam:artist" in metadata:
        converted["xesam:artist"] = dbus.Array(
            [str(item) for item in metadata["xesam:artist"]],
            signature="s",
        )
    if metadata.get("mpris:artUrl"):
        converted["mpris:artUrl"] = dbus.String(str(metadata["mpris:artUrl"]))
    return dbus.Dictionary(converted, signature="sv")


def _dbus_player_properties(properties: dict[str, Any]) -> Any:
    import dbus

    return dbus.Dictionary(
        {
            "PlaybackStatus": dbus.String(properties["PlaybackStatus"]),
            "LoopStatus": dbus.String(properties["LoopStatus"]),
            "Rate": dbus.Double(properties["Rate"]),
            "Shuffle": dbus.Boolean(bool(properties["Shuffle"])),
            "Metadata": _dbus_metadata(properties["Metadata"]),
            "Volume": dbus.Double(float(properties["Volume"])),
            "Position": dbus.Int64(int(properties["Position"])),
            "MinimumRate": dbus.Double(properties["MinimumRate"]),
            "MaximumRate": dbus.Double(properties["MaximumRate"]),
            "CanGoNext": dbus.Boolean(bool(properties["CanGoNext"])),
            "CanGoPrevious": dbus.Boolean(bool(properties["CanGoPrevious"])),
            "CanPlay": dbus.Boolean(True),
            "CanPause": dbus.Boolean(True),
            "CanSeek": dbus.Boolean(True),
            "CanControl": dbus.Boolean(True),
        },
        signature="sv",
    )


def _dbus_root_properties(properties: dict[str, Any]) -> Any:
    import dbus

    return dbus.Dictionary(
        {
            "CanQuit": dbus.Boolean(bool(properties["CanQuit"])),
            "CanRaise": dbus.Boolean(bool(properties["CanRaise"])),
            "HasTrackList": dbus.Boolean(bool(properties["HasTrackList"])),
            "Identity": dbus.String(str(properties["Identity"])),
            "DesktopEntry": dbus.String(str(properties["DesktopEntry"])),
            "SupportedUriSchemes": dbus.Array(list(properties["SupportedUriSchemes"]), signature="s"),
            "SupportedMimeTypes": dbus.Array(list(properties["SupportedMimeTypes"]), signature="s"),
        },
        signature="sv",
    )


def start_mpris(player: Any, on_started: Callable[[], None] | None = None) -> Any:
    import threading

    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName(
        BUS_NAME,
        bus,
        allow_replacement=True,
        replace_existing=True,
        do_not_queue=True,
    )
    adapter = MprisAdapter(player)
    emitter = _MprisObject(bus, adapter)
    player.add_listener(lambda: GLib.idle_add(emitter.emit_update))
    loop = GLib.MainLoop()
    loop._otidal_keep = (name, emitter, bus)  # noqa: SLF001 — keep BusName alive

    def run() -> None:
        if on_started is not None:
            GLib.idle_add(on_started)
        loop.run()

    thread = threading.Thread(target=run, name="otidal-mpris", daemon=True)
    thread.start()
    print(f"mpris: {BUS_NAME}", flush=True)
    return loop


class _MprisObject:
    def __new__(cls, bus: Any, adapter: MprisAdapter) -> Any:
        import dbus
        import dbus.service

        class Exported(dbus.service.Object):
            def __init__(self) -> None:
                dbus.service.Object.__init__(self, bus, OBJECT_PATH)
                self.adapter = adapter

            @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
            def Raise(self) -> None:
                return None

            @dbus.service.method(ROOT_IFACE, in_signature="", out_signature="")
            def Quit(self) -> None:
                self.adapter.quit()

            @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
            def Next(self) -> None:
                self.adapter.next()

            @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
            def Previous(self) -> None:
                self.adapter.previous()

            @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
            def Pause(self) -> None:
                self.adapter.pause()

            @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
            def PlayPause(self) -> None:
                self.adapter.play_pause()

            @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
            def Stop(self) -> None:
                self.adapter.stop()

            @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
            def Play(self) -> None:
                self.adapter.play()

            @dbus.service.method(PLAYER_IFACE, in_signature="x", out_signature="")
            def Seek(self, offset: int) -> None:
                self.adapter.seek(int(offset))
                self.Seeked(self.adapter.position_us())

            @dbus.service.method(PLAYER_IFACE, in_signature="ox", out_signature="")
            def SetPosition(self, track_id: str, position: int) -> None:
                self.adapter.set_position(str(track_id), int(position))
                self.Seeked(self.adapter.position_us())

            @dbus.service.method(PLAYER_IFACE, in_signature="s", out_signature="")
            def OpenUri(self, uri: str) -> None:
                return None

            @dbus.service.signal(PLAYER_IFACE, signature="x")
            def Seeked(self, position: int) -> None:
                return None

            @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss", out_signature="v")
            def Get(self, interface: str, name: str) -> Any:
                return self.GetAll(interface)[name]

            @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
            def GetAll(self, interface: str) -> dict[str, Any]:
                if interface == ROOT_IFACE:
                    return _dbus_root_properties(self.adapter.root_properties())
                if interface == PLAYER_IFACE:
                    return _dbus_player_properties(self.adapter.player_properties())
                return {}

            @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ssv", out_signature="")
            def Set(self, interface: str, name: str, value: Any) -> None:
                if interface == PLAYER_IFACE and name == "Volume":
                    self.adapter.set_volume(float(value))
                    self.emit_update()

            @dbus.service.signal(dbus.PROPERTIES_IFACE, signature="sa{sv}as")
            def PropertiesChanged(
                self, interface: str, changed: dict[str, Any], invalidated: list[str]
            ) -> None:
                return None

            def emit_update(self) -> bool:
                try:
                    self.PropertiesChanged(
                        PLAYER_IFACE,
                        _dbus_player_properties(self.adapter.player_properties()),
                        [],
                    )
                except Exception:
                    pass
                return False

        return Exported()
