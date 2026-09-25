# omarchy-tidal-bar — Roadmap

Each milestone must work without reading or changing the installed personal
TIDAL CLI.

1. **Live gate** — *passed.* Isolated login works. Search works. LOSSLESS
   playback of `t:56299935` (Marilyn Manson — Coma White) reached PipeWire
   via a local MPEG-DASH `.mpd`. mpv needed a lavf `https` protocol
   whitelist; `otidal-dev` must not replace `XDG_RUNTIME_DIR`.
2. **DASH / Hi-Res** — *passed in daily use.* Default quality is
   `HI_RES_LOSSLESS` with fallback. Live Hi-Res DASH (24-bit / 96 kHz) has
   played through the same local `.mpd` path. A private HTTP helper remains
   available if a future stream fails; never use port 8765 or the existing
   `tidal-manifest` unit.
3. **Player process** — *passed.* `otidal daemon` owns mpv and Unix-socket
   JSON at `player.sock`. `play` auto-starts it. `quit` shuts it down.
4. **Queue** — *passed.* play vs append, next/previous, auto-advance, jump.
   Shuffle reorders the remaining tail and keeps the current track. Streams
   are re-resolved per track.
5. **Radio and catalog** — *passed.* Replenishing radio, mixed search,
   `t:`/`a:`/`p:`/`r:`/`favs` expand, artwork URLs. Favorites can be listed,
   added, and removed for the current track (`otidal favorite`).
6. **MPRIS** — *passed.* `org.mpris.MediaPlayer2.otidal` with metadata,
   artwork, and transport. Omarchy's built-in media widget should talk to
   otidal, not to `mpv-mpris`.
7. **Omarchy plugin** — *installed locally for testing.* Bar popup: search,
   favorites, radio, queue (with remove), shuffle, artwork favorite-heart
   overlay, playback controls, and a two-step Login flow when logged out.
   Full favorites list with lazy rows; long titles marquee on hover;
   now-playing toast on track change; queue +/− membership buttons. QML
   edits need `omarchy restart shell` because the install is a symlink.
   Rollback: `scripts/otidal-plugin-rollback`. Remote is
   `origin` → `git@github.com:carlbme/omarchy-tidal-bar.git`. Pushes go to
   a PR; the owner reviews and merges `master`.
8. **Packaging** — Arch/AUR player package and a separately git-installed
   Shell plugin, only after this would replace the MPD path for daily use.

Keep command contracts versioned. Default tests use fakes. Live-account and
playback tests are explicit opt-in.
