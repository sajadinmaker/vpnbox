# Changelog

All notable changes to vpnbox. The first stable will be `1.0.0`; the beta
cycle uses `1.0.0-beta1`, `1.0.0-beta2`, …

## Unreleased

### Fixed
- `vpn status --no-ip` no longer prints your unprotected address while the
  tunnel is down. The flag now suppresses the lookup in every state.
- A failed public-IP lookup no longer turns a successful connect, or a
  status read, into a crashed command.
- `vpn disconnect` reports the failure and exits 2 when the daemon could not
  be stopped, instead of printing `openvpn stopped`.
- A disconnect writes the end-of-session marker before tearing the tunnel
  down, so a slow teardown can no longer race `vpn watch` into resurrecting
  the tunnel.
- `--skip`, `--index`, `--max-tries`, `--give-up`, `--ping`, and `--limit`
  reject values that selected no servers or emitted an invalid profile.
- `vpn watch` gives up immediately after the final failed recovery cycle
  instead of waiting out the full backoff first.
- A failed refresh from the interactive menu returns to the menu instead of
  closing the UI.
- Corrupt server caches are ignored and refreshed instead of crashing
  `countries`, `servers`, or `connect`.
- `vpn status` no longer shows an age measured from 1970 when the metadata
  file is missing.
- A daemon can no longer survive `vpn disconnect` with its pid file lost:
  the cleanup path now sweeps any openvpn still bound to the pid marker
  before reporting "not connected".
- A sudo binary that is missing entirely now surfaces as exit code 127 with
  a readable message instead of an unhandled traceback mid-teardown.
- The interactive prompts stop instead of spinning on a detached terminal
  (EOF in raw mode used to busy-loop).

### Changed
- The tunnel profile, session intent, and metadata now live in a private
  runtime directory (`/run/vpnbox` when invoked as root, the user's runtime
  directory otherwise) instead of world-writable `/tmp` and `/var/tmp`.
  Legacy paths are still read so an upgrade keeps existing state.

## 1.0.0-beta5 — 2026-10-24

### Added
- **`vpn watch`**: supervise a connected session. If the OpenVPN daemon exits
  mid-session, the watchdog reconnects with the stored intent (country, city,
  site, office, transport), prints one line per event, and waits out repeated
  failures with a 30 s backoff capped at 5 min (`--give-up n` bounds the
  cycles, default 3). Ctrl-C stops the watcher, never the tunnel; a clean
  `vpn disconnect` always wins.
- **Dead-server detection** during the connect: the daemon pings the remote
  every 10 s and exits when nothing answers for 60 s by default
  (`--ping`, `--ping-exit`), so a dead volunteer server no longer leaves a
  silent black-hole tunnel. `--ping-exit 0` restores the old behavior.

### Fixed
- `--skip N` was accepted and documented but never applied; it now removes the
  first N ranked candidates before `--index`.
- A disconnect running while `vpn watch` was mid-recovery could resurrect the
  tunnel. `vpn disconnect` now records the end of the session on disk and the
  watchdog honors it: it tears down any tunnel it just rebuilt and exits.
- A failed connect attempt could leave an untracked OpenVPN daemon behind
  (a relaunch overwrites the pid file). Every fresh connect and recovery now
  sweeps the daemons bound to its config before launching a new one.

## 1.0.0-beta — 2026-10-20

### Added
- **Arrow-key selection**: ↑/↓ moves a reverse-video highlight over the
  menu, Enter runs it — over a plain numbered list that anyone can follow
- One-key shortcuts 1–6 run menu items instantly (plus silent letter
  aliases r/c/s/d/q for the old habit)

### Changed
- **Red-accented theme**: bold letterspaced red title, thin red rule, and a
  red-bordered live status panel — the big ASCII banner and the tagline
  lines ("no account, no key", "sources: …") are gone for good
- Plain-English wording throughout: "your IP / exit IP", "96 live servers
  · 8 countries", "list refreshed 5 min ago" — jargon gone
- Prompt semantics made foolproof: **Enter commits a forward default**
  (the top pool / first entry / HQ — shown right in the prompt), **Esc
  backs out** cleanly; nothing ever leaves you stranded, and success/
  error feedback is ✓ green / ✗ red in one status line
- **Fast-typing proof**: keys typed ahead (e.g. a number then Enter in one
  burst) are drained instead of answering the next dialog on their own —
  a dialog's first 0.35 s ignore pre-typed noise, and trailing keystrokes
  can no longer re-run a menu item after an action; typed-ahead input
  can no longer be answered by the terminal's own `tcflush` no-op either
- Dialogs are read through a raw-mode line reader with live echo (backspace
  works, caret visible), replacing cooked `input()`
- **The name is drawn, not typed**: a big red-themed box with `VPNBOX` in
  huge mono block letters (5 rows, bold white on solid red); on very wide
  terminals the letter cells double in width for an even bigger name, and
  narrow screens / `VPNBOX_PLAIN=1` fall back to a bold letterspaced strip
- **Fully responsive UI for every screen**: the layout adapts from 46 to
  120 columns — the status panel re-wraps its facts into stacked rows on
  narrow terminals, menu labels drop their long parenthetical hint, and
  the credit line trims its URL when the width demands it (wide screens
  get everything, never an overflow)
