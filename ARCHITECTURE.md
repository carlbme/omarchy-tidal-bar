# omarchy-tidal-bar — Architecture

## Product boundary

omarchy-tidal-bar is an independent Linux application. Omarchy integration is a
thin, optional presentation layer rather than the owner of playback.

```text
                     TIDAL API
                         ^
                         |
  otidal CLI ---- IPC ---+--- otidal daemon ---- mpv ---- PipeWire
      ^                         |
      |                         +---- MPRIS (org.mpris.MediaPlayer2.otidal)
      |
  Omarchy bar panel             +---- XDG config/cache/runtime

  Omarchy's built-in media widget ---- MPRIS
```

The Shell plugin calls the public CLI/JSON contract. It never holds
credentials, decodes audio, or imports `tidalapi` inside `omarchy-shell`.

## Components

### `otidal`

User-facing CLI. Catalog lookups that do not need the daemon
(`login`, `search`, `favs` list, `doctor`) run in-process. Playback, queue,
radio, shuffle, favorite toggle, and status go over `player.sock`. `play`
auto-starts the daemon.

### Player process

`otidal daemon` owns the TIDAL session, in-memory queue, radio replenishment,
shuffle flag, current-track favorite flag, and mpv. It listens on
`$XDG_RUNTIME_DIR/otidal/player.sock` (or `.dev/runtime/otidal/` under
`otidal-dev`).

Queue policy:

- `play` replaces the queue and starts index 0.
- `queue` appends. If shuffle is on, new tracks are mixed into the remaining
  tail; the current track stays put.
- `next` / `prev` / `jump` are sequential. Shuffle is a reorder of the
  remaining tail, not random-next.
- Radio replenishes when few tracks remain. New radio tracks are shuffled
  into the tail when shuffle is on.
- `favorite` adds or removes the current track via `tidalapi` user
  favorites. Status reports `favorite` from a per-track check, not from a
  full favorites list.

### mpv

Decode and PipeWire output. Direct BTS URLs and local MPEG-DASH `.mpd`
files. Started with a lavf `protocol_whitelist` that includes `https`.

Default quality is `HI_RES_LOSSLESS`, then `LOSSLESS`, `HIGH`, `LOW`.

### MPRIS

`org.mpris.MediaPlayer2.otidal`. Ordinary play/pause/next/previous/seek
and metadata can go through Omarchy's generic media widget. The TIDAL
plugin is for search, queue, radio, shuffle, and favorites.

### Omarchy plugin

`community.otidal` is a bar widget. Local install is a symlink from
`~/.config/omarchy/plugins/community.otidal` to `omarchy-plugin/`. The
panel invokes `omarchy-plugin/bin/otidal`, which execs `scripts/otidal-dev`.

Popup behavior:

- Transport and library rows stay compact. A heart on the library row
  toggles favorite for the current track.
- Search stays on one row with the Search button. When a list is open,
  Shuffle and Close List sit under the search field. Close List hides the
  list; it does not empty the play queue.
- Results are clipped to the popup with a vertical scrollbar.
- Long row titles marquee only while hovered.

## Isolation rules

- Never invoke, import, replace, or modify `~/.local/bin/tidal`.
- Never use ports 6600 or 8765, the existing MPD queue, or its manifest cache.
- Use `otidal`, package `omarchy_tidal`, plugin `community.otidal`, MPRIS
  `otidal`.
- Tests use fake catalog and playback adapters by default.

## Public status contract (v1)

Stopped / missing player:

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

While the daemon is up, additive fields currently include `queue`, `index`,
`radio`, `shuffle`, `favorite`, and `volume`. Additive fields are allowed
within version 1; incompatible changes require a new schema version.

## Packaging direction

The player belongs in an Arch/AUR package. The Omarchy plugin remains a
git-installed Shell plugin. Packaging waits until this would replace the
MPD path for daily use.
