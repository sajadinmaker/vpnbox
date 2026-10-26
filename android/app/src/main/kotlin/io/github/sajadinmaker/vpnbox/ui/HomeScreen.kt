package io.github.sajadinmaker.vpnbox.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.sajadinmaker.vpnbox.HomeUi
import io.github.sajadinmaker.vpnbox.ui.theme.Dim
import io.github.sajadinmaker.vpnbox.ui.theme.Green
import io.github.sajadinmaker.vpnbox.ui.theme.Red
import io.github.sajadinmaker.vpnbox.ui.theme.RedDeep
import io.github.sajadinmaker.vpnbox.ui.theme.White

private data class Action(val num: String, val label: String, val enabled: Boolean)

@Composable
fun HomeScreen(
    ui: HomeUi,
    onAction: (HomeAction) -> Unit,
) {
    val actions = listOf(
        Action("1", "Connect fastest anywhere", ui.servers > 0),
        Action("2", "Choose a country or city", ui.servers > 0),
        Action("3", "Refresh the live server list", true),
        Action("4", "Disconnect", ui.connected),
    )
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(io.github.sajadinmaker.vpnbox.ui.theme.Bg)
            .systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 18.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.padding(top = 22.dp))
        VpnboxLogo(width = 250.dp)
        Spacer(Modifier.height(6.dp))
        Text(
            "github.com/sajadinmaker/vpnbox  ·  1.0.0-beta5-android",
            fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Dim,
        )
        Spacer(Modifier.height(18.dp))
        PanelChrome(
            title = "vpnbox · live tunnel",
            tag = if (ui.connected) "ONLINE" else "STANDBY",
        ) {
            Column {
                HomeStatusRows(ui)
                Spacer(Modifier.height(12.dp))
                for (a in actions) ActionRow(a, enabled = a.enabled) {
                    onAction(when (a.num) {
                        "1" -> HomeAction.ConnectFast
                        "2" -> HomeAction.PickCountry
                        "3" -> HomeAction.Refresh
                        else -> HomeAction.Disconnect
                    })
                }
                if (ui.message.isNotBlank()) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        ui.message,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        color = if (ui.message.startsWith("refresh failed")) Red
                                else if (ui.message.startsWith("refreshed")) Green
                                else Dim,
                    )
                }
            }
        }
        Spacer(Modifier.weight(1f))
        Text(
            "no account  ·  no key  ·  volunteer relays",
            fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Dim,
        )
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun HomeStatusRows(ui: HomeUi) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (ui.connected) "● connected" else "○ not connected",
                fontFamily = FontFamily.Monospace,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
                color = if (ui.connected) Green else Red,
            )
        }
        Text(
            if (ui.connected) "your tunnel is up — ${ui.geoLabel.ifBlank { "locating…" }}"
            else "your IP: ${ui.geoLabel.ifBlank { "unknown — offline?" }}",
            fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Dim,
            maxLines = 2,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(
                if (ui.servers > 0) "${ui.servers} live servers · ${ui.countries} countries"
                else "no server list yet — pick 3 to refresh",
                fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Dim,
            )
            if (ui.cacheAgeMin != null && ui.servers > 0) {
                Text(
                    "refreshed ${ageText(ui.cacheAgeMin)}",
                    fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Dim,
                )
            }
        }
    }
}

private fun ageText(min: Long?): String = when {
    min == null -> ""
    min < 1 -> "just now"
    min < 60 -> "$min min ago"
    else -> "${min / 60} h ago"
}

enum class HomeAction { ConnectFast, PickCountry, Refresh, Disconnect }

/** Intro-menu styling: red ▸, bold number, selection fill. */
@Composable
private fun ActionRow(a: Action, enabled: Boolean, onClick: () -> Unit) {
    val active = enabled
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(if (active) RedDeep.copy(alpha = 0.55f)
                        else androidx.compose.ui.graphics.Color.Transparent)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("▸", color = if (active) Red else Dim, fontSize = 14.sp)
        Spacer(Modifier.width(8.dp))
        Text(a.num, fontWeight = FontWeight.Bold, fontSize = 14.sp,
             color = if (active) White else Dim)
        Spacer(Modifier.width(10.dp))
        Text(a.label, fontSize = 14.sp,
             color = if (active) White else Dim,
             fontFamily = FontFamily.Monospace)
    }
}
