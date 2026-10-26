# android/ — vpnbox app

Compose app port of the `vpnbox` CLI. Same data semantics, Material 3 UI.

## Status

- **Data layer**: semantic twin of the CLI — VPN Gate fetch/parse, `rank()`
  ordering, `select_servers()` narrowing, `check_ping_settings()`, `validate_args()`,
  `backoff_seconds()` (30 s doubling, 300 s cap), atomic cache/session writes,
  disconnect tombstones. Covered by JVM unit tests (`./gradlew testDebugUnitTest`).
- **UI**: Material 3 (dark, brand-red primary) — Scaffold + TopAppBar navigation,
  status hero card (green secondary-container state when connected), metric stat
  cards, icon list-row actions, message banners, animated screen transitions,
  M3 log card, linear progress, and standard buttons. The reel-era pixel
  wordmark survives in the launcher icon only.
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
