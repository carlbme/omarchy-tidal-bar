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
- A private HTTP helper owned by otidal is allowed later if local DASH files
  fail. Reusing the existing `tidal-manifest` unit is not.
- Keep the new command named `otidal`, package named `omarchy_tidal`, and
  Omarchy plugin ID named `community.otidal`.
- During development, use `scripts/otidal-dev`; it redirects all state beneath
  the git-ignored `.dev/` directory.
- The Omarchy plugin may be installed as a symlink for testing. Remove it
  with `scripts/otidal-plugin-rollback`. Do not `pip install` or add pacman
  packages for the plugin. Do not publish a git remote.

## Current state

The repository is local only and currently has no GitHub remote.

Implemented:

- Dedicated XDG path management and project-local development paths.
  `OTIDAL_RUNTIME_DIR` isolates sockets; `XDG_RUNTIME_DIR` stays the session
  runtime so mpv can reach PipeWire.
- Isolated `tidalapi` PKCE login and session loading.
- Track search, track-ID/query resolution, and normalized metadata.
- Stream resolution that distinguishes BTS direct URLs from MPEG-DASH MPDs,
  with quality fallback. Default quality is `LOSSLESS`. TIDAL served LOSSLESS
  as DASH in the live gate.
- mpv JSON IPC with lavf `https` whitelist for local DASH files, and
  `force-media-title` instead of read-only `media-title`.
- Persistent player process (`otidal daemon`) with Unix-socket JSON at
  `player.sock`. `play` auto-starts it. `login`/`search`/`doctor` stay in
  the CLI. `quit` shuts the process down.
- In-process queue: `play` replaces, `queue` appends, `next`/`prev`, and
  auto-advance when mpv goes idle. Streams are re-resolved per track.
- Catalog: mixed search, favorites, album/artist/playlist expand, artwork
  URLs. Radio starts a station from a seed and replenishes the queue.
- MPRIS `org.mpris.MediaPlayer2.otidal` exported by the player process.
- `login`, `search`, `favs`, `play`, `queue`, `radio`, `next`, `prev`,
  `toggle`, `stop`, `status`, `quit`, `doctor`, and `daemon` commands.
- Versioned JSON output for Shell integration.
- Frozen Omarchy bar-widget/popup prototype for search and playback controls.
- Unit tests covering CLI shape, path isolation, mpv IPC, stream sources,
  and player IPC.
- Omarchy manifest validation.

Live gate:

- Isolated login exists at `.dev/config/otidal/session.json`.
- Search and playback of `t:56299935` (Marilyn Manson — Coma White) worked.
- Audio reached PipeWire without MPD or port 8765.

Not yet performed:

- The Omarchy plugin has not been installed, loaded, or enabled.
- Packaging / AUR is not implemented.
- HI_RES_LOSSLESS has not been proven separately (LOSSLESS already used DASH).

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

Expected baseline: unit tests passing, valid plugin manifest, `mpv` and
`tidalapi` available, development login present, player process may or may
not be running.

## Immediate next milestone: packaging only after daily-driver use

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

After login, prove a direct URL first (default `OTIDAL_QUALITY=LOSSLESS`):

```bash
scripts/otidal-dev search "an exact track query"
scripts/otidal-dev play "the exact track query"
scripts/otidal-dev status
scripts/otidal-dev stop
```

Verify all of the following before expanding scope:

1. The search returns expected metadata.
2. Play reports `source.kind` `url` for LOSSLESS/HIGH (not a `.mpd` file).
3. Audio reaches PipeWire without MPD and without the old port-8765 server.
4. `status`, pause/toggle, and stop work across separate CLI invocations.
5. mpv remains controllable through `.dev/runtime/otidal/mpv.sock`.
6. The old `tidal` command and MPD playback remain unaffected.

Optional second proof, after LOSSLESS works:

```bash
OTIDAL_QUALITY=HI_RES_LOSSLESS scripts/otidal-dev play "the exact track query"
```

Expect `source.kind` `dash` and a file under
`.dev/cache/otidal/manifests/<track-id>.mpd`. If that fails, diagnose local
DASH vs expired segments vs mpv/FFmpeg. A private otidal HTTP helper is the
next lever. Do not fall back to the existing CLI credentials or manifest
server. `mpv-mpris` may be glanced at as a desktop-audio check; do not design
identity around it.

## Work after the gate

Proceed in this order (see `ROADMAP.md`):

1. Persistent player process (`otidald`) with Unix-socket JSON, session
   ownership, mpv child, stale-socket recovery, and clean shutdown.
2. Queue: next/previous, auto-advance, play vs append, tests on fakes.
3. Radio as a replenishing queue; favorites, albums, artists, playlists.
4. `org.mpris.MediaPlayer2.otidal` with real metadata/artwork.
5. Point the Omarchy plugin at the player process, then install only with
   user approval.
6. Packaging only after the owner would uninstall the MPD path.

Keep command contracts versioned and test fake adapters by default. Any test
that uses the live account or changes playback must be explicit rather than
part of the normal unit suite.

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
