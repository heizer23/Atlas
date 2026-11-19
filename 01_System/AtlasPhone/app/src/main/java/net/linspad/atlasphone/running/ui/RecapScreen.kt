package net.linspad.atlasphone.running.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import net.linspad.atlasphone.running.RunMeta
import net.linspad.atlasphone.running.RunState
import net.linspad.atlasphone.running.hr.HrSmoothingMode
import net.linspad.atlasphone.running.recap.FinishStanding
import net.linspad.atlasphone.running.session.RunController

private val Accent = Color(0xFF8CFF66)
private val Grey = Color(0xFF9E9E9E)
private val HrRed = Color(0xFFFF6B6B)

/**
 * Recap after the run (replaces the old "Run finished" card). Built only from the persisted [RunMeta], so it works offline and
 * with or without an H10. Blocks without data are omitted, never shown as zero. No animation, no pop-ups; the one emphasis is
 * the accent colour on the position line. Sync status, retry and "Open in Atlas" are as before.
 */
@Composable
fun RecapScreen(meta: RunMeta, smoothing: HrSmoothingMode, onDone: () -> Unit = {}) {
    val context = LocalContext.current
    val controller = remember { RunController.get(context) }
    val current by produceState(meta, meta.captureId) {
        while (true) { controller.meta(meta.captureId)?.let { value = it }; delay(2000) }
    }
    val s = current.summary
    val recap = current.recap
    val standing = recap?.standing
    val synced = current.state == RunState.SYNCED
    Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Run finished", style = MaterialTheme.typography.headlineMedium)

        // Primary: the result of the run.
        Text(fmtKm(s?.distanceM), fontSize = 56.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
            Column { Text("Running time", color = Grey); Text(fmtDuration(s?.elapsedS), fontSize = 32.sp) }
            Column { Text("Average pace", color = Grey); Text(fmtPace(s?.avgPaceSPerKm), fontSize = 32.sp) }
        }
        if (standing != null) {
            Text("Position ${standing.position} / ${standing.fieldSize + 1}", fontSize = 32.sp, color = Accent)
            Text("Ghosts overtaken: ${standing.overtaken} of ${standing.fieldSize}", fontSize = 20.sp)
            Text(rivalText(standing), fontSize = 20.sp)
            achievements(standing).forEach { Text(it, fontSize = 18.sp) }
        }

        // Secondary: smaller, only with data.
        val hrSeries = recap?.hrSeries.orEmpty()
        if (hrSeries.isNotEmpty() || s?.avgHr != null) {
            Text("Heart rate", style = MaterialTheme.typography.titleMedium)
            Text("Average ${s?.avgHr?.let { "%.0f".format(it) } ?: DASH}   Max ${recap?.maxHr?.toString() ?: DASH}  (running phase)", fontSize = 16.sp)
            if (hrSeries.isNotEmpty()) Sparkline(hrLines(hrSeries, smoothing, hrSeries.first().tsMillis, HrRed), emptyText = "No heart-rate graph")
        }
        efficiencyFactor(s?.distanceM, s?.movingS, s?.avgHr)?.let { ef ->
            val baseline by produceState<Double?>(null, meta.captureId) {
                value = withContext(Dispatchers.IO) { controller.efficiencyBaseline(meta.captureId) }
            }
            Text("Aerobic efficiency ${"%.3f".format(ef)}" + (baseline?.let { "   ${efficiencyDelta(ef, it)} vs last 5 runs" } ?: ""), fontSize = 16.sp)
            Text("Speed (m/min) per heart-rate beat; higher = fitter. Trend over runs: Atlas web, History.", color = Grey, fontSize = 13.sp)
        }
        current.recovery?.let { r ->
            Text("Recovery", style = MaterialTheme.typography.titleMedium)
            Text("HRR60 ${fmtBpm(r.hrr60)}   HRR120 ${fmtBpm(r.hrr120)}", fontSize = 16.sp)
            Text("HRR is the drop after exercise, not the return to resting heart rate.", color = Grey, fontSize = 13.sp)
        }
        val splits = recap?.splits.orEmpty()
        if (splits.isNotEmpty()) {
            Text("Pace per km", style = MaterialTheme.typography.titleMedium)
            splits.forEach { sp ->
                Text("${if (sp.partial) "%.2f km".format(sp.distanceM / 1000.0) else "km ${sp.km}"}   ${fmtPace(sp.paceSPerKm)}" +
                    (sp.avgHr?.let { "   ${"%.0f".format(it)} bpm" } ?: ""), fontSize = 16.sp)
            }
        }

        Text(
            if (synced) "Synced to Atlas" else "Pending sync",
            Modifier.fillMaxWidth().background(if (synced) Color(0xFF2E7D32) else Color(0xFFFFC107)).padding(12.dp),
            color = if (synced) Color.White else Color.Black, fontSize = 22.sp,
        )
        if (!synced) Text(current.lastError ?: "Waiting for Atlas. Start Tailscale on this phone; the run is kept and syncs automatically.")
        if (current.needsRepair) Text("This phone must be paired again before it can sync.")
        if (!synced) OutlinedButton(onClick = { controller.retrySync() }) { Text("Retry sync") }
        if (synced) Button(onClick = {
            // atlas:// is handled by MainActivity (TWA); no bridge, no credentials in the link.
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("atlas://running/history/${current.captureId}")))
        }) { Text("Open in Atlas") }
        OutlinedButton(onClick = onDone) { Text("Done") }
    }
}

/** Efficiency factor = speed (m/min) / average HR, as on Atlas web. Null without distance, moving time or HR. */
internal fun efficiencyFactor(distanceM: Double?, movingS: Double?, avgHr: Double?): Double? {
    if (distanceM == null || movingS == null || avgHr == null || distanceM <= 0 || movingS <= 0 || avgHr <= 0) return null
    return (distanceM / (movingS / 60.0)) / avgHr
}

/** "+2.1%" / "-0.4%" relative to the baseline. */
internal fun efficiencyDelta(ef: Double, baseline: Double): String = "%+.1f%%".format((ef - baseline) / baseline * 100)

private fun rivalText(st: FinishStanding): String {
    val margin = st.rivalMarginS?.let { fmtDuration(it) }
    return if (st.rivalBeaten) "Rival beaten" + (margin?.let { " by $it" } ?: "") else "Rival not beaten" + (margin?.let { " ($it behind)" } ?: "")
}

/** Only achievements that are true facts of the persisted standing (ST1); nothing is invented. */
internal fun achievements(st: FinishStanding): List<String> = buildList {
    if (st.personalRecord) add("Personal record on this route")
    if (st.beatPreviousRun == true) add("Faster than your previous run on this route")
    st.previousRunRank?.let { if (st.routeCompleted) add("Your previous run on this route ranks $it") }
}
