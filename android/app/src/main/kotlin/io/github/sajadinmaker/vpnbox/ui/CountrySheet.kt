package io.github.sajadinmaker.vpnbox.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.sajadinmaker.vpnbox.CountryPick
import io.github.sajadinmaker.vpnbox.ui.theme.Dim
import io.github.sajadinmaker.vpnbox.ui.theme.Panel
import io.github.sajadinmaker.vpnbox.ui.theme.Red
import io.github.sajadinmaker.vpnbox.ui.theme.White

/** The reel's country menu: bold code, name, live count. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CountrySheet(
    countries: List<CountryPick>,
    onPick: (CountryPick) -> Unit,
    onDismiss: () -> Unit,
) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = state,
        containerColor = Panel,
        tonalElevation = 0.dp,
    ) {
        Column(Modifier.padding(horizontal = 18.dp)) {
            Text("Which country?",
                 fontFamily = FontFamily.Monospace,
                 fontSize = 15.sp,
                 fontWeight = FontWeight.Bold,
                 color = White)
            Text("${countries.size} pools live",
                 fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Dim)
            Spacer(Modifier.heightIn(min = 10.dp))
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 420.dp)
                    .padding(top = 8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                items(countries, key = { it.cc }) { c ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .clickable { onPick(c) }
                            .padding(horizontal = 10.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            c.cc,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                            color = Red,
                            modifier = Modifier.width(52.dp),
                        )
                        Text(
                            c.country,
                            fontSize = 14.sp,
                            color = White,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1,
                            modifier = Modifier
                                .weight(1f)
                                .padding(end = 8.dp),
                        )
                        Text(
                            "${c.servers}",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp,
                            color = Dim,
                        )
                    }
                }
            }
            Spacer(Modifier.heightIn(min = 18.dp))
        }
    }
}
