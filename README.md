# vpnbox — free public-VPN manager for Linux

**v1.0.0-beta1** (2026-10-20) — single file, stdlib-only Python 3.

A from-scratch VPN client/manager (single file, stdlib-only Python) built on top of
**VPN Gate** — the open academic VPN relay experiment of the University of Tsukuba
(<https://vpngate.net>). It lists volunteer-run public VPN servers **live** (no account,
no key, no payment), adds **city/ISP geolocation**, and connects via OpenVPN while
keeping system DNS on systemd-resolved (no DNS leaks).

## Install / uninstall

```bash
cd vpnbox-1.0.0-beta1          # extracted release, or this repo dir
sudo ./install.sh              # deps check + /usr/local/bin/vpn + verify
sudo ./uninstall.sh            # remove the command
sudo ./uninstall.sh --purge    # also wipe runtime state files
rm -rf ~/.cache/vpnbox         # optional: drop server/office caches
```

## Daily use

```bash
vpn refresh         # pull live list + resolve cities (run when list feels stale)
vpn countries       # what's online right now  (vpn countries --all)
vpn servers JP      # servers in Japan, with cities/ISP/ping/speed
vpn status          # connection state + exit IP/location
vpn ip              # where your traffic appears from today
```

Connecting needs root (VPN interfaces are a system resource):

```bash
sudo vpn connect                          # best reachable server anywhere
sudo vpn connect US                       # positional: code or country name
sudo vpn connect --country Japan --city Tokyo
sudo vpn connect --country US --proto tcp # force a transport
sudo vpn connect CA --nearest             # country w/o live pool → closest one
vpn disconnect                            # terminates + cleans up
```

Platform HQ / area shortcuts ("appear near" Meta, X, WhatsApp, TikTok …):

```bash
vpn sites                       # 29 platforms, 224 offices across 31 countries
vpn sites --site meta           # ALL Meta offices + nearest live server for each
vpn sites --site meta --geocode # OSM-precise geocode of Meta's offices (cached)
vpn sites --recache             # re-geocode every office of every platform
sudo vpn connect --site meta    # nearest live server to the PRIMARY HQ (Menlo Park)
sudo vpn connect --site x       # X/Twitter HQ → San Francisco
sudo vpn connect --site meta --office Seattle    # pick a specific office
sudo vpn connect --site meta --office all        # nearest to ANY office worldwide
sudo vpn connect --site line    # Tokyo/Bangkok; kakaotalk=Seoul, telegram=Dubai …
```

- `--site X` targets the **primary HQ** (e.g. Meta → Menlo Park, CA).
- `--office CITY` narrows to any single office (substring match — Dublin,
  Mumbai, Toronto, …); `--office all` ranks by nearest-any-office.
- **Accuracy**: office addresses are geocoded via OpenStreetMap Nominatim
  (◈-precise, cached in `~/.cache/vpnbox/offices.json`); servers carry
  ip-api lat/lon. Ranking uses distance tiers (≤40/≤150/≤500/≤1500 km) —
  within a tier, ping/speed/UDP wins — so "near the office" also means
  "fast and actually alive". Connect triggers a quiet precision pass for
  the offices in use (first time only).
- Platforms: meta, instagram, threads, x, whatsapp, google, youtube,
  microsoft, linkedin, tiktok, snapchat, discord, reddit, pinterest, apple,
  telegram, signal, tumblr, viber, line, kakaotalk, wechat, netflix, twitch,
  slack, zoom, quora, spotify, vk.

`vpn connect` auto-retries the next best candidates (default 3) if a volunteer
server refuses to handshake, and prints the exit IP on success so you can confirm
the country you actually appear from. If the cache is >30 min old it refreshes
automatically first (the volunteer pool churns fast).

## How it works

- `vpn refresh` downloads the official CSV API of VPN Gate
  (`https://www.vpngate.net/api/iphone/`), parses the embedded OpenVPN profiles,
  and enriches the top ~300 servers with city/ISP/lat-lon data via the free
  ip-api.com batch endpoint. Cache: `~/.cache/vpnbox/servers.json`.
