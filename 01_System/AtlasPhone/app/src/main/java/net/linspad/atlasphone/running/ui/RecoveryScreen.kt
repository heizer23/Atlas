package net.linspad.atlasphone.running.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.hr.HrSmoothing
import net.linspad.atlasphone.running.hr.HrSmoothingMode
import net.linspad.atlasphone.running.session.LiveRunState

private val PanelBg = Color(0xFF1B1B2F)
private val Amber = Color(0xFFFFC107)
private val Grey = Color(0xFF9E9E9E)
private val HrRed = Color(0xFFFF6B6B)

/**
 * HR points -> line segments: smoothed per [mode] (centered), broken wherever a point is a gap (null) or the time between
 * samples exceeds HR_GAP_BREAK_S. x = seconds since [originMillis]. Never draws a zero for missing data.
 */
internal fun hrLines(points: List<HrPoint>, mode: HrSmoothingMode, originMillis: Long, color: Color): List<Line> {
    val smoothed = HrSmoothing.series(points, mode)
    val lines = ArrayList<Line>()
    var current = ArrayList<Pair<Double, Double>>()
    var prevTs: Long? = null
    for (p in smoothed) {
        val bpm = p.bpm
        if (bpm == null || (prevTs != null && HrSmoothing.isGap(prevTs, p.tsMillis))) {
            if (current.size >= 2) lines.add(Line(current, color))
            current = ArrayList()
        }
        if (bpm != null) current.add((p.tsMillis - originMillis) / 1000.0 to bpm)
        prevTs = p.tsMillis
    }
    if (current.size >= 2) lines.add(Line(current, color))
    return lines
}

/**
 * Recovery phase (RunState.RECOVERY): running is frozen; heart rate keeps recording. Shows the running result, the time since the
 * run end, smoothed HR, HRR values as they become available (dash until then), the recovery HR graph and the Finish Training
 * button. Nothing is saved automatically.
 */
@Composable
internal fun RecoveryScreen(
    live: LiveRunState, smoothing: HrSmoothingMode, onReconnectHr: () -> Unit, onFinishTraining: () -> Unit, finishing: Boolean,
) {
    var confirm by remember { mutableStateOf(false) }
    val rec = live.recovery
    val s = live.meta.summary
    val t0 = live.meta.runFinishedAtMillis
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Run finished. Recovery", fontSize = 24.sp)
            Text("Run: ${fmtKm(s?.distanceM)} in ${fmtDuration(s?.movingS)}, ${fmtPace(s?.avgPaceSPerKm)}", color = Grey)
            if (rec?.reminderDue == true) {
                Text("You have been recovering for a while. Tap Finish Training to save the run.",
                    Modifier.fillMaxWidth().background(Amber).padding(10.dp), color = Color.Black, fontSize = 16.sp)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                Column { Text("Since run end"); Text(fmtDuration(rec?.secondsSinceRunEnd), fontSize = 40.sp) }
                Column { Text("Heart rate"); Text(fmtBpm(live.hrDisplay), fontSize = 40.sp, color = HrRed) }
            }
            if (live.hrDisplay == null) {
                val state = live.hrState.lowercase().replace('_', ' ')
                Text("HR sensor: $state. Finish Training stays available.", color = Amber)
                if (live.hrState != "CONNECTED" && live.hrState != "CONNECTING" && live.hrState != "RECONNECTING") {
                    OutlinedButton(onClick = onReconnectHr) { Text("Reconnect sensor") }
                }
            }
            val summary = rec?.summary
            Column(Modifier.fillMaxWidth().background(PanelBg).padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                    Tile("HR at end", summary?.hrEnd)
                    Tile("HR 60 s", summary?.hr60)
                    Tile("HR 120 s", summary?.hr120)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                    Tile("HRR60", summary?.hrr60)
                    Tile("HRR120", summary?.hrr120)
                }
                Text("HRR is the drop after exercise, not the return to resting heart rate.", color = Grey, fontSize = 13.sp)
            }
            val lines = if (rec != null && t0 != null) hrLines(rec.points, smoothing, t0, HrRed) else emptyList()
            Column(Modifier.fillMaxWidth().background(PanelBg).padding(12.dp)) {
                Text("Heart rate since run end")
                Sparkline(lines, emptyText = "The graph appears once heart-rate readings arrive")
            }
            Text("Recover the same way every time - standing or walking gently.", color = Grey)
        }
        Button(modifier = Modifier.fillMaxWidth(), enabled = !finishing, onClick = { confirm = true }) { Text("Finish Training", fontSize = 22.sp) }
    }
    if (confirm) {
        AlertDialog(
            onDismissRequest = { confirm = false },
            title = { Text("Finish training?") },
            text = { Text("Heart-rate recording stops and the run is saved. It is then synced to Atlas when it is reachable.") },
            confirmButton = { TextButton(onClick = { confirm = false; onFinishTraining() }) { Text("Finish Training") } },
            dismissButton = { TextButton(onClick = { confirm = false }) { Text("Keep recovering") } },
        )
    }
}

/** One value with a label; a dash until the value exists (never 0). */
@Composable
private fun Tile(label: String, value: Double?) {
    Column { Text(label, color = Grey, fontSize = 13.sp); Text(fmtBpm(value), fontSize = 28.sp) }
}
