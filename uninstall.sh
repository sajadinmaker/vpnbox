#!/usr/bin/env bash
# vpnbox uninstaller — pass --purge to also remove runtime state
# Usage:  sudo ./uninstall.sh [--purge] [PREFIX]   (PREFIX defaults to /usr/local)
set -uo pipefail

PURGE=0
PREFIX="/usr/local"
for a in "$@"; do
    case "$a" in
        --purge) PURGE=1 ;;
        *) PREFIX="$a" ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "uninstalling from $PREFIX needs root:  sudo ./uninstall.sh" >&2
    exit 2
fi

rm -f "$PREFIX/bin/vpn"
echo "removed: $PREFIX/bin/vpn"

if [ "$PURGE" -eq 1 ]; then
    rm -f /var/log/vpnbox.log /run/vpnbox.pid /var/tmp/vpnbox.meta
    echo "runtime state purged (/var/log/vpnbox.log, /run/vpnbox.pid, /var/tmp/vpnbox.meta)"
    echo "user caches kept in ~/.cache/vpnbox — delete manually if you want a fully clean slate"
fi

echo "vpnbox uninstalled"
