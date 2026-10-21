# vpnbox

**A free VPN for Linux that needs no account, no key, and no payment.**

v1.0.0-beta · 2026-10-20 · one Python file, standard library only
built by **sajadinmaker** — <https://github.com/sajadinmaker>

---

vpnbox is a command-line VPN client for Linux built on [VPN Gate](https://vpngate.net), the
volunteer relay experiment run by the University of Tsukuba. It fetches the live relay
list, shows what is reachable right now (with real ping and speed numbers), and connects
through OpenVPN with full-tunnel route enforcement and leak-safe DNS handling.

```bash
vpn refresh                          # see the world's volunteers as they are now
vpn countries                        # Japan? Korea? Thailand? — take your pick
sudo vpn connect --country Japan     # full tunnel, verified, ~15 seconds
```

## Requirements

Linux with OpenVPN 2.5+ and systemd-resolved (any current Ubuntu, Debian, Fedora,
Arch …), plus Python 3.8+. `install.sh` checks all of this for you:

- **python3** — the app itself
- **openvpn** — the datamover (vpnbox never reimplements a protocol)
- **openvpn-systemd-resolved** — so pushed DNS settings actually land on your system

## Install

Grab the release tarball, unpack, install:

```bash
tar -xzf vpnbox-1.0.0-beta.tar.gz
cd vpnbox-1.0.0-beta
sudo ./install.sh            # → /usr/local/bin/vpn, verified with --version
```

The command is `vpn` from then on. To leave cleanly:

```bash
sudo ./uninstall.sh          # remove the command
sudo ./uninstall.sh --purge  # also wipe runtime state (/var/log, /run, /var/tmp)
rm -rf ~/.cache/vpnbox       # optional: drop the server/office caches too
```

## Quick start

```bash
vpn refresh                  # fetch the live server list (~15 s) and geolocate it
vpn countries                # a table of what's out there right now
vpn servers JP --limit 10    # drill into one country — cities, ISPs, ping, speed
sudo vpn connect             # or skip browsing entirely: connect to the best server
vpn status                   # where did my traffic end up? (exit IP + city)
sudo vpn disconnect          # clean teardown: process, routes, DNS
```

Connecting needs `sudo` because VPN interfaces, routes and DNS policies are system
state. It prints the exact command to copy-paste if you forget.

## Interactive menu

Run `vpn` with no arguments (or `vpn intro`):

```
  █   █ ███  █   █ ███  ████ █   █   ← the name drawn in big mono
  █   █ █  █ ██  █ █  █ █  █  █ █      block letters inside a red band
  █   █ ███  █ █ █ ███  █  █    █     (5 rows, bold white on solid red;
   █ █  █    █  ██ █  █ █  █  █ █      double-wide on very wide screens)
    █   █    █   █ ███  ████ █   █
  ────────────────────────────────────────────────
  vpnbox 1.0.0-beta · by sajadinmaker — github.com/sajadinmaker

  ┌───────────────────────────────────────────────────────────┐
  │ ● not connected   your IP: 112.34.5.6                     │
  │ Bengaluru, India · 214 live servers · 14 countries        │
  │ list refreshed 5 min ago                                  │
  └───────────────────────────────────────────────────────────┘

   1  Connect to the fastest server
   2  Choose a country or city
   3  Appear near a platform office (Instagram, X, YouTube…)
   4  Refresh the live server list
   5  Disconnect
   6  Quit

  ↑/↓ select · 1–6 quick · Enter run · q quit
```

The **VPNBOX** name is drawn as large mono block letters inside a red band
(`VPNBOX_PLAIN=1` falls back to a plain letterspaced strip). The layout is
responsive from 46 to 120 columns: narrow screens stack the status facts
and shorten menu labels instead of overflowing.

Navigation is keyboard-driven: ↑/↓ moves the highlight, Enter runs it,
keys 1–6 jump straight to a task, q quits. Dialogs behave the same
everywhere: **Enter commits the default shown in the prompt**, **Esc
backs out**, and typed-ahead input is drained so a fast number+Enter
burst can never answer the next dialog by accident. Pressing **1**
connects to the fastest server directly; **3** walks through the
platform/office picker one numbered question at a time. In pipes or CI
the bare run prints a plain numbered command list and exits 0.

## Connection options

Everything that shapes *where* you connect is an option to `vpn connect`:

```bash
sudo vpn connect US                       # positional shortcut: code or name
sudo vpn connect --country Japan --city Tokyo
sudo vpn connect --country US --proto tcp # pin the transport if you have to
sudo vpn connect CA                       # no live CA pool? it tells you, and offers:
sudo vpn connect CA --nearest             # …the closest country that *is* alive
```

You never pick a server by hand unless you want to: after `--country`/`--city`,
ranking is automatic (more below), and if a volunteer server refuses to handshake,
vpnbox fails fast on it and tries the next best candidate, up to three times by
default (`--max-tries N` to change). Once you've browsed with `vpn servers JP`,
you can also pin an exact entry with `--index 3`, or skip a flaky one with
`--skip 1`. When vpnbox lands, it prints the exit IP and its city/ISP so you
can see exactly where you appear from; if that country doesn't match what you
asked for, it warns you rather than misreporting.

## Appear near a platform office

vpnbox knows the worldwide office locations of **29 platforms — 239 offices
across 31 countries** and can connect you through a server close to one:

```bash
vpn sites                                 # the whole catalogue, one row per platform
vpn sites --site meta                     # every Meta office + nearest live server to each
sudo vpn connect --site meta              # near Meta's primary HQ (Menlo Park, CA)
sudo vpn connect --site meta --office Seoul
sudo vpn connect --site meta --office all # nearest to ANY of its 29 offices worldwide
sudo vpn connect --site line              # LINE: Tokyo/Bangkok; kakaotalk → Seoul; telegram → Dubai
```

Notes:

- **`--site` alone means the primary HQ.** For Meta that's 1601 Willow Road,
  Menlo Park; for YouTube, 901 Cherry Avenue, San Bruno. Predictable by design.
- **`--office` picks any other location.** Substring match — `Dublin`, `Mumbai`,
  `Toronto` — with the list visible via `vpn sites --site <name>`.
  `--office all` ranks by *nearest to any office anywhere*, which is handy when
  your region's volunteers are thin.
- **Addresses are geocoded precisely**, not guessed: on first use vpnbox asks the
  OpenStreetMap Nominatim service for each office's exact coordinates (one polite
  request per second, their policy), then caches them forever in
  `~/.cache/vpnbox/offices.json`. The `◈` marker in `vpn sites` output means
  "OSM-precise"; everything degrades gracefully to city-level coordinates if OSM
  is unreachable. `vpn sites --recache` re-runs the whole precision pass.
