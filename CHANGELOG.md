# Changelog

## 0.0.2

### Added

- `shuffle <selector>`: queues the selector (skipping tracks already queued),
  turns shuffle on, and starts from a random track when the queue was empty.
- Bar plugin: clicking Shuffle while the favorites list is open queues all
  favorites, starts playback shuffled, and switches to the queue view.
- Two-phase login: `login start` prints/opens the TIDAL URL and stores the
  pending PKCE state; `login finish --redirect <oops-page-url>` completes the
  flow. Bare `login` still runs the original blocking terminal flow.
  `client_unique_key` is persisted between phases.
- `logout` command: stops playback, clears the queue, deletes the session and
  pending login state, and shuts the daemon down (next `play` starts a fresh
  one).
- `status --json` now carries `logged_in` (CLI-side, works with the daemon
  stopped) within schema v1.
- `remove <position>` command: deletes a queue position (1-based); removing
  the now-playing track stops playback.
- Bar plugin: in-popup two-step Login flow (URL + paste field + Finish). All
  other controls are hidden while logged out.
- Bar plugin: queue rows have a remove button; search and favorites rows
  switch between + and − as tracks enter and leave the queue (clicking − on
  an already-queued result removes it).
- Bar plugin: now-playing toast (cover, title, artist) appears under the bar
  at the plugin's position when the track changes; auto-hides after 4s;
  clicking it opens the popup. Status polling now runs continuously, so the
  bar also reflects external start/stop/queue changes.
- Bar plugin: the favorites list loads in full (up to 1000 tracks) in a lazy
  `ListView`; the now-playing title marquees on hover when it overflows.

### Fixed

- Favorite state: the per-track favorites GET is not supported by the TIDAL
  API (405/404), so the current track always read as not-favorited. The
  client now caches the favorites list once per daemon session and updates
  the cache on add/remove.
- Queue button grays out and is inert when the queue is empty.

## 0.0.1

- Initial release: isolated `otidal` CLI and daemon (mpv + MPRIS
  `org.mpris.MediaPlayer2.otidal`), in-memory queue, radio, favorites, mixed
  search, Hi-Res DASH playback, and the Omarchy bar plugin
  `community.otidal` (search, favorites, radio, queue, shuffle, favorite
  toggle, panel scrolling).
