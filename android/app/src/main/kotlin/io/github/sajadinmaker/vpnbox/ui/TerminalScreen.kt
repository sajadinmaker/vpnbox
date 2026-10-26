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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.sajadinmaker.vpnbox.TerminalLine
import io.github.sajadinmaker.vpnbox.TerminalUi
import io.github.sajadinmaker.vpnbox.WatchPhase
import io.github.sajadinmaker.vpnbox.ui.theme.Bg
import io.github.sajadinmaker.vpnbox.ui.theme.ChipBg
import io.github.sajadinmaker.vpnbox.ui.theme.ChipBorder
import io.github.sajadinmaker.vpnbox.ui.theme.Dim
import io.github.sajadinmaker.vpnbox.ui.theme.Green
import io.github.sajadinmaker.vpnbox.ui.theme.PanelBorder
import io.github.sajadinmaker.vpnbox.ui.theme.Red
import io.github.sajadinmaker.vpnbox.ui.theme.White
import io.github.sajadinmaker.vpnbox.ui.theme.Yellow

private val phaseCaption: Map<WatchPhase, Pair<String, String>> = mapOf(
    WatchPhase.CONNECT to Pair("01 · CONNECT", "Fastest volunteer relay"),
    WatchPhase.WATCH to Pair("02 · WATCH", "The watchdog has the intent"),
    WatchPhase.KILL to Pair("04 · RECOVER", "Back in 4 seconds"),
    WatchPhase.RECOVERED to Pair("04 · RECOVERED", "No human needed"),
    WatchPhase.FAILED to Pair("× FAILURE", "Volunteer servers churn — refresh"),
)

@Composable
fun TerminalScreen(
    ui: TerminalUi,
    onBack: () -> Unit,
    onKill: () -> Unit,
) {
    val (kicker, headline) = phaseCaption.getValue(ui.phase)
    val autoScroll = rememberScrollState()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Bg)
            .systemBarsPadding()
            .padding(horizontal = 18.dp),
    ) {
        Spacer(Modifier.height(20.dp))
        VpnboxLogo(width = 210.dp)
        Spacer(Modifier.height(14.dp))
        PanelChrome(
            title = "vpnbox · watch — live session",
            tag = when (ui.phase) {
                WatchPhase.RECOVERED -> "RECOVERED"
                WatchPhase.FAILED -> "DOWN"
                else -> "REAL ENGINE"
            },
            modifier = Modifier.weight(1f),
        ) {
            LaunchedEffect(ui.lines.size) {
                autoScroll.scrollTo(autoScroll.maxValue)
            }
            Column(
                modifier = Modifier
                    .verticalScroll(autoScroll),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                for (l in ui.lines) TerminalRow(l)
            }
        }
        Spacer(Modifier.height(16.dp))
        Text(
            kicker,
            fontFamily = FontFamily.Monospace,
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 2.sp,
            color = if (ui.phase == WatchPhase.FAILED) Red else Red,
        )
        Spacer(Modifier.height(4.dp))
        Text(headline, fontSize = 30.sp, fontWeight = FontWeight.Bold,
             color = if (ui.phase == WatchPhase.FAILED) Dim else White)
        Spacer(Modifier.height(14.dp))
        ChipsRow(ui.phase, onBack, onKill)
        Spacer(Modifier.height(12.dp))
        ProgressBar(fraction = when (ui.phase) {
            WatchPhase.CONNECT -> 0.33f
            WatchPhase.WATCH -> 0.66f
            WatchPhase.KILL -> 0.8f
            WatchPhase.RECOVERED, WatchPhase.FAILED -> 1f
        })
        Spacer(Modifier.height(10.dp))
        Text(
            "vpnbox",
            fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = Dim,
        )
        Spacer(Modifier.height(14.dp))
    }
}

@Composable
private fun TerminalRow(l: TerminalLine) {
    val color = when (l.tone) {
        TerminalLine.Tone.OK -> Green
        TerminalLine.Tone.WARN -> Yellow
        TerminalLine.Tone.ERR -> Red
        TerminalLine.Tone.ACCENT -> White
        TerminalLine.Tone.PLAIN -> Dim
    }
    Text(
        l.text,
        fontFamily = FontFamily.Monospace,
        fontSize = 11.sp,
        lineHeight = 15.sp,
        color = color,
    )
}

@Composable
private fun ChipsRow(phase: WatchPhase, onBack: () -> Unit, onKill: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Chip("connect", if (phase != WatchPhase.CONNECT) Dim else White,
             bold = false, modifier = Modifier.weight(1f), onClick = onBack)
        Chip("watch", if (phase == WatchPhase.KILL) Yellow else Dim,
             bold = phase == WatchPhase.KILL,
             modifier = Modifier.weight(1f))
        Chip("kill", Dim, bold = phase == WatchPhase.KILL,
             modifier = Modifier.weight(1f), onClick = if (phase == WatchPhase.WATCH) onKill else null)
        val (label, color) = when (phase) {
            WatchPhase.RECOVERED -> "recovered" to Green
            WatchPhase.FAILED -> "failed" to Red
            else -> "—" to Dim
        }
        Chip(label, color, bold = phase == WatchPhase.RECOVERED,
             modifier = Modifier.weight(1f))
    }
}

@Composable
private fun Chip(
    label: String,
    color: androidx.compose.ui.graphics.Color,
    bold: Boolean,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(18.dp))
            .background(ChipBg)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            fontFamily = FontFamily.Monospace,
            fontSize = 12.sp,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
            color = color,
            modifier = if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier,
        )
    }
}

@Composable
private fun ProgressBar(fraction: Float) {
    Column {
        Row(horizontalArrangement = Arrangement.SpaceBetween,
            modifier = Modifier.fillMaxWidth()) {
            for (i in 0 until 20) {
                val on = (i + 1) / 20f <= fraction
                Box(
                    Modifier
                        .height(3.dp)
                        .weight(1f)
                        .padding(horizontal = 1.dp)
                        .background(if (on) Red else PanelBorder,
                                    RoundedCornerShape(2.dp)),
                )
            }
        }
    }
}
