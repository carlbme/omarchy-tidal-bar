# omarchy-tidal-bar

An isolated prototype for a local, unofficial TIDAL player with an optional
Omarchy Shell integration. It does not install files, start services, read the
credentials of, or communicate with the existing `~/.local/bin/tidal`
application.

## Current state

This repository is at an isolated local prototype stage:

- `otidal` is a new, non-conflicting command name.
- The Python package defines a stable JSON status contract.
- Login uses a dedicated `~/.config/otidal/session.json`; it never loads the
  credentials used by the existing personal CLI.
- Search, track resolution, BTS/DASH stream handoff, and mpv JSON IPC are wired.
- Default quality is HI_RES_LOSSLESS, falling back to LOSSLESS/HIGH/LOW.
- Live account login and LOSSLESS DASH playback of a real track have been
  proven in `.dev/` (Marilyn Manson — Coma White).
- `play` auto-starts `otidal daemon`, which owns mpv over `player.sock`.
- `omarchy-plugin/` is a frozen, separately validatable Shell plugin sketch.
  It is not installed and is not the integration to grow next.
- Queue, mixed search, favorites, album/artist/playlist expand,
  replenishing radio, and MPRIS (`org.mpris.MediaPlayer2.otidal`) are in
  the player process. The Omarchy bar plugin can be installed locally
  with `scripts/otidal-plugin-install` and removed with
  `scripts/otidal-plugin-rollback`. Packaging is not implemented.
- No installer or systemd unit exists yet.

Run the safe scaffold locally:

```bash
PYTHONPATH=src python -m omarchy_tidal --help
PYTHONPATH=src python -m omarchy_tidal status --json
PYTHONPATH=src python -m unittest discover -s tests
omarchy plugin validate ./omarchy-plugin
```

For live development without touching any existing TIDAL state, use
[`scripts/otidal-dev`](scripts/otidal-dev) as described in
[`DEVELOPMENT.md`](DEVELOPMENT.md).

This is an unofficial personal community project, not affiliated with TIDAL.

Playback uses the unofficial `tidalapi` package; that path is outside TIDAL's
documented third-party playback offering.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the proposed production shape and
[ROADMAP.md](ROADMAP.md) for the gated implementation sequence.
