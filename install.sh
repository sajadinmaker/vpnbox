#!/usr/bin/env bash
# vpnbox installer — see CHANGELOG.md for the release notes
# Usage:  sudo ./install.sh [PREFIX]     (PREFIX defaults to /usr/local)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' "$HERE/vpnbox.py")"
PREFIX="${1:-${PREFIX:-/usr/local}}"

if [ "$(id -u)" -ne 0 ]; then
    echo "installing to $PREFIX needs root:  sudo ./install.sh" >&2
    exit 2
fi

echo "== vpnbox $VERSION — installer"

MISSING=()
command -v python3 >/dev/null 2>&1 || MISSING+=(python3)
command -v openvpn >/dev/null 2>&1 || MISSING+=(openvpn)
if [ ! -e /etc/openvpn/update-systemd-resolved ] && \
   [ ! -e /usr/lib/openvpn/update-systemd-resolved ]; then
    MISSING+=(openvpn-systemd-resolved)
fi
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "missing dependencies: ${MISSING[*]}"
    echo "  Debian/Ubuntu:  sudo apt install ${MISSING[*]}"
    exit 3
fi
echo "deps ok: python3, openvpn $(openvpn --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1), systemd-resolved helper"

mkdir -p "$PREFIX/bin"
rm -f "$PREFIX/bin/vpn" 2>/dev/null || true   # replace dev symlinks/stale copies
install -m 0755 "$HERE/vpnbox.py" "$PREFIX/bin/vpn"
echo "installed: $PREFIX/bin/vpn"

"$PREFIX/bin/vpn" --version
echo
echo "quick start:"
echo "  vpn refresh                       # live list of public VPN servers"
echo "  vpn countries                     # what is reachable right now"
echo "  sudo vpn connect --country JP     # full-tunnel connect + auto-failover"
echo "  sudo vpn connect --site instagram --office Tokyo"
echo "  sudo vpn disconnect"
echo
echo "data source: VPN Gate (vpngate.net) — the academic relay experiment of the"
echo "University of Tsukuba. Volunteer servers change by the hour; failures are"
echo "normal and auto-retried."
