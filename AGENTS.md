# omarchy-tidal-bar — Agent Handoff

## Objective

Continue building a clean, unofficial TIDAL player with an optional Omarchy
Shell plugin. The owner accepts responsibility for personal use and
maintenance.

Git remote `origin` is `git@github.com:carlbme/omarchy-tidal-bar.git`.
`master` tracks `origin/master`. Do not add another remote, force-push,
push to `master`, merge to `master`, or change GitHub visibility unless
the user asks.

When the user asks to publish work: commit on a topic branch, push that
branch to `origin`, and open a pull request against `master`. The owner
(Carl) reviews and merges. Do not merge the PR, do not push commits onto
`master`, and do not use admin merge shortcuts.

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
- The Omarchy plugin is installed as a symlink. Remove it with
  `scripts/otidal-plugin-rollback`. Do not `pip install` or add pacman
  packages for the plugin.

## Current state

Workspace: `/home/carl/Work/tidal-omarchy`. Public name and GitHub repo:
`omarchy-tidal-bar`.

HEAD on `origin/master` is older than the working tree. Uncommitted work
covers the plugin UX (scrollable lists, hover marquee, Shuffle / Close List,
favorite heart) plus player/CLI shuffle and favorite toggle. Do not discard
that work.

Implemented (including uncommitted tree):

- Dedicated XDG path management and project-local development paths.
  `OTIDAL_RUNTIME_DIR` isolates sockets; `XDG_RUNTIME_DIR` stays the session
  runtime so mpv can reach PipeWire.
- Isolated `tidalapi` PKCE login and session loading. Login is two-phase:
  `login start` (prints/opens the URL, stores `login-pending.json` with the
  code verifier) and `login finish --redirect <oops-page-url>`. Bare `login`
  keeps the blocking terminal flow. `logout` stops the daemon (or deletes
  files directly) and removes the session.
- Track search, track-ID/query resolution, and normalized metadata.
- Stream resolution that distinguishes BTS direct URLs from MPEG-DASH MPDs,
  with quality fallback. Default quality is `HI_RES_LOSSLESS`. Live playback
  has used LOSSLESS DASH and Hi-Res DASH.
- mpv JSON IPC with lavf `https` whitelist for local DASH files.
- Persistent player process (`otidal daemon`) with Unix-socket JSON at
  `player.sock`. `play` auto-starts it. `login`/`search`/`favs` list/`doctor`
  stay in the CLI. `quit` shuts the process down and drops the in-memory
  queue.
- In-process queue: `play` replaces, `queue` appends, `next`/`prev`/`jump`,
  auto-advance. `remove` deletes a queue position; removing the now-playing
  track stops playback. Shuffle reorders the remaining tail and keeps the
  current track. New appends and radio fills mix into that tail while shuffle
  is on.
- Catalog: mixed search, favorites list/add/remove, album/artist/playlist
  expand, artwork URLs. Radio replenishes the queue.
- MPRIS `org.mpris.MediaPlayer2.otidal`.
- Commands: `login` (`start`/`finish`), `logout`, `search`, `favs`, `play`,
  `queue`, `radio`, `next`, `prev`, `jump`, `toggle`, `stop`, `shuffle`,
  `favorite`, `remove`, `status`, `quit`, `doctor`, `daemon`. Versioned JSON
  output for Shell integration. `status` carries `logged_in` (CLI-side, works
  with the daemon stopped).
- Omarchy plugin `community.otidal` enabled on the right of the bar as a
  symlink to `omarchy-plugin/`. Popup: search, favorites, radio, queue (with
  remove), shuffle, artwork favorite-heart overlay, transport, and a two-step
  Login flow when logged out (everything else is hidden). Lists clip inside
  the popup with a scrollbar. Long titles marquee on hover. Search/favorites
  rows show +/− by queue membership. A now-playing toast appears under the
  bar at the plugin's position on track change. Shuffle and Close
  List sit under the search field when a list is open. Close List hides the
  list; it does not empty the play queue.
- Unit tests covering CLI shape, path isolation, mpv IPC, stream sources,
  queue shuffle, favorite toggle, and player IPC.

Live gate:

- Isolated login exists at `.dev/config/otidal/session.json`.
- Search and playback of `t:56299935` (Marilyn Manson — Coma White) worked.
- Audio reached PipeWire without MPD or port 8765.
- The bar plugin is installed and in daily use.

Not yet performed:

- Packaging / AUR.
- Committing the uncommitted plugin/player work on a topic branch and
  opening a PR to `master` for the owner to review and merge.

Reload caveats (not missing features):

- The plugin install is a symlink, so QML saves in the repo do not
  hot-reload. After `Panel.qml` edits run `omarchy restart shell`.
- After player IPC changes run `scripts/otidal-dev quit` so the next play
  starts a new daemon. That drops the in-memory queue.

## Start every continuation with

```bash
cd /home/carl/Work/tidal-omarchy
git status --short
git remote -v
git log -1 --oneline
PYTHONPATH=src python3 -m unittest discover -s tests -v
omarchy plugin validate ./omarchy-plugin
scripts/otidal-dev doctor
scripts/otidal-dev status --json
```

Expected baseline: unit tests passing, valid plugin manifest, `mpv` and
`tidalapi` available, development login present, `origin` set, player
process may or may not be running.

## Immediate next milestone: packaging only after daily-driver use

The plugin is already in daily use. Do not expand into AUR until the owner
would uninstall the MPD path. Authentication remains interactive:

```bash
scripts/otidal-dev login
```

Credentials must land at `.dev/config/otidal/session.json`.

## Architecture and policy context

Read these before changing component boundaries:

- `README.md`
- `ARCHITECTURE.md`
- `DEVELOPMENT.md`
- `ROADMAP.md`

The application uses the unofficial `tidalapi` package. Keep the project
described as unofficial; do not imply TIDAL affiliation.

For Omarchy work, follow installed Omarchy plugin conventions. The plugin
runs as unsandboxed QML inside `omarchy-shell`, so keep authentication,
network access, credentials, and playback in the external `otidal`
application. The plugin should consume only the public CLI/JSON contract.
