# Architecture

## Product boundary

The player is an independent Linux application. Omarchy integration is a thin,
optional presentation layer rather than the owner of playback.

Target shape:

```text
                     TIDAL API
                         ^
                         |
  otidal CLI ---- IPC ---+--- otidald/player ---- mpv ---- PipeWire
      ^                         |
      |                         +---- MPRIS (org.mpris.MediaPlayer2.otidal)
      |
  Omarchy search panel          +---- XDG state/cache/config

  Omarchy's built-in media widget ---- MPRIS
```

Current shape:

```text
  otidal CLI ---- player.sock ---- otidal daemon ---- mpv ---- PipeWire
                                         |
                                         +---- MPRIS org.mpris.MediaPlayer2.otidal
                                         +---- XDG config/cache/runtime
```

The Shell plugin remains an uninstalled sketch until it talks to `player.sock`.

## Components

### `otidal`

User-facing CLI. Today it still performs catalog and playback work itself.
Once the player process exists, it only sends commands and prints
human-readable or versioned JSON responses. The distinct name guarantees that
development cannot shadow or overwrite the existing `tidal` command.

### Player process

A small persistent process owns the TIDAL session, queue, radio replenishment,
and playback state. It controls mpv over a private socket located beneath
`$XDG_RUNTIME_DIR/otidal/`. The first playback command may start it on demand;
packaging may later include a user service after lifecycle behavior is proven.

### mpv

The decoding/output backend. It provides FFmpeg-based decode (direct URLs and
DASH), PipeWire output, seeking, volume, and a documented IPC protocol. We do
not implement codecs or audio output ourselves. mpv is not the application:
it has no TIDAL session, queue policy, or public identity.

### Stream sources

`tidalapi` returns two playback kinds. The player must distinguish them:

- **BTS** (`application/vnd.tidal.bts`), typical for LOSSLESS/HIGH/LOW: a
  JSON manifest with one or more direct audio URLs. mpv should `loadfile`
  the URL.
- **MPEG-DASH** (`application/dash+xml`), used here for LOSSLESS FLAC as well
  as HI_RES: an MPD document with absolute https segment URLs. Write it
  atomically under the private cache and load the file. mpv must be started
  with a lavf `protocol_whitelist` that includes `https`; otherwise FFmpeg
  refuses nested https from a local file. If that still fails, serve the
  same bytes from a private loopback or Unix-socket HTTP helper. Never bind
  ports 8765 or 6600. Do not point `XDG_RUNTIME_DIR` at the project tree, or
  mpv will lose PipeWire.

Default quality is `HI_RES_LOSSLESS`. If that stream is unavailable, fall
back through `LOSSLESS`, `HIGH`, and `LOW`. `get_stream()` uses the session
attached to the track object, so fallback must set quality on that session.

### MPRIS

The player should publish `org.mpris.MediaPlayer2.otidal`. Omarchy already has
an MPRIS media service and bar widget, so ordinary playback controls and track
metadata require no duplicated TIDAL-specific bar widget. `mpv-mpris` may be
used as a one-time audio-path check; it is not the product identity.

### Omarchy plugin

The plugin supplies the TIDAL-specific experience that generic MPRIS cannot:
login state, search, favorites, radio, and queue browsing. It must call only
the public JSON/IPC contract of the player process. It must never hold
credentials, decode audio, or fork `tidalapi` inside `omarchy-shell`.

The in-repo `omarchy-plugin/` tree is an uninstalled UX sketch. Leave it
frozen until the player socket exists.

## Isolation rules

- Never invoke, import, replace, or modify `~/.local/bin/tidal`.
- Never use ports 6600 or 8765, the existing MPD queue, or its manifest cache.
- A private HTTP helper owned by otidal is allowed; sharing the old manifest
  server is not.
- Use the command name `otidal`, Python package `omarchy_tidal`, application ID
  `org.omarchycommunity.otidal`, and MPRIS name `otidal`.
- Use XDG paths rooted at `otidal`, not `tidal-cli` or `upmpdcli`.
- Tests use fake catalog and playback adapters by default; live-account tests
  must be explicit opt-in tests.

## Public status contract (v1)

```json
{
  "schema_version": 1,
  "available": false,
  "state": "stopped",
  "track": null,
  "position": 0.0,
  "duration": 0.0,
  "error": "player is not running"
}
```

The Shell plugin may depend on this shape. Additive fields are allowed within
version 1; incompatible changes require a new schema version.

## Packaging direction

The eventual player belongs in an Arch/AUR package with explicit dependencies.
The Omarchy plugin remains a normal git-installed Shell plugin. Keeping those
delivery mechanisms separate prevents unsandboxed QML plugin installation from
running package hooks or silently installing system software. Packaging waits
until this would replace the MPD path for daily use. The project stays
unofficial and local.
