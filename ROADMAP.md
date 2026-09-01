# Roadmap

Each milestone must work without reading or changing the installed personal
TIDAL CLI.

1. **Stream feasibility** *(foundation implemented; live proof pending)* — with separate opt-in development credentials,
   resolve one track and prove mpv can play it without MPD or a localhost HTTP
   server.
2. **Player IPC** — persistent mpv control, status, stop, pause, next, clean
   shutdown, and recovery from a stale socket.
3. **Application login** — own PKCE flow and XDG credential storage; remove the
   `upmpdcli` authentication dependency.
4. **Queue and radio** — queue ownership plus replenishing radio, with unit tests
   against fake TIDAL responses.
5. **MPRIS** — metadata and standard desktop media controls.
6. **Omarchy UX** — search/favorites/radio panel backed by versioned JSON or IPC.
7. **Packaging** — reproducible Arch package, dependency declaration, uninstall,
   credential preservation policy, and community documentation.

The first go/no-go decision is milestone 1. If mpv cannot consume the stream
reliably without a local manifest bridge, retain a private embedded bridge or
reconsider MPD before building the rest.
