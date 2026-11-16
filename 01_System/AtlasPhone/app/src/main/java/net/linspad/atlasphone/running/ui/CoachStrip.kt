package net.linspad.atlasphone.running.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.coach.CoachUiState

private val StripBg = Color(0xFF111827)
private val Soft = Color(0xFF9AA3B2)
private val Amber = Color(0xFFFFC107)

/**
 * One thin coach strip (display + input only, COACH1): the last instruction while it is fresh, the current segment with its
 * remaining time, a mute toggle. State null (no coach session) renders nothing. No animation.
 */
@Composable
internal fun CoachStrip(state: CoachUiState?, onMute: (Boolean) -> Unit, modifier: Modifier = Modifier) {
    if (state == null) return
    val segment = state.segmentLabel?.let { label ->
        label + (state.segmentRemainingS?.let { " ${fmtDuration(it.toDouble())}" } ?: "")
    } ?: "Plan complete"
    Row(modifier.fillMaxWidth().background(StripBg, RoundedCornerShape(10.dp)).padding(8.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(Modifier.weight(1f)) {
            Text(state.lastInstruction ?: "Coach: $segment", color = Color.White, fontSize = if (state.lastInstruction != null) 18.sp else 14.sp)
            if (state.lastInstruction != null) Text(segment, color = Soft, fontSize = 12.sp)
            if (!state.speechAvailable) Text("Voice unavailable, text only", color = Amber, fontSize = 12.sp)
        }
        OutlinedButton(onClick = { onMute(!state.muted) }, modifier = Modifier.height(36.dp)) { Text(if (state.muted) "Unmute" else "Mute", fontSize = 14.sp) }
    }
}
