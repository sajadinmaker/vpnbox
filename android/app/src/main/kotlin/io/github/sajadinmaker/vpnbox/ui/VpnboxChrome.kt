package io.github.sajadinmaker.vpnbox.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.sajadinmaker.vpnbox.ui.theme.Dim
import io.github.sajadinmaker.vpnbox.ui.theme.Panel
import io.github.sajadinmaker.vpnbox.ui.theme.PanelBorder
import io.github.sajadinmaker.vpnbox.ui.theme.White
import io.github.sajadinmaker.vpnbox.ui.theme.Red

// 5-row pixel glyphs for the wordmark, straight off the reel's intro band.
private val PIXEL_FONT = mapOf(
    'V' to listOf("X...X", "X...X", "X...X", "X.X.X", ".X.X."),
    'P' to listOf("XXXX.", "X...X", "X...X", "XXXX.", "X...."),
    'N' to listOf("X...X", "XX..X", "X.X.X", "X..XX", "X...X"),
    'B' to listOf("XXXX.", "X...X", "XXXX.", "X...X", "XXXX."),
    'O' to listOf(".XXX.", "X...X", "X...X", "X...X", ".XXX."),
    'X' to listOf("X...X", ".X.X.", "..X..", ".X.X.", "X...X"),
)

/** The red band logo: white pixel VPNBOX on red, like the video's header. */
@Composable
fun VpnboxLogo(width: Dp = 264.dp) {
    val cell = width / 30f   // 6 letters x 5 cells = 30 wide
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(Red)
            .padding(horizontal = 2.dp, vertical = 3.dp),
    ) {
        Canvas(modifier = Modifier.size(width, cell * 5f)) {
            var x = 0f
            for (ch in "VPNBOX") {
                val glyph = PIXEL_FONT[ch] ?: continue
                for ((row, mask) in glyph.withIndex()) {
                    for ((col, c) in mask.withIndex()) {
                        if (c == 'X') {
                            drawRect(
                                color = Color(0xFFFFFFFF),
                                topLeft = Offset(x + col * cell.toPx(),
                                                 row * cell.toPx()),
                                size = androidx.compose.ui.geometry.Size(
                                    cell.toPx() - cell.toPx() * 0.12f,
                                    cell.toPx() - cell.toPx() * 0.12f,
                                ),
                            )
                        }
                    }
                }
                x += (5 + 1) * cell.toPx()   // 5 wide + 1 spacing
            }
        }
    }
}

/** The three traffic-light dots of the terminal chrome. */
@Composable
fun TrafficLights() {
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        listOf(Red, Color(0xFFF1FA8C), Color(0xFF50FA7B)).forEach { c ->
            Box(
                modifier = Modifier
                    .size(9.dp)
                    .clip(CircleShape)
                    .background(c),
            )
        }
    }
}

/** Terminal panel chrome: dots, mono title, right tag chip. */
@Composable
fun PanelChrome(
    title: String,
    tag: String,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(Panel)
            .border(1.dp, PanelBorder, RoundedCornerShape(14.dp)),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TrafficLights()
            Spacer(Modifier.weight(1f))
            Text(
                title,
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp,
                color = Dim,
            )
            Spacer(Modifier.weight(1f))
            Text(
                tag,
                fontFamily = FontFamily.Monospace,
                fontSize = 10.sp,
                letterSpacing = 1.2.sp,
                color = Red,
            )
        }
        Spacer(
            Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(PanelBorder),
        )
        Box(Modifier.padding(10.dp)) { content() }
    }
}

@Composable
fun LabeledLine(
    left: String,
    right: String,
    tone: Color = White,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(left, fontFamily = FontFamily.Monospace, fontSize = 12.sp,
             color = Dim)
        Text(right, fontFamily = FontFamily.Monospace, fontSize = 12.sp,
             color = tone, fontWeight = FontWeight.SemiBold,
             maxLines = 1)
    }
}
