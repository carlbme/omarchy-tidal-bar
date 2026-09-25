# omarchy-tidal-bar

An isolated, unofficial TIDAL player with an optional Omarchy Shell bar
plugin. It does not install files, start services, read the credentials of,
or communicate with the existing `~/.local/bin/tidal` application.

## Current state

- `otidal` is a new, non-conflicting command. The Python package is
  `omarchy_tidal`. The Omarchy plugin id is `community.otidal`.
- Login uses a dedicated `session.json`; it never loads credentials from the
  existing personal CLI.
- `play` auto-starts `otidal daemon`, which owns mpv over `player.sock` and
  publishes MPRIS as `org.mpris.MediaPlayer2.otidal`.
- Queue, mixed search, favorites list/add/remove, album/artist/playlist
  expand, replenishing radio, and shuffle of remaining tracks live in the
  player process.
- Default quality is HI_RES_LOSSLESS, falling back through LOSSLESS/HIGH/LOW.
  Live playback has used both LOSSLESS DASH and Hi-Res DASH.
- The Omarchy bar plugin is installed locally as a symlink via
  `scripts/otidal-plugin-install` and removed with
  `scripts/otidal-plugin-rollback`. Packaging / AUR is not implemented.

This is an unofficial personal community project, not affiliated with TIDAL.
Playback uses the unofficial `tidalapi` package; that path is outside TIDAL's
documented third-party playback offering.

## Commands

```text
login search favs play queue radio next prev jump toggle stop
shuffle favorite status quit doctor daemon
```

Most playback commands accept `--json`. `shuffle` and `favorite` toggle, or
take `on` / `off`.

## Plugin

The bar popup talks only to the plugin-local `bin/otidal` wrapper (which
runs `scripts/otidal-dev`). It provides search, favorites, radio, queue,
shuffle, a favorite heart for the current track, and playback controls.
Search and queue lists stay inside the popup with a scrollbar. Long titles
marquee on hover. Shuffle and Close List appear under the search field when
a list is open.

The install is a symlink into `~/.config/omarchy/plugins/`. Omarchy's plugin
watcher does not follow that symlink, so QML edits need
`omarchy restart shell`. New player IPC methods need `otidal-dev quit` (the
next play command starts a fresh daemon).

## Local checks

```bash
PYTHONPATH=src python3 -m omarchy_tidal --help
PYTHONPATH=src python3 -m unittest discover -s tests
omarchy plugin validate ./omarchy-plugin
```

Live development without touching existing TIDAL state uses
[`scripts/otidal-dev`](scripts/otidal-dev). See
[`DEVELOPMENT.md`](DEVELOPMENT.md), [`ARCHITECTURE.md`](ARCHITECTURE.md),
and [`ROADMAP.md`](ROADMAP.md).