- **Distance is balanced with reachability.** Offices are bucketed into distance
  tiers around the server (≤40, ≤150, ≤500, ≤1500 km); within a tier, ping,
  speed and UDP preference decide. The closest office therefore still resolves
  to a live, responsive server — never a close-but-dead one.

**The platforms**: meta, instagram, threads, x, whatsapp, google, youtube,
microsoft, linkedin, tiktok, snapchat, discord, reddit, pinterest, apple,
telegram, signal, tumblr, viber, line, kakaotalk, wechat, netflix, twitch,
slack, zoom, quora, spotify, vk.

Appearing near an office changes **your exit IP and its reported location**
only — it is not a way around a platform's own server-side policies.

## How it works

The whole implementation is a single readable file:

- `vpn refresh` downloads VPN Gate's official CSV API
  (`https://www.vpngate.net/api/iphone/`), parses the embedded OpenVPN profiles for
  every entry, and enriches the strongest ~300 servers with city/ISP/lat-lon
  geolocation through ip-api.com's free batch endpoint — receiving only cached
  server addresses, never anything of yours. Cache lives in `~/.cache/vpnbox/servers.json`.
- On connect, vpnbox builds an OpenVPN config from the winning server's profile:
  real `remote`/`proto`, Windows-only directives stripped, sane ciphers appended,
  and the `update-systemd-resolved` up/down script wired in so pushed DNS options
  are applied through systemd-resolved. The daemon runs with its PID in
  `/run/vpnbox.pid` and its log in `/var/log/vpnbox.log`.
