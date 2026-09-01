# TIDAL for Omarchy (design prototype)

An isolated prototype for a community-friendly TIDAL player and Omarchy Shell
integration. It does not install files, start services, read the credentials of,
or communicate with the existing `~/.local/bin/tidal` application.

## Current state

This repository is at an isolated local prototype stage:

- `otidal` is a new, non-conflicting command name.
- The Python package defines a stable JSON status contract.
- Login uses a dedicated `~/.config/otidal/session.json`; it never loads the
  credentials used by the existing personal CLI.
- Search, track resolution, DASH manifest handoff, and mpv JSON IPC are wired.
- Live account login and stream playback remain explicit manual test gates.
- `omarchy-plugin/` is a separately validatable Shell plugin prototype.
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

This is an unofficial personal integration built on `tidalapi`. It is not
affiliated with or endorsed by TIDAL, and its playback path is outside TIDAL's
documented third-party playback offering.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the proposed production shape and
[ROADMAP.md](ROADMAP.md) for the gated implementation sequence.
