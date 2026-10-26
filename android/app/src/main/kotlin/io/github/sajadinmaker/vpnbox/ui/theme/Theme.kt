package io.github.sajadinmaker.vpnbox.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val VpnboxScheme = darkColorScheme(
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

@Composable
fun VpnboxTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = VpnboxScheme,
        content = content,
    )
}
