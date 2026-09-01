# Architecture

## Product boundary

The player is an independent Linux application. Omarchy integration is a thin,
optional presentation layer rather than the owner of playback.

```text
                     TIDAL API
                         ^
                         |
  otidal CLI ---- IPC ---+--- otidald/player ---- mpv ---- PipeWire
      ^                         |
      |                         +---- MPRIS
      |
  Omarchy search panel          +---- XDG state/cache/config

  Omarchy's built-in media widget ---- MPRIS
```

## Components

### `otidal`

User-facing CLI. It sends commands to the player and prints human-readable or
versioned JSON responses. The distinct name guarantees that development cannot
shadow or overwrite the existing `tidal` command.

### Player process

A small persistent process owns the TIDAL session, queue, radio replenishment,
and playback state. It controls mpv over a private socket located beneath
`$XDG_RUNTIME_DIR/otidal/`. The first playback command may start it on demand;
packaging may later include a user service after lifecycle behavior is proven.

### mpv

The proposed decoding/output backend. It provides FFmpeg-based DASH decoding,
PipeWire output, seeking, volume, and a documented IPC protocol. We do not
implement codecs or audio output ourselves.

### MPRIS

The player should publish `org.mpris.MediaPlayer2.otidal`. Omarchy already has
an MPRIS media service and bar widget, so ordinary playback controls and track
metadata require no duplicated TIDAL-specific bar widget.

### Omarchy plugin

The plugin supplies the TIDAL-specific experience that generic MPRIS cannot:
login state, search, favorites, radio, and queue browsing. It calls only the
public `otidal --json` contract. It must never hold credentials or decode audio
inside `omarchy-shell`.

## Isolation rules

- Never invoke, import, replace, or modify `~/.local/bin/tidal`.
- Never use ports 6600 or 8765, the existing MPD queue, or its manifest cache.
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
  "error": "playback backend is not implemented"
}
```

The Shell plugin may depend on this shape. Additive fields are allowed within
version 1; incompatible changes require a new schema version.

## Packaging direction

The eventual player belongs in an Arch/AUR package with explicit dependencies.
The Omarchy plugin remains a normal git-installed Shell plugin. Keeping those
delivery mechanisms separate prevents unsandboxed QML plugin installation from
running package hooks or silently installing system software.

