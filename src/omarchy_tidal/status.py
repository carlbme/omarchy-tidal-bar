from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


PlaybackState = Literal["playing", "paused", "stopped"]


@dataclass(frozen=True, slots=True)
class TrackStatus:
    id: str
    title: str
    artist: str
    album: str = ""
    artwork_url: str = ""


@dataclass(frozen=True, slots=True)
class PlayerStatus:
    schema_version: int = 1
    available: bool = False
    state: PlaybackState = "stopped"
    track: TrackStatus | None = None
    position: float = 0.0
    duration: float = 0.0
    error: str | None = "playback backend is not implemented"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
