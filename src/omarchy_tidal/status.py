from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


PlaybackState = Literal["playing", "paused", "stopped"]


@dataclass(frozen=True, slots=True)
class TrackStatus:
    id: str
    title: str
    artist: str
    album: str = ""
    artwork_url: str = ""
    quality: str = ""


@dataclass(frozen=True, slots=True)
class PlayerStatus:
    schema_version: int = 1
    available: bool = False
    state: PlaybackState = "stopped"
    track: TrackStatus | None = None
    position: float = 0.0
    duration: float = 0.0
    queue: list[TrackStatus] = field(default_factory=list)
    index: int = -1
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
