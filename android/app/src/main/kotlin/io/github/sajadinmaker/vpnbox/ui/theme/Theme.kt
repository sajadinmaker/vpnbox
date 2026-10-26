package io.github.sajadinmaker.vpnbox.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val VpnboxColors = darkColorScheme(
    primary = Red,
    onPrimary = Bg,
    secondary = Green,
    onSecondary = Bg,
    tertiary = Yellow,
    background = Bg,
    onBackground = White,
    surface = Panel,
    onSurface = White,
    outline = PanelBorder,
    inverseSurface = RedDeep,
)

@Composable
fun VpnboxTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = VpnboxColors,
        typography = MaterialTheme.typography,
        content = content,
    )
}