- `connect` reads `remote`/`proto` from each profile, strips Windows-only
  directives, appends sane ciphers and (if installed) the
  `openvpn-systemd-resolved` up/down script so pushed DHCP DNS options land in
  systemd-resolved, then runs `openvpn --daemon` with PID/log in
  `/run/vpnbox.pid` / `/var/log/vpnbox.log`.
- **Full-tunnel enforcement**: vpnbox always appends `redirect-gateway def1`
  and `block-ipv6` — some volunteer servers forget to push full-tunnel routes;
  these lines make leaking impossible for IPv4 and disable IPv6 passthrough
  (delete the `block-ipv6` line in `vpnbox.py` to allow v6).
- **Success detection is session-scoped**: the daemon log is append-shared, so
  `wait_ready()` only inspects bytes appended after launch — a stale OK line
  from a previous session can never fake a successful handshake (this exact
  bug was caught in live testing on 2026-10-20).
- UDP servers are preferred in ranking (volunteer TCP relays drop more often).

## Honest limitations

- **Servers are volunteers**: counts/countries swing over the day (typically a
  few dozen to a few hundred servers across 10–60 countries; big pools in
  JP/KR/TH/US). Some restrict or log traffic — the `LogType` field from VPN Gate
  is stored in the cache (`jq '.servers[] | .log' ~/.cache/vpnbox/servers.json`).
- Countries appear and disappear with their volunteers. On 2026-10-20: US and
  PH had live entries (some temporarily unreachable), **CA had none** — when
  that happens `vpn connect CA` prints the closest live pool and offers
  `--nearest` to bridge to it. Run `vpn refresh` periodically.
- **No kill switch**: traffic falls back to your normal connection if OpenVPN
  dies. If you need one, add a firewall rule (e.g. ufw policy) or consider
  WireGuard on your own VPS (~$5/mo, a single country, but under your control).
- City enrichment uses a free third-party geolocation service (ip-api.com);
  it receives only cached server IPs, not any personal data.
- Per VPN Gate's terms when you use their list, keep the attribution noted here.

## Debugging a connection (verb 6, foreground)

Verified working debug recipe — shows the full TLS handshake, server PUSH options,
route installs and DNS script activity:

```python
# 1) generate a debug config file from the best current server
python3 - <<'EOF'
import sys; sys.path.insert(0, '/home/sajad/vpnbox')
import vpnbox as v
s = sorted(v.load_cache()['servers'], key=v.rank)
r = [x for x in s if x['cc']=='JP'][0]
open('/tmp/vpnbox-debug.ovpn','w',encoding='utf-8').write(v.build_conf(r))
print(r['host'], r['ip'], r['proto']+'/'+r['port'])
EOF
```

```bash
# 2) launch in the foreground and watch /tmp/vpnbox-debug.log
sudo bash -c 'openvpn --config /tmp/vpnbox-debug.ovpn --verb 6 \
  > /tmp/vpnbox-debug.log 2>&1 & sleep 14; kill -INT $!'
grep -aE "Control Channel|PUSH|ARP|Initialization|update-systemd-resolved" /tmp/vpnbox-debug.log
rm -f /tmp/vpnbox-debug.ovpn /tmp/vpnbox-debug.log   # when done
```

Reference run on 2026-10-20 (server `vpn537511968`, Tokyo, UDP/7610): TLSv1.3 control
channel (AES-256-GCM-SHA384, X25519), PUSH: `ifconfig 10.211.x.x`, two DNS options,
`redirect-gateway def1`, `/1-split routes installed via tun0`, DNS applied with
`SetLinkDNS(7 …)` → exit IP confirmed as Tokyo. SIGINT then exits code 0.

## Attribution

Server list by the VPN Gate Academic Experiment / University of Tsukuba.
vpnbox is a client only; it runs no servers of its own.
