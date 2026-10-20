# Changelog

All notable changes to vpnbox. Versioning: semver, pre-releases as
`1.0.0-betaN` until the first stable.

## 1.0.0-beta1 — 2026-10-20

First public beta. Single-file Python 3 CLI (`vpnbox.py`), stdlib-only,
built on the VPN Gate academic relay experiment (vpngate.net) + OpenVPN.

### Core
- Live VPN Gate server list — no account, no key, no payment; CSV parse with
  per-server ping/speed/protocol extraction and auto-refresh when stale
- City/ISP geolocation enrichment (ip-api.com batch incl. lat/lon/region)
- Full-tunnel OpenVPN: forced `redirect-gateway def1` + `block-ipv6` and
  server-pushed route protection, systemd-resolved DNS handling
  (`openvpn-systemd-resolved`, no DNS leaks), leak-safe revert on exit
- Auto-failover: dead servers fast-fail (auth failures, unreachable,
  handshake timeouts) and the next best candidate is tried automatically
  (default 3 attempts); log-window check prevents stale-success false alarms
- Exit-IP verification after connect with country-mismatch warning

### Commands
- `vpn refresh` · `countries [--all]` · `servers CC [--city] [--limit]`
- `sites [--site X] [--geocode] [--recache]`
- `connect [--country CC] [--city CITY] [--site X] [--office CITY] [--tries N] [--debug]`
- `status` · `disconnect` · `log`

### Site / office targeting (new in this beta)
- 29 platforms, 239 offices across 31 countries: meta, instagram, threads,
  x, whatsapp, google, youtube, microsoft, linkedin, tiktok, snapchat,
  discord, reddit, pinterest, apple, telegram, signal, tumblr, viber, line,
  kakaotalk, wechat, netflix, twitch, slack, zoom, quora, spotify, vk
- `--site X` targets the primary HQ; `--office CITY` any specific office
  (substring match); `--office all` = nearest to ANY office worldwide
- Office addresses precise-geocoded via OpenStreetMap Nominatim
  (1 req/s policy, cached forever in `~/.cache/vpnbox/offices.json`)
- Distance-tier ranking (≤40 / ≤150 / ≤500 / ≤1500 km) — within a tier,
  ping/speed/UDP decide, so "near the office" also means "fast and alive"

### Verified in this beta
- Live connects + exit-IP verification: Tokyo, Osaka?→Tokyo offices,
  Bangkok (Meta office, 4 km), Nakano City/Tokyo (9 km), Seoul/Yongin-si
  (Instagram Seoul office, 31 km), Chiba (Instagram Tokyo office, 38 km)
- Debug recipe in README (foreground verb-6 run) exercised twice: one clean
  connect and one caught real-world server death (UDP hard-resets sent,
  zero replies) proving failover

### Known limits (beta)
- Volunteer servers churn by the hour; some countries appear/disappear
  (at release time: JP/KR/TH strong; US few; CA/PH unavailable)
- OpenVPN only — no WireGuard yet
- WeChat/Telegram server-side blocks etc. are not magic: "appear near an
  office" changes your exit IP; it cannot unblock platform-specific server
  policies
