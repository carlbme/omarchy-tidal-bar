from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _xdg(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name)
    return Path(value).expanduser() if value else fallback


@dataclass(frozen=True, slots=True)
class AppPaths:
    config_dir: Path
    cache_dir: Path
    runtime_dir: Path

    @classmethod
    def from_environment(cls) -> "AppPaths":
        home = Path.home()
        runtime_base = _xdg("XDG_RUNTIME_DIR", Path("/tmp") / f"otidal-{os.getuid()}")
        return cls(
            config_dir=_xdg("XDG_CONFIG_HOME", home / ".config") / "otidal",
            cache_dir=_xdg("XDG_CACHE_HOME", home / ".cache") / "otidal",
            runtime_dir=runtime_base / "otidal",
        )

    @property
    def session_file(self) -> Path:
        return self.config_dir / "session.json"

    @property
    def mpv_socket(self) -> Path:
        return self.runtime_dir / "mpv.sock"

    @property
    def manifest_dir(self) -> Path:
        return self.cache_dir / "manifests"

    @property
    def now_playing_file(self) -> Path:
        return self.runtime_dir / "now-playing.json"

    def prepare_private_dirs(self) -> None:
        for directory in (self.config_dir, self.cache_dir, self.runtime_dir, self.manifest_dir):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory.chmod(0o700)