- **Full-tunnel enforcement is unconditional:** `redirect-gateway def1` and
  `block-ipv6` are always appended — some volunteer servers forget to push
  complete routes, and these two lines make that forgetfulness harmless on IPv4
  while disabling IPv6 passthrough entirely. (Comfortable with IPv6 leaks? Delete
  the `block-ipv6` line in `vpnbox.py`.)
- **Success detection can't be fooled by history:** the daemon log file is shared
  between sessions, so vpnbox only ever reads bytes *appended after* its own
  launch. A stale "Initialization Sequence Completed" from yesterday can never
  count as today's handshake.
- UDP servers are preferred in ranking; volunteer TCP relays drop out more often.

## Limitations

- **These servers are volunteers.** The map changes every hour: pools in
  JP/KR/TH/US are usually strong; individual countries appear and disappear with
  the volunteers behind them. Run `vpn refresh` before connecting.
- **Logging is defined per operator.** Each relay decides its logging
  policy; VPN Gate ships that field and vpnbox stores it
  (`jq '.servers[] | .log' ~/.cache/vpnbox/servers.json`). Read it before doing
  anything sensitive.
- **There is no kill switch.** If OpenVPN dies, traffic resumes through your
  normal connection. If that matters, add a firewall policy (e.g. ufw allow
  outbound only on `tun0`) or run your own WireGuard on a VPS — one country,
  but fully under your control.
- **A free third-party geolocation service** (ip-api.com) does the city
  enrichment; if it's slow or absent, server listing still works, just without
  city names.
- Per VPN Gate's terms of use, their attribution must travel with any tool that
  reads their list — it does, in `LICENSE`.

## Debugging a connection

When a connect fails in a way you don't understand, run OpenVPN in the foreground
with maximum verbosity and read what actually happened:

```bash
# 1) build a debug config from the best current pool (from the vpnbox folder)
python3 - <<'EOF'
import vpnbox as v
servers = v.load_cache()['servers']
pool = [x for x in servers if x['cc'] == 'JP'] or servers
r = min(pool, key=v.rank)
open('/tmp/vpnbox-debug.ovpn', 'w').write(v.build_conf(r))
print(r['host'], r['ip'], f"{r['proto']}/{r['port']}")
EOF

# 2) run it in the foreground, watch the log, stop after ~15 s
sudo bash -c 'openvpn --config /tmp/vpnbox-debug.ovpn --verb 6 \
  > /tmp/vpnbox-debug.log 2>&1 & sleep 15; kill -INT $!'
grep -aE "Control Channel|Initialization|PUSH|P_CONTROL|update-systemd-resolved" \
  /tmp/vpnbox-debug.log
rm -f /tmp/vpnbox-debug.ovpn /tmp/vpnbox-debug.log
```

A healthy run shows a TLS 1.3 control channel, a `PUSH` block with your address
and DNS options, the `/1`-split routes entering the table, and
`update-systemd-resolved` installing DNS on `tun0` — then SIGINT exits cleanly
with code 0. A run with repeated `P_CONTROL_HARD_RESET_CLIENT_V2` writes and *no
reads* means the server simply isn't answering; the normal `vpn connect` path
would have already failed it over to the next candidate.

Recent daemon activity is visible at any time: `tail -40 /var/log/vpnbox.log`.

## Developing

The whole program is `vpnbox.py` — designed to be read, not just run. The test
suite is hermetic (no network, no root), and CI runs it on every push across
Python 3.9 → 3.13; pushing a `v*` tag builds and publishes the release
automatically.

```bash
make check                 # syntax: compileall + bash -n
make test                  # hermetic unit tests (site DB, geography, ranking, config)
make dist                  # build the release tarball + SHA256SUMS locally
```

See `CONTRIBUTING.md` for the design rules (one file, stdlib-only, no accounts)
and the release checklist.

## Attribution

Server list and relay profiles by the **VPN Gate Academic Experiment**,
University of Tsukuba (<https://vpngate.net>). Geocoding by OpenStreetMap
contributors via Nominatim, and IP geolocation by ip-api.com. OpenVPN is a
registered trademark of OpenVPN Inc.; vpnbox invokes it, it is not part of it.
vpnbox is a client only — it operates no servers of its own.

vpnbox is MIT-licensed; see `LICENSE` for the full text and third-party notices.
