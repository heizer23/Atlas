package net.linspad.atlasphone.running.ui

import android.content.Intent
import android.net.Uri
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
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.Switch
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import net.linspad.atlasphone.mobile.MobilePlatform
import net.linspad.atlasphone.mobile.heartrate.HeartRateMonitor
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionStatus
import net.linspad.atlasphone.running.live.HrTarget
import net.linspad.atlasphone.running.RunMeta
import net.linspad.atlasphone.running.RunState
import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.session.GhostReadiness
import net.linspad.atlasphone.running.session.LiveRunState
import net.linspad.atlasphone.running.session.RunController

// ── Formatting (display only) ────────────────────────────────────────────────

internal const val DASH = "–"

internal fun fmtDuration(s: Double?): String {
    if (s == null) return DASH
    val t = s.toLong()
    val h = t / 3600; val m = t % 3600 / 60; val sec = t % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, sec) else "%d:%02d".format(m, sec)
}

internal fun fmtPace(sPerKm: Double?): String {
    if (sPerKm == null || sPerKm.isNaN() || sPerKm.isInfinite() || sPerKm > 3599) return DASH
    val t = sPerKm.toLong()
    return "%d:%02d /km".format(t / 60, t % 60)
}

internal fun fmtKm(m: Double?): String = if (m == null) DASH else "%.2f km".format(m / 1000.0)

/** "0:23 AHEAD" / "0:23 BEHIND" / "LEVEL" from timeGapS (negative = ahead). Null gap -> dash. */
internal fun fmtGap(timeGapS: Double?): String {
    if (timeGapS == null) return DASH
    val abs = Math.abs(timeGapS)
    if (abs < 1.0) return "LEVEL"
    return fmtDuration(abs) + if (timeGapS < 0) " AHEAD" else " BEHIND"
}

/** "+45 m ahead" / "12 m behind" from leadM (positive = ahead). */
internal fun fmtLead(leadM: Double?): String {
    if (leadM == null) return DASH
    val m = Math.round(Math.abs(leadM))
    return if (m == 0L) "level" else if (leadM > 0) "$m m ahead" else "$m m behind"
}

internal fun fmtBpm(bpm: Double?): String = if (bpm == null) DASH else "%.0f".format(bpm)

// ── Home / recording ─────────────────────────────────────────────────────────

/**
 * Pre-start panel (GPS and H10 status, prepared runs, Free Run, pending uploads with retry, Recover/Discard) and, while a
 * run is active, the recording panel. Uses only [RunController] / MobilePlatform; a run never depends on Atlas.
 */
@Composable
fun RunningScreen(
    controller: RunController,
    ensurePermission: (Capability, () -> Unit) -> Unit = { _, action -> action() },
    onFinished: (RunMeta) -> Unit = {},
    onPair: () -> Unit = {},
) {
    val live by controller.live().collectAsState()
    live?.let { RecordingPanel(controller, it, ensurePermission, onFinished); return }
    HomePanel(controller, ensurePermission, onPair)
}

