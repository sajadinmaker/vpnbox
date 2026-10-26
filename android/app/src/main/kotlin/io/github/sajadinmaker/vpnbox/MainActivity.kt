package io.github.sajadinmaker.vpnbox

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.Crossfade
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.sajadinmaker.vpnbox.ui.CountrySheet
import io.github.sajadinmaker.vpnbox.ui.HomeAction
import io.github.sajadinmaker.vpnbox.ui.HomeScreen
import io.github.sajadinmaker.vpnbox.ui.TerminalScreen
import io.github.sajadinmaker.vpnbox.ui.theme.VpnboxTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VpnboxTheme {
                val vm: VpnViewModel = viewModel()
                LaunchedEffect(Unit) { vm.start() }
                val screen by vm.screen.collectAsState()
                val home by vm.home.collectAsState()
                val terminal by vm.terminal.collectAsState()
                val countries by vm.countries.collectAsState()
                var picking by remember { mutableStateOf(false) }

                Crossfade(targetState = screen, label = "screen") { s ->
                    if (s == Screen.TERMINAL) {
                        TerminalScreen(
                            ui = terminal,
                            onBack = { vm.dismissAndGoHome() },
                            onKill = { vm.killTunnel() },
                        )
                    } else {
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
