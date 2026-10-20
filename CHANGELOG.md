# Changelog

All notable changes to vpnbox. The first stable will be `1.0.0`; the beta
cycle uses `1.0.0-beta1`, `1.0.0-beta2`, …

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
- Cancel paths clarified: Enter on any prompt backs out ("back to the
  menu"), nothing ever leaves you stranded; success/error feedback is ✓
  green / ✗ red in one status line
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