- Human list age: "5 min ago"/"2 h ago" instead of raw seconds
- Credit everywhere now names the full handle: **by sajadinmaker —
  github.com/sajadinmaker** (also in the LICENSE copyright)
- Version naming simplified to plain `1.0.0-beta` (the beta cycle's
  numbered tags v1.0.0-beta1…beta4 stay published on GitHub)

### Compatibility
- Static (non-TTY) fallback keeps the same numbered menu with the
  equivalent commands, so scripts and users see the same mental model

## 1.0.0-beta3 — 2026-10-20

### Added
- Author credit: "by sajad — github.com/sajadinmaker" on the intro screen,
  static banner, README and LICENSE
- One-key quick actions from the intro screen: `[1]` best server anywhere,
  `[2]` country / city, `[3]` appear near an office (skips the wizard menu)

### Changed
- Intro banner rebuilt as **pure ASCII** slab letters — renders correctly on
  every terminal font (the previous art used box-drawing glyphs that can
  mangle on some fonts). A regression test now enforces ASCII-only banner.
- README quick-start made friendlier for new users: numbered menu shown in
  the docs, credit at the top, LICENSE copyright now "sajad (sajadinmaker)
  and vpnbox contributors"

## 1.0.0-beta2 — 2026-10-20

### Added
- **Interactive intro session**: bare `vpn` (or explicit `vpn intro`) opens a
  full-screen experience — VPNBOX ASCII banner, live status panel
  (connection state, your IP + city, cache age) and a key-driven shell:
  `[R]` refresh · `[C]` connect wizard (best-anywhere / country+city /
  appear-near-a-platform-office) · `[S]` sites browser with each office's
  nearest live server · `[D]` disconnect · `[Q]` quit
- Implemented in pure ANSI + termios — stdlib-only rule preserved (no
  curses); terminal state is always restored, sudo prompts unaffected;
  arrows and Esc work
- Graceful fallback: when stdout isn't a real terminal (pipes, CI,
  `NO_COLOR`), the bare run prints the banner + status + command hints and
  exits 0 — scripts and pipelines never hang
- CI smoke now exercises the bare-invocation path
- `exit` codes unchanged; every existing command and flag behaves exactly
  as before

## 1.0.0-beta1 — 2026-10-20

First public release. Single-file Python 3 application (`vpnbox.py`),
standard library only, built on the VPN Gate academic relay experiment
(vpngate.net) and OpenVPN.

### Core features
- Live VPN Gate server list — no account, no key, no payment; per-server
  ping/speed/protocol extraction; auto-refresh when the cache is stale
- City/ISP geolocation enrichment (ip-api.com batch endpoint; receives only
  cached server IPs, never anything of yours)
- Full-tunnel OpenVPN: forced `redirect-gateway def1` + `block-ipv6`,
  systemd-resolved DNS handling (no DNS leaks), leak-safe revert on exit,
  exit-IP printed after every connect with country-mismatch warning
- Auto-failover: dead volunteer servers fast-fail and the next best candidate
  is tried (`--max-tries`, default 3); session-scoped success detection
  prevents stale-log false positives; `--index` / `--skip` for manual pinning
- 29 platforms · 239 offices · 31 countries for "appear near" targeting:
  `--site X` (primary HQ), `--office CITY` (any specific office),
  `--office all` (nearest to any office worldwide); office addresses
  precisely geocoded via OpenStreetMap Nominatim (cached); distance-tier
  ranking (≤40 / ≤150 / ≤500 / ≤1500 km) with ping/speed/UDP deciding
  within a tier

### Engineering base (shipped with this release)
- Hermetic unit-test suite — `make test` — covering site-database integrity,
  geography, ranking rules, office-tier targeting, full-tunnel config
  enforcement and version consistency
- CI on every push/PR across Python 3.9 → 3.13
- Tag-triggered release automation: pushing `vX.Y.Z` builds the tarball,
  checksums it and publishes it to GitHub Releases
- `install.sh` with dependency checks and stale-symlink replacement,
  `uninstall.sh --purge`, `vpn --version`, `Makefile` (check/test/dist/clean),
  `CONTRIBUTING.md`, `.editorconfig`, `.gitattributes`
- `APP_VERSION` in vpnbox.py is the single source of truth (enforced by
  tests and the release workflow)

### Verified live
- Connects with correct exit IPs: Tokyo (LINE office path, 3 km), Bangkok
  (Meta office, 4 km), Nakano City/Tokyo (Meta any-office, 9 km),
  Suwon/Yongin-si (Instagram Seoul office, 31 km), Chiba (Instagram Tokyo
  office, 38 km)
- Foreground verb-6 debug sessions, twice: one clean connect; one that
  exposed a mid-test server death (UDP hard-resets sent, zero replies —
  exactly the failure mode the auto-failover then routes around)

### Known limits
- Volunteer servers churn by the hour; country availability swings
  (typically strong: JP/KR/TH; delicate: US; sometimes absent: others)
- OpenVPN only — WireGuard support is future work
- No kill switch (see the README's "Honest limitations" for guidance)
