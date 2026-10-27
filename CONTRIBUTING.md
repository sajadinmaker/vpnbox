# Contributing to vpnbox

Thanks for helping. The Android client is the product; these rules keep it
consistent. All Gradle commands run from the `android/` directory.

## Development setup

- JDK 17.
- Android SDK (API 36), or `sdk.dir` set in `android/local.properties`.
- A clone of this repository.

```bash
git clone https://github.com/sajadinmaker/vpnbox && cd vpnbox/android
./gradlew assembleDebug           # build a debug APK
./gradlew testDebugUnitTest       # unit tests
```

## Project rules

1. **Layered packages.** `VpnGate` fetches and parses relay data,
   `Domain`/data types hold pure logic — no Android imports where possible —
   `VpnViewModel` orchestrates, and `ui/` is Compose only. Pure logic changes
   get unit tests in `android/app/src/test/kotlin/`.
2. **Strings are resources.** UI strings live in `res/values/strings.xml`,
   never hardcoded in screens. The app must stay ready for per-app locales.
3. **Public data is fault-tolerant.** Malformed caches or server lists are
   ignored and refreshed, never crash. Network lookups (geo, fetch) are
   best-effort and may fail silently where the UX allows it.
4. **Country mismatch is visible.** If the exit-IP country does not match the
   selected server country, surface it to the user. Never silently succeed.
5. **One version source.** The version name lives in
   `android/app/build.gradle.kts` (`versionName`); the version-consistency
   unit test must stay green. Never hardcode the version string in UI screens
   or docs code.
6. **Release hygiene.** R8 minification stays on for release builds. Signing
   material exists only through gitignored `android/keystore.properties` —
   never commit keys or passwords.

## Releasing (maintainers)

1. Bump `versionName` and `versionCode` in `android/app/build.gradle.kts`.
2. Add a matching section to `CHANGELOG.md`.
3. Run:

   ```bash
   ./gradlew testDebugUnitTest assembleRelease bundleRelease
   ```

4. Create a git tag and push it. The `release` workflow builds, signs,
   checksums, and attaches the artifacts to the GitHub release.
5. On the GitHub release, rename the uploaded artifacts to
   `vpnbox-<version>.apk`, `vpnbox-<version>.aab`, and `SHA256SUMS`, and write
   a notes body.

Keep the CLI-era tag convention: `vX.Y.Z-name` (as in `v1.0.0-beta5-android`).

## Pull requests

- Keep them small; one logical change each.
- Include unit-test output for anything touching logic.
- Do not post screenshots containing real IP addresses in PRs or releases —
  redact or crop them.
