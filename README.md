# vpnbox

**Free VPN for Linux — no account, no key, no payment.**

`v1.0.0-beta` · one Python file, stdlib only · [sajadinmaker](https://github.com/sajadinmaker)

vpnbox is a command-line VPN client built on [VPN Gate](https://vpngate.net), the
volunteer relay experiment run by the University of Tsukuba. It fetches the live
server list, ranks it by reachability and speed, and connects through OpenVPN with
a full tunnel and leak-safe DNS.

## Requirements

Linux, OpenVPN 2.5+, systemd-resolved, Python 3.8+. `install.sh` checks all of it.

## Install

```bash
tar -xzf vpnbox-1.0.0-beta.tar.gz
cd vpnbox-1.0.0-beta
sudo ./install.sh
```

Uninstall: `sudo ./uninstall.sh` (`--purge` also removes runtime state).

## Quick start

```bash
vpn refresh                  # fetch the live server list (~15 s)
vpn countries                # what's available right now
sudo vpn connect             # best server, anywhere
vpn status                   # exit IP + city
sudo vpn disconnect          # clean teardown
```

## Interactive menu

Bare `vpn` (or `vpn intro`) opens a TUI:

- ↑/↓ selects, Enter runs, **1–6** run instantly, `q` quits
- Enter commits the default shown in the prompt, Esc backs out; typed-ahead
  input is drained, so a fast number+Enter burst can't answer a dialog
- 1 fastest · 2 country/city · 3 platform office · 4 refresh · 5 disconnect · 6 quit
- responsive from 46 to 120 columns; piped runs print a plain numbered list

## Connection options

```bash
sudo vpn connect US                          # positional: code or name
sudo vpn connect --country Japan --city Tokyo
sudo vpn connect CA --nearest                # closest country that's alive
sudo vpn connect --country US --proto tcp    # pin the transport
```

Dead volunteer servers fail over automatically (3 tries by default,
`--max-tries N`), and the exit IP is verified against what you asked for. Pin an
exact entry with `--index N`, skip a flaky one with `--skip N`.

## Appear near a platform office

29 platforms, 239 offices, 31 countries — connect through a server close to one:

```bash
vpn sites                                   # the catalogue
vpn sites --site meta                       # every Meta office + nearest live server
sudo vpn connect --site meta                # near Meta HQ (Menlo Park, CA)
sudo vpn connect --site meta --office Seoul
sudo vpn connect --site meta --office all   # nearest to any office worldwide
```

`--site` alone means the primary HQ; `--office` substring-matches any office.
Offices are geocoded via OpenStreetMap (cached in `~/.cache/vpnbox/offices.json`);
ranking prefers live, fast servers within each distance tier. Hitting an office
changes your exit IP and its reported location only — not server-side policies.

## How it works

- Server list from VPN Gate's CSV API; city/ISP enrichment via ip-api.com
  (batched, only cached server IPs are sent). Cache: `~/.cache/vpnbox/servers.json`.
- Per-server OpenVPN config; `redirect-gateway def1` and `block-ipv6` always
  appended; DNS applied through `update-systemd-resolved`. PID in `/run/vpnbox.pid`,
  log in `/var/log/vpnbox.log`.
- Success detection reads only log bytes appended after launch, so a stale
  handshake can never count. UDP preferred over TCP.

## Limitations

- These are volunteer servers — the pool changes hourly. Run `vpn refresh` first.
- Logging is defined per operator: `jq '.servers[] | .log' ~/.cache/vpnbox/servers.json`.
- No kill switch: if OpenVPN dies, traffic resumes via your normal connection.
- Without ip-api.com, listings work but lose city names.

## Developing

`make check` (syntax), `make test` (hermetic — no network, no root), `make dist`
(release tarball). CI runs Python 3.9–3.13. See `CONTRIBUTING.md`.

## Attribution & license

Server list and relay profiles by the **VPN Gate Academic Experiment**, University
of Tsukuba. Geocoding by OpenStreetMap/Nominatim; IP geolocation by ip-api.com.
OpenVPN is a registered trademark of OpenVPN Inc. vpnbox operates no servers.
MIT-licensed — see `LICENSE`.
