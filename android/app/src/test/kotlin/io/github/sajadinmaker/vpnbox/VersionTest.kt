package io.github.sajadinmaker.vpnbox

import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * CONTRIBUTING rule 5: the version name lives only in
 * `android/app/build.gradle.kts` and reaches UI via `BuildConfig` — never
 * hard-coded. This locks the release-name shape so a stray rename breaks
 * the build instead of shipping.
 */
class VersionTest {

    @Test
    fun versionNameFollowsAndroidReleasePattern() {
        val pattern = Regex("""^\d+\.\d+\.\d+-beta\d+-android$""")
        assertTrue(
            "versionName '${BuildConfig.VERSION_NAME}' must follow X.Y.Z-betaN-android " +
                "(versionName in android/app/build.gradle.kts)",
            pattern.matches(BuildConfig.VERSION_NAME),
        )
    }

    @Test
    fun versionCodeIsPositive() {
        assertTrue(BuildConfig.VERSION_CODE >= 1)
    }
}
