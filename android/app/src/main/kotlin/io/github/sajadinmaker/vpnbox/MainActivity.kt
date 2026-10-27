package io.github.sajadinmaker.vpnbox

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.Crossfade
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.sajadinmaker.vpnbox.data.ThemeMode
import io.github.sajadinmaker.vpnbox.ui.AboutScreen
import io.github.sajadinmaker.vpnbox.ui.CountrySheet
import io.github.sajadinmaker.vpnbox.ui.HomeAction
import io.github.sajadinmaker.vpnbox.ui.HomeScreen
import io.github.sajadinmaker.vpnbox.ui.SettingsScreen
import io.github.sajadinmaker.vpnbox.ui.TerminalScreen
import io.github.sajadinmaker.vpnbox.ui.theme.VpnboxTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val vm: VpnViewModel = viewModel()
            val settings by vm.settings.collectAsState()
            val systemDark = isSystemInDarkTheme()
            VpnboxTheme(
                darkTheme = when (settings.themeMode) {
                    ThemeMode.SYSTEM -> systemDark
                    ThemeMode.LIGHT -> false
                    ThemeMode.DARK -> true
                },
                dynamicColor = settings.dynamicColor,
            ) {
                LaunchedEffect(Unit) { vm.start() }
                val screen by vm.screen.collectAsState()
                val home by vm.home.collectAsState()
                val terminal by vm.terminal.collectAsState()
                val countries by vm.countries.collectAsState()
                var picking by remember { mutableStateOf(false) }

                BackHandler(enabled = screen != Screen.HOME) { vm.onSystemBack() }

                Crossfade(targetState = screen, label = "screen") { s ->
                    when (s) {
                        Screen.TERMINAL -> TerminalScreen(
                            ui = terminal,
                            onBack = { vm.dismissAndGoHome() },
                            onKill = { vm.killTunnel() },
                        )
                        Screen.SETTINGS -> SettingsScreen(
                            settings = settings,
                            onBack = { vm.dismissAndGoHome() },
                            onThemeMode = { vm.setThemeMode(it) },
                            onDynamicColor = { vm.setDynamicColor(it) },
                        )
                        Screen.ABOUT -> AboutScreen(onBack = { vm.dismissAndGoHome() })
                        else -> {
                            HomeScreen(
                                ui = home,
                                onAction = { action ->
                                    when (action) {
                                        HomeAction.ConnectFast -> vm.connect(null, null)
                                        HomeAction.PickCountry -> {
                                            vm.rebuildCountries()
                                            picking = true
                                        }
                                        HomeAction.Refresh -> vm.refresh()
                                        HomeAction.Disconnect -> vm.disconnect()
                                        HomeAction.Settings -> vm.goSettings()
                                        HomeAction.About -> vm.goAbout()
                                    }
                                },
                            )
                            if (picking) {
                                CountrySheet(
                                    countries = countries,
                                    onPick = { pick ->
                                        picking = false
                                        vm.connect(pick.cc, null)
                                    },
                                    onDismiss = { picking = false },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
