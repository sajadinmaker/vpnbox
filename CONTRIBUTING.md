# Contributing to vpnbox

Thanks for helping. vpnbox's design constraints are the whole product — please
read these before opening a pull request.

## The rules of the house

1. **One file.** The entire application lives in `vpnbox.py`, standard library
   only. No pip dependencies, no imports beyond the stdlib. A user should be
   able to read the whole program on a train.
2. **No accounts, ever.** VPN Gate is anonymous and key-free; vpnbox must stay
   that way.
3. **Fail loudly, fail fast.** Volunteer servers churn. Never paper over a
   failure — surface it (and then auto-failover if a *better* candidate exists).
4. **Polite to shared infrastructure.** Nominatim: max 1 request/second, a real
   User-Agent. ip-api: batch endpoint only (100 IPs/request).
5. **Honest status output.** Exit IP is always printed after a connect; country
   mismatch is a warning, never a silent success.

## Development flow

```bash
git clone https://github.com/sajadinmaker/vpnbox && cd vpnbox
make check                 # syntax: python compile + bash -n
make test                  # hermetic unit tests (no network, no root)
sudo ./install.sh          # installs ./vpnbox.py as /usr/local/bin/vpn
```

Live-fire testing (needs root, hits the real VPN Gate network):

```bash
sudo vpn connect --country JP          # or any --site/--office target
vpn status && sudo vpn disconnect
```

## Release checklist (maintainers)

1. Bump `APP_VERSION` in `vpnbox.py` — it is the single source of truth.
2. Add a matching `## X.Y.Z — date` section to `CHANGELOG.md`
   (`test_version_single_source_of_truth` enforces this).
3. Update `README.md` if behavior changed.
4. Commit, tag `vX.Y.Z`, push both: `git push origin main vX.Y.Z`
   — the `release` workflow builds the tarball, checksums it, and attaches
   both to the GitHub release automatically.

## Style

- Python: stdlib, 4-space indent, f-strings, `def name(...)` with docstrings
  on non-obvious functions (match the existing file).
- Shell: `set -euo pipefail`, tab-free indents of 4.
- Commits: imperative mood, one logical change per commit.
