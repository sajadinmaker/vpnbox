# android/ — vpnbox app

Compose app port of the `vpnbox` CLI. Same data semantics, same aesthetic.

## Status

- **Data layer**: semantic twin of the CLI — VPN Gate fetch/parse, `rank()`
  ordering, `select_servers()` narrowing, `check_ping_settings()`, `validate_args()`,
  `backoff_seconds()` (30 s doubling, 300 s cap), atomic cache/session writes,
  disconnect tombstones. Covered by JVM unit tests (`./gradlew testDebugUnitTest`).
- **UI**: the reel's language — pixel wordmark band, terminal panel with
  traffic lights and right tag, `● connected` status rows, ▸+number action
  rows, chips `connect → watch → kill → recovered`, segment progress bar,
  caption blocks (`04 · RECOVER / Back in 4 seconds`).
- **Engine seam**: `TunnelEngine` interface. Today `SimulatedEngine` drives the
  UI (real pacing, kill/recovery cycles reachable from the chips row).
  `VpnboxVpnService` (manifest-registered, specialUse foreground) is the
  skeleton where the OpenVPN core (ics-openvpn) plugs in — swap the engine
  once the core lands; the UI, watchdog, and tombstone logic do not change.
- **Skills**: curated agent skills from github.com/android/skills vendored
  under `.skills/` (android-cli, testing-setup, edge-to-edge, permissions
  security, compose theming, compose performance).

## Build

```bash
cd android && ./gradlew testDebugUnitTest assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

The `android` CLI (dl.google.com/android/cli) can create AVDs, install APKs,
and drive UIs without Android Studio.

## Known divergence (intentional)

`select_servers()` in the Python CLI leaves the unfiltered list in place when
a `--city` filter matches nothing — the CLI then connects to the narrowed-out
country anyway. The app refuses: no match means no connection, with a
readable "city not found … known: …" message. (Candidate fix for the CLI side.)
