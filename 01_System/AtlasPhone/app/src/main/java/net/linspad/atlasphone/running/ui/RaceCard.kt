package net.linspad.atlasphone.running.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.ghost.LibraryRun
import net.linspad.atlasphone.running.live.HrTarget
import net.linspad.atlasphone.running.session.RunController
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val DATE = DateTimeFormatter.ofPattern("d MMM yyyy").withZone(ZoneId.systemDefault())

private fun describe(r: LibraryRun, rank: Int?): String =
    listOfNotNull(rank?.let { "#$it" }, DATE.format(Instant.ofEpochMilli(r.startedAtMillis)), fmtDuration(r.movingS), r.category, r.avgHr?.let { "avg HR %.0f".format(it) })
        .joinToString(" · ")

/**
 * Race any earlier run on a route, chosen on the phone from the local library (works offline). The chosen run is the
 * raced ghost; every other run on the route appears on the minimap. #n is the rank by finishing time (1 = fastest).
 */
@Composable
internal fun RaceCard(controller: RunController, tick: Int, targetHr: Int?, start: (() -> Unit) -> Unit, onError: (String?) -> Unit) {
    val library = remember(tick) { controller.library() }
    var routeId by remember { mutableStateOf<String?>(null) }
    var ghostId by remember { mutableStateOf<String?>(null) }
    val route = library.routes.firstOrNull { it.routeId == routeId }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Race a run", style = MaterialTheme.typography.titleMedium)
            val routes = library.routes.filter { library.runsOn(it.routeId).isNotEmpty() }
            if (routes.isEmpty()) Text("No runs in the library yet. Refresh from Atlas.")
            routes.forEach { r ->
                val sel = r.routeId == routeId
                Pick(sel, { routeId = r.routeId; ghostId = null }) {
                    Text("${r.name}  (%.2f km, ${library.runsOn(r.routeId).size} runs)".format(r.referenceDistanceM / 1000.0))
                }
            }
            if (route != null) {
                val wanted = HrTarget.category(targetHr, route.referenceDistanceM)
                val runs = library.runsOn(route.routeId).sortedWith(compareByDescending<LibraryRun> { wanted != null && it.category == wanted }.thenByDescending { it.startedAtMillis })
                QuickPicks(runs.minByOrNull { it.movingS ?: Double.MAX_VALUE }, runs.maxByOrNull { it.startedAtMillis }) { ghostId = it }
                val ranks = controller.fieldRanks(route.routeId)
                runs.take(30).forEach { r ->
                    val sel = r.runId == ghostId
                    val ready = controller.raceReady(r)
                    Pick(sel, { ghostId = r.runId }) { Text(describe(r, ranks[r.runId]) + if (ready) "" else "  (not downloaded)", fontSize = 14.sp) }
                }
                val chosen = runs.firstOrNull { it.runId == ghostId }
                if (chosen != null && !controller.raceReady(chosen)) Text("This ghost is not on the phone yet: refresh with Atlas reachable.", color = Color(0xFFFFC107))
                Button(modifier = Modifier.fillMaxWidth(), enabled = chosen != null && controller.raceReady(chosen),
                    onClick = { start { runCatching { controller.startRace(route.routeId, chosen!!.runId, targetHr) }.onFailure { onError(it.message) } } }) {
                    Text("Start race", fontSize = 22.sp)
                }
            }
        }
    }
}

@Composable
private fun QuickPicks(fastest: LibraryRun?, latest: LibraryRun?, pick: (String) -> Unit) {
    androidx.compose.foundation.layout.Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(enabled = fastest != null, onClick = { fastest?.let { pick(it.runId) } }) { Text("Fastest") }
        OutlinedButton(enabled = latest != null, onClick = { latest?.let { pick(it.runId) } }) { Text("Latest") }
    }
}

/** Selected = filled button, otherwise outlined. */
@Composable
private fun Pick(selected: Boolean, onClick: () -> Unit, content: @Composable () -> Unit) {
    if (selected) Button(onClick = onClick) { content() } else OutlinedButton(onClick = onClick) { content() }
}
