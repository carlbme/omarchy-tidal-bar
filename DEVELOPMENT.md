# Development

## Isolation

Use `scripts/otidal-dev` during development. It redirects all application
configuration, credentials, manifests, state, and runtime sockets beneath the
git-ignored `.dev/` directory in this repository.

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

Then perform the smallest stream experiment:

```bash
scripts/otidal-dev search "test query"
scripts/otidal-dev play "exact track query"
scripts/otidal-dev status
scripts/otidal-dev stop
```

Do not install or enable the Omarchy plugin until this gate proves that mpv can
consume the generated manifest reliably.