@Composable
private fun HomePanel(controller: RunController, ensurePermission: (Capability, () -> Unit) -> Unit, onPair: () -> Unit) {
    val context = LocalContext.current
    val platform = remember { MobilePlatform.get(context) }
    val scope = rememberCoroutineScope()
    var tick by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var confirmDiscard by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { while (true) { delay(3000); tick++ } } // the stored lists are not reactive

    @Suppress("UNUSED_VARIABLE") val t = tick
    val prefs = remember { context.getSharedPreferences("running_prefs", android.content.Context.MODE_PRIVATE) }
    var targetOn by remember { mutableStateOf(prefs.getBoolean("target_on", false)) }
    var targetBpm by remember { mutableIntStateOf(prefs.getInt("target_hr", HrTarget.DEFAULT_BPM)) }
    fun saveTarget() { prefs.edit().putBoolean("target_on", targetOn).putInt("target_hr", targetBpm).apply() }
    val targetHr = if (targetOn) targetBpm else null
    val gps by platform.location.state.collectAsState()
    val hrState by platform.heartRate.state.collectAsState()
    val hrLatest by platform.heartRate.latest.collectAsState()
    val devices by platform.heartRate.devices.collectAsState()
    val prepared = controller.preparedRuns()
    val pending = controller.pendingUploads()
    val interrupted = controller.interruptedRuns()
    val paired = controller.tokens.isPaired()

    // Keep the library current in the background (best effort, silent when Atlas is unreachable).
    LaunchedEffect(Unit) { if (controller.tokens.isPaired()) { controller.refreshLibrary(); tick++ } }

    // A remembered sensor is reconnected as soon as this screen opens (only if Bluetooth permission is already granted).
    LaunchedEffect(Unit) {
        val idle = platform.heartRate.state.value.let { it == HeartRateMonitor.State.IDLE || it == HeartRateMonitor.State.DISCONNECTED }
        if (idle && platform.heartRate.lastDeviceAddress() != null &&
            platform.permissions.status(Capability.BLUETOOTH, context as? android.app.Activity) == PermissionStatus.GRANTED) {
            platform.heartRate.connectLast(); platform.ensureForegroundService(context)
        }
    }

    Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Running", style = MaterialTheme.typography.headlineMedium)
        message?.let { Text(it, color = MaterialTheme.colorScheme.primary) }

        if (interrupted.isNotEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Interrupted run found", style = MaterialTheme.typography.titleMedium)
                    Text("The app was closed while recording. Nothing is finalized automatically.")
                    interrupted.forEach { r ->
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { runCatching { controller.recover(r.captureId) }.onFailure { message = "Cannot recover: ${it.message}" } }) { Text("Recover") }
                            OutlinedButton(onClick = { confirmDiscard = r.captureId }) { Text("Discard") }
                        }
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Sensors", style = MaterialTheme.typography.titleMedium)
                Text("GPS: ${gps.name.lowercase().replace('_', ' ')}")
                val hrOk = hrState == HeartRateMonitor.State.CONNECTED
                Text("Heart-rate sensor: ${hrState.name.lowercase().replace('_', ' ')}" + (hrLatest?.takeIf { hrOk }?.let { " (${it.bpm} bpm)" } ?: ""),
                    color = if (hrOk) MaterialTheme.colorScheme.primary else Color(0xFFFFC107))
                if (!hrOk) Text(
                    if (targetOn) "No heart-rate sensor: the target cannot be tracked. You can still run without it."
                    else "No heart-rate sensor: heart rate will not be recorded. You can still run without it.",
                    color = Color(0xFFFFC107))
                OutlinedButton(onClick = {
                    ensurePermission(Capability.BLUETOOTH) {
                        if (platform.heartRate.lastDeviceAddress() != null) platform.heartRate.connectLast() else platform.heartRate.scan()
                        platform.ensureForegroundService(context)
                    }
                }) { Text("Connect heart-rate sensor") }
                if (hrState == HeartRateMonitor.State.SCANNING) {
                    devices.forEach { d ->
                        OutlinedButton(onClick = { ensurePermission(Capability.BLUETOOTH) { platform.heartRate.connect(d); platform.ensureForegroundService(context) } }) {
                            Text("${d.name ?: d.address}  (${d.rssi} dBm)")
                        }
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Target heart rate", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    Switch(checked = targetOn, onCheckedChange = { targetOn = it; saveTarget() })
                }
                if (targetOn) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedButton(onClick = { targetBpm = (targetBpm - 5).coerceAtLeast(HrTarget.MIN_BPM); saveTarget() }) { Text("−5") }
                        Text("$targetBpm bpm", fontSize = 32.sp)
                        OutlinedButton(onClick = { targetBpm = (targetBpm + 5).coerceAtMost(HrTarget.MAX_BPM); saveTarget() }) { Text("+5") }
                    }
                    Text("Category: ${HrTarget.category(targetBpm, null)} (a route adds its length, e.g. 4 km · HR $targetBpm)")
                }
            }
        }

        Button(modifier = Modifier.fillMaxWidth(), onClick = {
            ensurePermission(Capability.LOCATION) { runCatching { controller.startFree(targetHr) }.onFailure { message = it.message } }
        }) { Text("Free Run", fontSize = 22.sp) }

        RaceCard(controller, tick, targetHr, { go -> ensurePermission(Capability.LOCATION, go) }) { message = it }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Prepared runs", style = MaterialTheme.typography.titleMedium)
                if (prepared.isEmpty()) Text("None downloaded.")
                prepared.forEach { r ->
                    val ghostReady = controller.ghostReadiness(r)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Column(Modifier.weight(1f)) {
                            Text("${r.title ?: "Untitled run"} (${r.preparedShortId ?: DASH})")
                            when (ghostReady) {
                                GhostReadiness.NONE -> if (r.routeId != null) Text("Route run, no ghost")
                                GhostReadiness.READY -> Text("Ghost ready (works offline)", color = MaterialTheme.colorScheme.primary)
                                GhostReadiness.MISSING -> Text("Ghost data not downloaded: refresh with Atlas reachable. Starting now runs without the ghost.", color = Color(0xFFFFC107))
                            }
                        }
                        Button(onClick = {
                            ensurePermission(Capability.LOCATION) { runCatching { controller.startPrepared(controller.preparedRunFor(r), targetHr) }.onFailure { message = it.message } }
                        }) { Text("Start") }
                    }
                }
                if (paired) {
                    OutlinedButton(onClick = { scope.launch { message = controller.refreshLibrary() ?: controller.refreshPrepared() ?: "Library and prepared runs updated."; tick++ } }) { Text("Refresh from Atlas") }
                } else {
                    Text("This phone is not paired with Atlas. Free Run works without it.")
                    OutlinedButton(onClick = onPair) { Text("Pair with Atlas") }
                }
            }
        }

        if (pending.isNotEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Pending sync", style = MaterialTheme.typography.titleMedium)
                    pending.forEach { r ->
                        Text("${fmtKm(r.summary?.distanceM)} in ${fmtDuration(r.summary?.elapsedS)}: " + (r.lastError ?: "waiting for Atlas"))
                        if (r.needsRepair) OutlinedButton(onClick = onPair) { Text("Re-pair this phone") }
                    }
                    OutlinedButton(onClick = { controller.retrySync(); message = "Sync requested."; tick++ }) { Text("Retry sync") }
                }
            }
        }
    }

    confirmDiscard?.let { id ->
        AlertDialog(
            onDismissRequest = { confirmDiscard = null },
            title = { Text("Discard this run?") },
            text = { Text("The recorded GPS and heart-rate data of this run will be deleted from the phone. This cannot be undone.") },
            confirmButton = { TextButton(onClick = { controller.discard(id); confirmDiscard = null; tick++ }) { Text("Discard") } },
            dismissButton = { TextButton(onClick = { confirmDiscard = null }) { Text("Keep") } },
        )
    }
}

