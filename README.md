# vpnbox

**A free VPN client for Linux.** No account, no key, no payment.

`v1.0.0-beta` · one Python file, standard library only · built by
[sajadinmaker](https://github.com/sajadinmaker)

vpnbox connects through the volunteer relays of
[VPN Gate](https://vpngate.net), the academic experiment run by the University
of Tsukuba. It fetches the live server list, ranks it by reachability and
speed, and connects through OpenVPN with a full tunnel and leak-safe DNS from
systemd-resolved.

## Install

```bash
tar -xzf vpnbox-1.0.0-beta.tar.gz
cd vpnbox-1.0.0-beta
sudo ./install.sh
```

`install.sh` checks the requirements: OpenVPN 2.5+, systemd-resolved, and
Python 3.8+. To remove vpnbox, run `sudo ./uninstall.sh`.

## Commands

Everything is a subcommand of `vpn`:

| Command | Result |
|---|---|
| `vpn refresh` | Fetches the live server list. |
| `vpn countries` | Shows what is reachable right now. |
| `vpn servers JP` | Lists one country: cities, ISPs, ping, speed. |
| `sudo vpn connect` | Connects to the fastest server. |
| `vpn status` | Shows the exit IP and its city. |
| `sudo vpn disconnect` | Stops the tunnel and restores routes and DNS. |

Connecting needs `sudo` because routes and DNS policies are system state. If a
server refuses to handshake, vpnbox fails fast and tries the next best
candidate, up to three attempts (`--max-tries N`). Pin a specific server with
`--index N` or skip a flaky one with `--skip N`.

## Pick a country, city, or transport

```bash
sudo vpn connect US                           # positional: code or name
sudo vpn connect --country JP --city chiyoda  # filter by city
sudo vpn connect CA --nearest                 # closest country that is alive
sudo vpn connect --country US --proto tcp     # pin the transport
```

After `--country` or `--city`, the ranking is automatic. If the exit IP lands
somewhere other than what you asked for, vpnbox says so.

## Interactive menu

Run `vpn` with no arguments to open the menu. ↑/↓ selects, Enter runs, keys
1–6 run entries directly, and `q` quits. The entries are the fastest server,
a country or city, a platform office, list refresh, disconnect, and quit.
Dialogs accept Enter for the default shown in the prompt and Esc to back out.
Typed-ahead input is drained, so a fast number-then-Enter burst cannot answer
the next dialog. The layout adapts from 46 to 120 columns, and a piped run
prints a plain numbered list. Set `VPNBOX_PLAIN=1` to render a plain banner.

## Appear near a platform office

vpnbox knows the offices of 29 platforms (239 offices in 31 countries) and can
route you through a server near one:

| Command | Result |
|---|---|
| `vpn sites` | Lists the platform catalogue. |
| `vpn sites --site meta` | Lists every Meta office and its nearest live server. |
| `sudo vpn connect --site meta` | Connects near the Meta HQ in Menlo Park. |
| `sudo vpn connect --site meta --office Seoul` | Connects near a specific office. |
| `sudo vpn connect --site meta --office all` | Connects nearest to any office worldwide. |

Office addresses are geocoded through OpenStreetMap and cached in
`~/.cache/vpnbox/offices.json`. Offices fall into distance tiers. Within a
tier, ping, speed, and UDP preference decide. The nearest office therefore
still resolves to a server that is alive.

## Limits

- The volunteers pool changes hourly. Run `vpn refresh` before you connect.
- Each operator sets its own logging policy. Read it with
  `jq '.servers[] | .log' ~/.cache/vpnbox/servers.json`.
- There is no kill switch. If OpenVPN exits abnormally, traffic resumes through
  your normal connection. Add a firewall rule if you need one (ufw, outbound
  only on `tun0`).
- City names come from ip-api.com. Listings work without it.

## Development

```bash
make check    # syntax checks
make test     # hermetic unit tests, no network and no root
make dist     # release tarball with checksums
```

CI runs the tests on Python 3.9 through 3.13. `CONTRIBUTING.md` covers the
design rules and the release checklist.

## Attribution

Server list and relay profiles: VPN Gate Academic Experiment, University of
Tsukuba. Geocoding: OpenStreetMap Nominatim. IP geolocation: ip-api.com.
OpenVPN is a registered trademark of OpenVPN Inc. vpnbox is a client only. It
operates no servers. Released under the MIT license. See `LICENSE`.
