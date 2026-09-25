# omarchy-tidal-bar — Development

## Isolation

Use `scripts/otidal-dev` during development. It redirects configuration,
credentials, manifests, and otidal runtime sockets beneath the git-ignored
`.dev/` directory. It does not replace `XDG_RUNTIME_DIR`, so mpv can still
reach PipeWire.

It does not use:

- `~/.local/bin/tidal`
- `~/.cache/upmpdcli/tidal/`
- `~/.cache/tidal-cli/`
- MPD or its queue
- TCP ports 6600 or 8765

## Safe checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
omarchy plugin validate ./omarchy-plugin
scripts/otidal-dev doctor
scripts/otidal-dev status --json
```

## Live session

```bash
scripts/otidal-dev login
scripts/otidal-dev search "test query"
scripts/otidal-dev play "exact track query"
scripts/otidal-dev status
scripts/otidal-dev shuffle
scripts/otidal-dev favorite
scripts/otidal-dev remove 2
scripts/otidal-dev stop
```

Login is two-phase and non-blocking:

```bash
scripts/otidal-dev login start
# log in at the URL (opened in your browser), copy the 'Oops' page URL
scripts/otidal-dev login finish --redirect <oops-page-url>
```

A bare `scripts/otidal-dev login` still runs the original blocking flow.
`scripts/otidal-dev logout` stops playback and deletes the session. The
session is stored at `.dev/config/otidal/session.json`. Default quality is
`HI_RES_LOSSLESS`.

`shuffle` and `favorite` toggle. Pass `on` or `off` to set them. Both accept
`--json`.

## Plugin install (reversible)

```bash
scripts/otidal-plugin-install
scripts/otidal-plugin-rollback
```

Install is a symlink into `~/.config/omarchy/plugins/community.otidal` plus a
bar enable. It does not add pacman or pip packages. The panel runs
`omarchy-plugin/bin/otidal`, which execs `scripts/otidal-dev`. Rollback
disables and unlinks the plugin. A copy of `shell.json` from just before
install is kept at `.dev/plugin-install/shell.json`.

## Reloading after edits

The plugin is a symlink. Omarchy watches `~/.config/omarchy/plugins/` and
does not follow that symlink, so saving `Panel.qml` in the repo does not
hot-reload the widget. After QML changes:

```bash
omarchy restart shell
```

The running daemon does not reload Python. After player, queue, or IPC
changes:

```bash
scripts/otidal-dev quit
```

The next `play` / `queue` / `radio` / `shuffle` / `favorite` starts a new
daemon. `quit` drops the in-memory queue.
