package io.github.sajadinmaker.vpnbox.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val BrandDark = darkColorScheme(
    primary = RedPrimary,
    onPrimary = OnPrimary,
    primaryContainer = PrimaryContainer,
    onPrimaryContainer = OnPrimaryContainer,
    secondary = GreenSecondary,
    onSecondary = OnSecondary,
    secondaryContainer = SecondaryContainer,
    onSecondaryContainer = OnSecondaryContainer,
    tertiary = YellowTertiary,
    onTertiary = OnTertiary,
    tertiaryContainer = TertiaryContainer,
    onTertiaryContainer = OnTertiaryContainer,
    error = Error,
    onError = OnError,
    errorContainer = ErrorContainer,
    onErrorContainer = OnErrorContainer,
    background = BackgroundN,
    onBackground = OnBackgroundN,
    surface = SurfaceN,
    onSurface = OnSurfaceN,
    surfaceVariant = SurfaceVariantN,
    onSurfaceVariant = OnSurfaceVariantN,
    outline = OutlineN,
    outlineVariant = OutlineVariantN,
    surfaceDim = SurfaceDimN,
    surfaceBright = SurfaceBrightN,
    surfaceContainerLowest = SurfaceContainerLowestN,
    surfaceContainerLow = SurfaceContainerLowN,
    surfaceContainer = SurfaceContainerN,
    surfaceContainerHigh = SurfaceContainerHighN,
    surfaceContainerHighest = SurfaceContainerHighestN,
    inverseSurface = InverseSurfaceN,
    inverseOnSurface = InverseOnSurfaceN,
    inversePrimary = InversePrimaryN,
    scrim = ScrimN,
)

private val BrandLight = lightColorScheme(
    primary = PrimaryL,
    onPrimary = OnPrimaryL,
    primaryContainer = PrimaryContainerL,
    onPrimaryContainer = OnPrimaryContainerL,
    secondary = SecondaryL,
    onSecondary = OnSecondaryL,
    secondaryContainer = SecondaryContainerL,
    onSecondaryContainer = OnSecondaryContainerL,
    tertiary = TertiaryL,
    onTertiary = OnTertiaryL,
    tertiaryContainer = TertiaryContainerL,
    onTertiaryContainer = OnTertiaryContainerL,
    error = ErrorL,
    onError = OnErrorL,
    errorContainer = ErrorContainerL,
    onErrorContainer = OnErrorContainerL,
    background = BackgroundL,
    onBackground = OnBackgroundL,
    surface = SurfaceL,
    onSurface = OnSurfaceL,
    surfaceVariant = SurfaceVariantL,
    onSurfaceVariant = OnSurfaceVariantL,
    outline = OutlineL,
    outlineVariant = OutlineVariantL,
    surfaceDim = SurfaceDimL,
    surfaceBright = SurfaceBrightL,
    surfaceContainerLowest = SurfaceContainerLowestL,
    surfaceContainerLow = SurfaceContainerLowL,
    surfaceContainer = SurfaceContainerL,
    surfaceContainerHigh = SurfaceContainerHighL,
    surfaceContainerHighest = SurfaceContainerHighestL,
    inverseSurface = InverseSurfaceL,
    inverseOnSurface = InverseOnSurfaceL,
    inversePrimary = InversePrimaryL,
    scrim = ScrimL,
)

/** Material 3 theme: Material You dynamic color on Android 12+, brand
 *  light/dark schemes otherwise. Follows the system dark-mode setting. */
@Composable
fun VpnboxTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        }
        darkTheme -> BrandDark
        else -> BrandLight
    }
    MaterialTheme(
        colorScheme = colorScheme,
        content = content,
    )
}
