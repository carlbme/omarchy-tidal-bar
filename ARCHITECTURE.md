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
When `status` reports `logged_in: false`, the popup shows a Login button
that runs `login start` / `login finish`.

## Components

### `otidal`

User-facing CLI. Catalog lookups that do not need the daemon
(`login`, `search`, `favs` list, `doctor`) run in-process. `logout` uses the
daemon when it is running and deletes the session files directly otherwise.
Playback, queue, radio, shuffle, favorite toggle, and status go over
`player.sock`. `play` auto-starts the daemon. `login start` / `login finish`
perform the non-blocking PKCE exchange (`login-pending.json` holds the code
verifier between the two steps).

### Player process

`otidal daemon` owns the TIDAL session, in-memory queue, radio replenishment,
shuffle flag, current-track favorite flag, and mpv. It listens on
`$XDG_RUNTIME_DIR/otidal/player.sock` (or `.dev/runtime/otidal/` under
`otidal-dev`).

Queue policy:

- `play` replaces the queue and starts index 0.
- `queue` appends. If shuffle is on, new tracks are mixed into the remaining
  tail; the current track stays put.
- `remove` deletes a queue position (shifting the index when it precedes the
  current track). Removing the now-playing track stops playback.
- `next` / `prev` / `jump` are sequential. Shuffle is a reorder of the
  remaining tail, not random-next.
- Radio replenishes when few tracks remain. New radio tracks are shuffled
  into the tail when shuffle is on.
- `favorite` adds or removes the current track via `tidalapi` user
  favorites. The per-track check is membership in a cached favorites list
  (one GET per daemon session; the cache updates on add/remove), because
  TIDAL has no per-track favorites GET endpoint.

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

- Transport and library rows stay compact. A heart overlay on the artwork
  (revealed on hover, outline vs. filled) toggles favorite for the current
  track.
- Search stays on one row with the Search button. When a list is open,
  Shuffle and Close List sit under the search field. Close List hides the
  list; it does not empty the play queue.
- Results (search, queue, and the full favorites list up to 1000 tracks)
  render in a lazy `ListView` clipped to the popup with a vertical
  scrollbar, so row objects and artwork load on demand.
- Long row titles marquee only while hovered.
- Queue rows show a remove (−) button; search and favorites rows switch
  between + and − by queue membership (matched against the `status` queue
  IDs on the 2s poll). Clicking − on an already-queued result removes it.
- The plugin polls `status --json` every 2s continuously (so the bar also
  reflects external start/stop/queue changes). On a `track.id` change
  while logged in, a now-playing toast opens via the shell's `PopupCard`
  (a dedicated `PopupWindow` anchored under the bar item, passive
  "hover" mode — no focus grab, no outside-click dismissal). It auto-hides
  after 4s; clicking it opens the main popup. The first read after a reset
  only sets the baseline and never toasts.

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
  "error": "player is not running",
  "logged_in": false
}
```

While the daemon is up, additive fields currently include `queue`, `index`,
`radio`, `shuffle`, `favorite`, and `volume`. `logged_in` is added by the
CLI from the session file, so it is present even when the daemon is stopped.
Additive fields are allowed within version 1; incompatible changes require a
new schema version.

## Packaging direction

The player belongs in an Arch/AUR package. The Omarchy plugin remains a
git-installed Shell plugin. Packaging waits until this would replace the
MPD path for daily use.
