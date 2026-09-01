# TIDAL for Omarchy — Agent Handoff

## Objective

Continue building a clean, local, unofficial TIDAL player with an optional
Omarchy Shell plugin. The owner accepts responsibility for personal use and
maintenance. Do not publish the repository or create/push a GitHub remote
unless the user explicitly asks.

## Non-negotiable isolation

The existing personal TIDAL CLI works and must remain untouched.

- Never modify, replace, invoke, or import `~/.local/bin/tidal`.
- Never read or reuse `~/.cache/upmpdcli/tidal/pkce.credentials.json`.
- Never read or reuse `~/.cache/tidal-cli/`.
- Do not connect to or alter MPD, its queue, port 6600, or port 8765.
- Keep the new command named `otidal`, package named `omarchy_tidal`, and
  Omarchy plugin ID named `community.otidal`.
- During development, use `scripts/otidal-dev`; it redirects all state beneath
  the git-ignored `.dev/` directory.
- Do not install or enable the Omarchy plugin until live playback is proven and
  the user authorizes installation.

## Current state

The repository is local only and currently has no GitHub remote. Initial work
is committed as:

```text
50d3ca2 Scaffold isolated TIDAL player and Omarchy plugin
```

Implemented:

- Dedicated XDG path management and project-local development paths.
- Isolated `tidalapi` PKCE login and session loading.
- Track search, track-ID/query resolution, and normalized metadata.
- DASH manifest extraction and atomic private-cache writes.
- On-demand mpv process and JSON IPC controller.
- `login`, `search`, `play`, `toggle`, `stop`, `status`, and `doctor` commands.
- Versioned JSON output for Shell integration.
- Omarchy bar-widget/popup prototype for search and playback controls.
- Six unit tests covering CLI shape, path isolation, and mpv IPC behavior.
- Omarchy manifest validation.

Not yet performed:

- No login has been created for `otidal`.
- No live TIDAL search or stream has been tested.
- mpv has not been started by this project.
- The Omarchy plugin has not been installed, loaded, or enabled.
- Queueing, next/previous, radio, favorites, artwork, and complete MPRIS
  metadata are not implemented.

## Start every continuation with

```bash
cd /home/carl/Work/tidal-omarchy
git status --short
git log -1 --oneline
PYTHONPATH=src python3 -m unittest discover -s tests -v
omarchy plugin validate ./omarchy-plugin
scripts/otidal-dev doctor
scripts/otidal-dev status --json
```

Expected baseline: six passing tests, valid plugin manifest, `mpv` and
`tidalapi` available, no development login, and no player running.

## Immediate next milestone: one-track feasibility gate

Authentication is interactive and must be initiated by the account owner in a
terminal:

```bash
scripts/otidal-dev login
```

The command prints a TIDAL PKCE URL. The user opens it, authenticates, and
pastes the final redirect URL into the same terminal. Credentials must land at:

```text
.dev/config/otidal/session.json
```

After login, perform the smallest possible live test:

```bash
scripts/otidal-dev search "an exact track query"
scripts/otidal-dev play "the exact track query"
scripts/otidal-dev status
scripts/otidal-dev stop
```

Verify all of the following before expanding scope:

1. The search returns expected metadata.
2. The generated `.dev/cache/otidal/manifests/<track-id>.mpd` is usable by mpv.
3. Audio reaches PipeWire without MPD or a localhost HTTP server.
4. `status`, pause/toggle, and stop work across separate CLI invocations.
5. mpv remains controllable through `.dev/runtime/otidal/mpv.sock`.
6. `mpv-mpris` exposes the player to Omarchy's existing media service.
7. The old `tidal` command and MPD playback remain unaffected.

If playback fails, preserve diagnostic output and determine whether the issue is
the local-file DASH manifest, expired segment URLs, mpv/FFmpeg parsing, audio
output, or IPC. Do not fall back to the existing CLI credentials or manifest
server as a shortcut.

## Work after the gate

Proceed in this order:

1. Harden mpv startup, stale-socket recovery, shutdown, and error reporting.
2. Add a persistent queue with next/previous and automatic track transitions.
3. Implement radio as a replenishing queue, not a fixed one-track action.
4. Add favorites, albums, artists, and playlists behind stable JSON contracts.
5. Add artwork and complete MPRIS metadata.
6. Add plugin model tests and validate QML against the installed Omarchy API.
7. Design explicit install/uninstall tooling only after the source workflow is
   reliable; obtain user approval before installing it.

Keep command contracts versioned and test fake adapters by default. Any test
that uses the live account or changes playback must be explicit rather than part
of the normal unit suite.

## Architecture and policy context

Read these before changing component boundaries:

- `README.md`
- `ARCHITECTURE.md`
- `DEVELOPMENT.md`
- `ROADMAP.md`

The application uses the unofficial `tidalapi` package. TIDAL's documented
third-party platform does not currently provide this native full-track playback
path. Keep the project described as unofficial and local; do not imply TIDAL
affiliation or endorsement.

For Omarchy work, follow the installed Omarchy plugin conventions. The plugin
runs as unsandboxed QML inside `omarchy-shell`, so keep authentication, network
access, credentials, and playback in the external `otidal` application. The
plugin should consume only the public CLI/JSON or future IPC contract.
