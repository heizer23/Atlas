package net.linspad.atlasphone.running.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.coach.CoachFrequency
import net.linspad.atlasphone.running.coach.CoachPlan
import net.linspad.atlasphone.running.coach.CoachPlanParse
import net.linspad.atlasphone.running.coach.SegmentKind

private val Amber = Color(0xFFFFC107)

private fun targets(plan: CoachPlan): String {
    val seg = plan.segments.firstOrNull { it.kind == SegmentKind.STEADY || it.kind == SegmentKind.WORK } ?: return ""
    val parts = buildList {
        seg.hr?.let { add("HR ${it.lo.toInt()}-${it.hi.toInt()}") }
        seg.pace?.let { add("pace ${fmtPace(it.lo)}-${fmtPace(it.hi)}") }
        seg.cadence?.let { add("cadence ${it.lo.toInt()}-${it.hi.toInt()}") }
    }
    return parts.joinToString(" · ")
}

/** Run home panel card: the cached plan, the 'Coach this run' switch, the frequency and a refresh button (display + input only). */
@Composable
internal fun CoachPlanCard(
    plan: CoachPlanParse?, enabled: Boolean, frequency: CoachFrequency, speechAvailable: Boolean, refreshing: Boolean,
    onEnabled: (Boolean) -> Unit, onFrequency: (CoachFrequency) -> Unit, onRefresh: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Coach", style = MaterialTheme.typography.titleMedium)
            when (plan) {
                is CoachPlanParse.Ok -> {
                    Text(plan.plan.title, fontSize = 18.sp)
                    Text("${Math.round(plan.plan.totalS() / 60.0)} min · ${targets(plan.plan)}")
                    Text("Saved on this phone. It works offline and refreshes when Atlas is reachable.", fontSize = 12.sp)
                }
                is CoachPlanParse.Unsupported -> Text("Plan needs an app update", color = Amber)
                is CoachPlanParse.Invalid -> Text("The saved plan cannot be read. Refresh or accept it again on Atlas.", color = Amber)
                null -> Text("No plan accepted. Accept a recommended session on the Coach page of Atlas, then refresh.")
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Switch(checked = enabled, onCheckedChange = onEnabled)
                Text("Coach this run")
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Frequency")
                CoachFrequency.entries.forEach { f ->
                    if (f == frequency) Button(onClick = { onFrequency(f) }) { Text(f.label) }
                    else OutlinedButton(onClick = { onFrequency(f) }) { Text(f.label) }
                }
            }
            if (!speechAvailable) Text("Voice is unavailable on this phone: instructions appear as text only.", color = Amber, fontSize = 12.sp)
            OutlinedButton(onClick = onRefresh, enabled = !refreshing) { Text(if (refreshing) "Refreshing..." else "Refresh plan") }
        }
    }
}