@Composable
private fun RecordingPanel(controller: RunController, live: LiveRunState, ensurePermission: (Capability, () -> Unit) -> Unit, onFinished: (RunMeta) -> Unit) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val platform = remember { MobilePlatform.get(context) }
    var confirmFinish by remember { mutableStateOf(false) }
    var finishing by remember { mutableStateOf(false) }
    val paused = live.meta.state == RunState.PAUSED
    val m = live.metrics
    val gpsText = when {
        live.gpsState != "TRACKING" -> "GPS: ${live.gpsState.lowercase().replace('_', ' ')}"
        m.lastAccuracyM == null -> "GPS: waiting for a fix"
        m.lastAccuracyM > 30f -> "GPS: poor (%.0f m)".format(m.lastAccuracyM)
        else -> "GPS: good (%.0f m)".format(m.lastAccuracyM)
    }

    val ghost = live.ghost
    if (ghost != null) {
        // Ghost race: full-screen heading-up map with the stats laid over it.
        GhostRaceScreen(live, ghost, paused, finishing, gpsText, gpsGood = live.gpsState == "TRACKING" && (m.lastAccuracyM ?: 99f) <= 30f,
            onReconnectHr = { ensurePermission(Capability.BLUETOOTH) { platform.heartRate.reconnect(); platform.ensureForegroundService(context) } },
            onPause = { controller.pause() }, onResume = { controller.resume() }, onFinish = { confirmFinish = true })
    } else Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        // Free run: scrolling cockpit; Pause / Finish stay pinned below it.
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (paused) {
                // Manual pause is its own, unmistakable state; it is not poor GPS and not missing HR.
                Text("PAUSED", Modifier.fillMaxWidth().background(Color(0xFFFFC107)).padding(12.dp), color = Color.Black, fontSize = 28.sp)
            }
            live.meta.category?.let { Text(it, color = Color(0xFF9E9E9E)) }
            Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                Column { Text("Time"); Text(fmtDuration(m.elapsedS), fontSize = 40.sp) }
                Column { Text("Distance"); Text(fmtKm(m.distanceM), fontSize = 40.sp) }
            }
            Text("moving ${fmtDuration(m.movingS)}")
            HrCard(m, live.hrState, live.targetHr) {
                ensurePermission(Capability.BLUETOOTH) { platform.heartRate.reconnect(); platform.ensureForegroundService(context) }
            }
            PaceCard(m, live.trends)
            Text(gpsText)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (paused) Button(modifier = Modifier.weight(1f), onClick = { controller.resume() }) { Text("Resume", fontSize = 22.sp) }
            else OutlinedButton(modifier = Modifier.weight(1f), onClick = { controller.pause() }) { Text("Pause", fontSize = 22.sp) }
            OutlinedButton(modifier = Modifier.weight(1f), enabled = !finishing, onClick = { confirmFinish = true }) { Text("Finish", fontSize = 22.sp) }
        }
    }

    if (confirmFinish) {
        AlertDialog(
            onDismissRequest = { confirmFinish = false },
            title = { Text("Finish this run?") },
            text = { Text("Recording stops. The run is then synced to Atlas when it is reachable.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmFinish = false; finishing = true
                    scope.launch { val meta = controller.finish(); finishing = false; onFinished(meta) }
                }) { Text("Finish") }
            },
            dismissButton = { TextButton(onClick = { confirmFinish = false }) { Text("Keep running") } },
        )
    }
}

// ── Summary ──────────────────────────────────────────────────────────────────

/** Short summary after finishing; shows clearly whether the run is already synced to Atlas. */
@Composable
fun SummaryScreen(meta: RunMeta, onDone: () -> Unit = {}) {
    val context = LocalContext.current
    val controller = remember { RunController.get(context) }
    val current by produceState(meta, meta.captureId) {
        while (true) { controller.meta(meta.captureId)?.let { value = it }; delay(2000) }
    }
    val s = current.summary
    val synced = current.state == RunState.SYNCED
    Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Run finished", style = MaterialTheme.typography.headlineMedium)
        Text(fmtKm(s?.distanceM), fontSize = 48.sp)
        Text("Time ${fmtDuration(s?.elapsedS)}   Moving ${fmtDuration(s?.movingS)}")
        Text("Average pace ${fmtPace(s?.avgPaceSPerKm)}   Average HR ${s?.avgHr?.let { "%.0f".format(it) } ?: DASH}")
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
