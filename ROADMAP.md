# Roadmap

Each milestone must work without reading or changing the installed personal
TIDAL CLI. Login, search, and a basic mpv controller already exist in-tree.
The remaining unknown is live stream proof, not those pieces.

The CLI plus idle mpv process is a feasibility harness. The product is a small
persistent player that owns the TIDAL session, queue, and mpv child.

1. **Live gate** — *passed.* Isolated login works. Search works. LOSSLESS
   playback of `t:56299935` (Marilyn Manson — Coma White) reached PipeWire
   via a local MPEG-DASH `.mpd` (TIDAL served DASH for LOSSLESS, not a BTS
   URL). mpv needed a lavf `https` protocol whitelist; `otidal-dev` must not
   replace `XDG_RUNTIME_DIR`. The old `tidal` command and MPD stayed
   untouched.
2. **DASH proof** — one HI_RES MPEG-DASH track plays. Prefer a local `.mpd`
   file. If mpv cannot consume that file, serve it from a **private** loopback
   or Unix-socket HTTP helper owned by otidal. Never use port 8765 or the
   existing `tidal-manifest` unit. Do not return to MPD unless both the direct
   URL and private-helper DASH paths fail.
3. **Player process** — *passed.* `otidal daemon` owns mpv and a Unix-socket
   JSON protocol at `player.sock`. `play` auto-starts it. `quit` shuts it
   down. Live play/status/toggle/stop/quit of Coma White worked.
4. **Queue** — *passed.* play vs append, next/previous, auto-advance when
   mpv goes idle. Streams are re-resolved per track.
5. **Radio and catalog** — replenishing radio, favorites, mixed search, and
   `t:`/`a:`/`p:`/`r:`/`favs` expand. Artwork URL on catalog tracks and
   status. Unit tests against fakes.
6. **MPRIS** — *passed.* The player process publishes
   `org.mpris.MediaPlayer2.otidal` with metadata, artwork, play/pause/stop/
   next/previous, seek, and volume. Omarchy's built-in media widget should
   talk to otidal, not to `mpv-mpris`.
7. **Omarchy plugin** — *installed locally for testing.* The bar widget
   calls the plugin-local `bin/otidal` wrapper, which uses `scripts/otidal-dev`
   so it talks to the isolated player process. Search, favorites, radio,
   play, queue, next/prev, and status polling are in the panel. Rollback:
   `scripts/otidal-plugin-rollback`. Do not publish a git remote.
8. **Packaging** — Arch/AUR player package and a separately git-installed
   Shell plugin, only after this would replace the MPD path for daily use.

Keep command contracts versioned. Default tests use fakes. Live-account and
playback tests are explicit opt-in.
