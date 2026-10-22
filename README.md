# vpnbox

Free VPN for Linux. No account, no key, no payment.

`v1.0.0-beta` · one Python file, stdlib only · [sajadinmaker](https://github.com/sajadinmaker)

Client for [VPN Gate](https://vpngate.net) — the University of Tsukuba volunteer
relay experiment. Fetches the live server list, ranks it by reachability, and
connects through OpenVPN with a full tunnel and systemd-resolved DNS.

## Install

```bash
tar -xzf vpnbox-1.0.0-beta.tar.gz
cd vpnbox-1.0.0-beta
sudo ./install.sh
```

Requires OpenVPN 2.5+, systemd-resolved, Python 3.8+. Remove with
`sudo ./uninstall.sh`.

## Commands

| | |
|---|---|
| `vpn refresh` | fetch the live server list |
| `vpn countries` | what's reachable right now |
| `vpn servers JP` | drill into one country |
| `sudo vpn connect` | connect to the fastest server |
| `sudo vpn connect --country JP --city chiyoda` | pick country / city |
| `sudo vpn connect CA --nearest` | closest country that is alive |
| `sudo vpn connect --site meta --office all` | nearest to any Meta office |
| `vpn status` | exit IP + location |
| `sudo vpn disconnect` | clean teardown |

`sudo` is required for routes and DNS. Dead servers fail over automatically
(3 tries); the reported exit IP is verified. Pin with `--index N`, skip with
`--skip N`.

## Menu

Bare `vpn` opens a TUI: ↑/↓ or 1–6 — `1` fastest · `2` country/city ·
`3` platform office · `4` refresh · `5` disconnect · `6` quit. Enter commits,
Esc backs out. `VPNBOX_PLAIN=1` renders a plain banner.

Offices: 29 platforms · 239 offices · 31 countries; geocoded via OpenStreetMap
and cached.

## Limitations

- The volunteer pool changes hourly — run `vpn refresh` first.
- Logging is per operator: `jq '.servers[] | .log' ~/.cache/vpnbox/servers.json`
- No kill switch: if OpenVPN dies, traffic resumes over your normal connection.
- City names need ip-api.com; listings work without it.

## Development

`make check` · `make test` · `make dist`. CI: Python 3.9–3.13. See
`CONTRIBUTING.md`.

Attribution: VPN Gate Academic Experiment, University of Tsukuba; geocoding by
OpenStreetMap/Nominatim; IP data by ip-api.com. MIT — see `LICENSE`.
