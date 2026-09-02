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

## First live gate

Login is intentionally interactive and must be initiated by the account owner:

```bash
scripts/otidal-dev login
```

Open the printed TIDAL URL, authenticate, and paste the final redirect URL back
into that terminal. The resulting session is stored at
`.dev/config/otidal/session.json` with private permissions.

Then prove a **direct URL** path first. Default quality is `LOSSLESS`:

```bash
scripts/otidal-dev search "test query"
scripts/otidal-dev play "exact track query"
scripts/otidal-dev status
scripts/otidal-dev stop
```

Override quality only after LOSSLESS works:

```bash
OTIDAL_QUALITY=HI_RES_LOSSLESS scripts/otidal-dev play "exact track query"
```

## Plugin install (reversible)

```bash
scripts/otidal-plugin-install
scripts/otidal-plugin-rollback
```

Install is a symlink into `~/.config/omarchy/plugins/community.otidal` plus a
bar enable. It does not add pacman or pip packages. The panel runs
`omarchy-plugin/bin/otidal`, which execs `scripts/otidal-dev` so it uses the
isolated `.dev/` session. Rollback disables and unlinks the plugin. A copy of
`shell.json` from just before install is kept at `.dev/plugin-install/shell.json`.
