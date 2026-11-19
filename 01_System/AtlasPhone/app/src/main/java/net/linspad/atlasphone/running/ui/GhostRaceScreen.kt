package net.linspad.atlasphone.running.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.RecoveryGate
import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.session.LiveRunState
import net.linspad.atlasphone.running.live.HeadingSmoother
import net.linspad.atlasphone.running.live.LiveTrends
import net.linspad.atlasphone.running.live.LocalMap
import net.linspad.atlasphone.running.metrics.LiveMetrics

// Dark sports-tech palette: calm route, restrained colours for me / the raced ghost / the two heart-rate traces.
private val Bg = Color(0xFF070B14)
private val RouteGreen = Color(0xFF4FB477)
private val MeGreen = Color(0xFF22C55E)
private val GhostBlue = Color(0xFF3B8EFF)
private val HrRed = Color(0xFFFF4D6D)
private val Soft = Color(0xFF9AA3B2)
private val Amber = Color(0xFFFFC107)

private val Big = TextStyle(fontWeight = FontWeight.SemiBold, fontFeatureSettings = "tnum", color = Color.White)

/**
 * The ghost race screen: a full-screen heading-up map with everything else laid over it (see the Ghost Runner mockup).
 * Display only: it reads [live] and never touches recording. The map, markers and chart glide between the 1 Hz updates.
 */
@Composable
internal fun GhostRaceScreen(
    live: LiveRunState, ghost: GhostLive, paused: Boolean, finishing: Boolean, gpsText: String, gpsGood: Boolean,
    onReconnectHr: () -> Unit, onPause: () -> Unit, onResume: () -> Unit, onFinish: () -> Unit,
    onCycleMetronome: () -> Unit = {}, onUseManualCadence: () -> Unit = {}, onManualCadence: (Int) -> Unit = {}, onClickVolume: (Float) -> Unit = {},
    onCoachMute: (Boolean) -> Unit = {}, onSelectGhost: (String) -> Unit = {},
) {
    val m = live.metrics
    val trends = live.trends
    val reading = ghost.reading
    BoxWithConstraints(Modifier.fillMaxSize().background(Bg)) {
        if (ghost.progressM != null && ghost.route.size >= 2 && ghost.status != GhostStatus.WAITING_FOR_START) {
            RaceMap(ghost, aspect = (maxHeight / maxWidth).toDouble(), onSelect = onSelectGhost)
        }
        // Soft fades keep the numbers readable over the route.
        Spacer(Modifier.fillMaxWidth().height(170.dp).background(Brush.verticalGradient(listOf(Bg, Color.Transparent))).align(Alignment.TopCenter))
        Spacer(Modifier.fillMaxWidth().height(230.dp).background(Brush.verticalGradient(listOf(Color.Transparent, Bg))).align(Alignment.BottomCenter))

        Column(Modifier.fillMaxSize().safeDrawingPadding().padding(horizontal = 16.dp, vertical = 8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.SpaceBetween) {
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(ghost.position?.toString() ?: DASH, style = Big, fontSize = 52.sp)
                    if (ghost.position != null) Text(" / ${ghost.fieldSize + 1}", style = Big.copy(color = Soft), fontSize = 28.sp, modifier = Modifier.padding(bottom = 6.dp))
                }
                HrPair(live.hrDisplay, reading?.ghostHrAtPosition)
            }
            StatusLines(live, ghost, paused, gpsText, gpsGood, onReconnectHr)
            MetronomeChip(live.metronome, live.cadenceSpm, onCycle = onCycleMetronome, onUseManual = onUseManualCadence,
                onManualSpm = onManualCadence, onVolume = onClickVolume)
            CoachStrip(live.coach, onCoachMute, Modifier.padding(top = 4.dp))   // absent without a coach session
            Row(Modifier.weight(1f).fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                // Left: distance gap (equal elapsed time). Right: HR and pace differences (same route position). The map shows between.
                GapChart(trends.race, Modifier.width(74.dp).fillMaxHeight())
                DeltaChart(trends.race, Modifier.width(112.dp).fillMaxHeight())
            }
            BottomStats(m, trends)
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (paused) Button(modifier = Modifier.weight(1f).height(40.dp), onClick = onResume) { Text("Resume") }
                else OutlinedButton(modifier = Modifier.weight(1f).height(40.dp), onClick = onPause) { Text("Pause") }
                OutlinedButton(modifier = Modifier.weight(1f).height(40.dp), enabled = !finishing, onClick = onFinish) {
                    Text(if (RecoveryGate.offersRecovery(m.currentHr)) "Finish Run" else "Finish") // O1: recovery only with a live HR
                }
            }
        }
    }
}

// ── Top row ──────────────────────────────────────────────────────────────────

/** "♥ 142 vs ♥ 149": my heart rate (red) and the raced ghost's at my route position (blue). */
@Composable
private fun HrPair(mine: Double?, ghostAtSpot: Double?) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("♥", color = HrRed, fontSize = 26.sp)
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(fmtBpm(mine), style = Big, fontSize = 40.sp)
            Text("bpm", color = Soft, fontSize = 13.sp)
        }
        Text("vs", color = Soft, fontSize = 15.sp)
        Text("♥", color = GhostBlue, fontSize = 26.sp)
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(fmtBpm(ghostAtSpot), style = Big, fontSize = 40.sp)
            Text("bpm", color = Soft, fontSize = 13.sp)
        }
    }
}

/** Only what needs attention: pause, comparison suspended, HR signal, poor GPS. Nothing when all is well. */
@Composable
private fun StatusLines(live: LiveRunState, ghost: GhostLive, paused: Boolean, gpsText: String, gpsGood: Boolean, onReconnectHr: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        if (paused) Text("PAUSED", Modifier.fillMaxWidth().background(Amber).padding(6.dp), color = Color.Black, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
        when (ghost.status) {
            GhostStatus.WAITING_FOR_START -> Text("Go to the start of the route", color = Amber, fontSize = 18.sp)
            GhostStatus.OFF_COURSE -> Text("Off the route: comparison paused", color = Amber, fontSize = 16.sp)
            GhostStatus.GPS_LOST -> Text("GPS lost: comparison paused", color = Amber, fontSize = 16.sp)
            GhostStatus.ON_COURSE -> Unit
        }
        if (!gpsGood && ghost.status != GhostStatus.GPS_LOST) Text(gpsText, color = Amber, fontSize = 14.sp)
        if (live.metrics.currentHr == null) {
            val state = live.hrState
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("No heart-rate signal", color = Amber, fontSize = 14.sp)
                if (state != "CONNECTED" && state != "CONNECTING" && state != "RECONNECTING") {
                    OutlinedButton(onClick = onReconnectHr, modifier = Modifier.height(32.dp)) { Text("Reconnect", fontSize = 12.sp) }
                }
            }
        }
    }
}

// ── Bottom row ───────────────────────────────────────────────────────────────

@Composable
private fun BottomStats(m: LiveMetrics, trends: LiveTrends) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(paceValue(trends.smoothedPaceSPerKm), style = Big, fontSize = 34.sp)
            Text("min/km", color = Soft, fontSize = 14.sp)
        }
        Column(Modifier.weight(1.15f), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(verticalAlignment = Alignment.Bottom) {
                Text("%.2f".format(m.distanceM / 1000.0), style = Big, fontSize = 34.sp)
                Text(" km", color = Soft, fontSize = 16.sp, modifier = Modifier.padding(bottom = 4.dp))
            }
        }
        Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(fmtDuration(m.elapsedS), style = Big, fontSize = 34.sp)
            Text("time", color = Soft, fontSize = 14.sp)
        }
    }
}

/** "7:15" from seconds per km (the unit label is drawn separately). */
internal fun paceValue(sPerKm: Double?): String = fmtPace(sPerKm).removeSuffix(" /km")

// ── Map ──────────────────────────────────────────────────────────────────────

@Composable
private fun RaceMap(ghost: GhostLive, aspect: Double, onSelect: (String) -> Unit) {
    val progress = ghost.progressM ?: return
    val dur = tween<Float>(1000, easing = LinearEasing)
    // Heading = route direction at my position (steadier than GPS bearing), low-passed and glided: the map turns slowly.
    val smoother = remember(ghost.route) { HeadingSmoother() }
    var lastNanos by remember(ghost.route) { mutableStateOf<Long?>(null) }
    val now = System.nanoTime()
    val smoothed = smoother.update(LocalMap.routeBearingDeg(ghost.route, progress), lastNanos?.let { (now - it) / 1e9 } ?: 0.0)
    lastNanos = now
    val heading by animateFloatAsState(smoothed.toFloat(), dur, label = "heading")
    // Positions arrive once a second; every runner glides to the next one.
    val myS by animateFloatAsState(progress.toFloat(), dur, label = "me")
    val field = ghost.field.map { f -> f.copy(progressM = animateFloatAsState(f.progressM.toFloat(), dur, label = "r${f.rank}").value.toDouble()) }
    val view = LocalMap.build(ghost.route, myS.toDouble(), field, heading.toDouble(), aspect)

    val ring = remember { android.graphics.Paint().apply { isAntiAlias = true; textAlign = android.graphics.Paint.Align.CENTER; isFakeBoldText = true } }
    val kmPaint = remember { android.graphics.Paint().apply { isAntiAlias = true; textAlign = android.graphics.Paint.Align.RIGHT; color = 0xFFB4BCC9.toInt() } }

    // Tap a ghost to race it: nearest marker within a thumb-sized radius. Display only, the run is untouched.
    val tapView = rememberUpdatedState(view)
    val tapSelect = rememberUpdatedState(onSelect)
    Canvas(Modifier.fillMaxSize().pointerInput(Unit) {
        detectTapGestures { tap ->
            val v = tapView.value
            val centre = Offset(size.width / 2f, size.height * 0.68f)
            val scale = size.width / 2f / v.radiusM.toFloat()
            val hit = v.markers.filter { it.runId.isNotEmpty() }.minByOrNull { mk ->
                (Offset(centre.x + mk.at.east.toFloat() * scale, centre.y - mk.at.north.toFloat() * scale) - tap).getDistance()
            }?.takeIf { mk ->
                (Offset(centre.x + mk.at.east.toFloat() * scale, centre.y - mk.at.north.toFloat() * scale) - tap).getDistance() <= 32.dp.toPx()
            }
            hit?.let { tapSelect.value(it.runId) }
        }
    }) {
        val centre = Offset(size.width / 2, size.height * 0.68f)
        val scale = size.width / 2 / view.radiusM.toFloat()
        fun at(east: Double, north: Double) = Offset(centre.x + east.toFloat() * scale, centre.y - north.toFloat() * scale)

        val path = Path()
        view.route.forEachIndexed { i, p -> val o = at(p.east, p.north); if (i == 0) path.moveTo(o.x, o.y) else path.lineTo(o.x, o.y) }
        drawPath(path, RouteGreen.copy(alpha = 0.16f), style = Stroke(26.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
        drawPath(path, RouteGreen.copy(alpha = 0.55f), style = Stroke(11.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))

        kmPaint.textSize = 12.dp.toPx()
        view.kmMarks.forEach { k ->
            val o = at(k.at.east, k.at.north)
            drawCircle(Color.White.copy(alpha = 0.75f), 3.dp.toPx(), o)
            drawContext.canvas.nativeCanvas.drawText("%.1f km".format(k.km), o.x - 9.dp.toPx(), o.y + kmPaint.textSize * 0.35f, kmPaint)
        }

        // Others first (digits 1-9, dots beyond), the raced ghost on top.
        view.markers.sortedBy { it.isMain }.forEach { mk ->
            val o = at(mk.at.east, mk.at.north)
            when {
                mk.isMain -> {
                    drawCircle(Amber, 31.dp.toPx(), o, style = Stroke(3.dp.toPx()))      // selected: unmistakable ring
                    drawCircle(GhostBlue.copy(alpha = 0.25f), 30.dp.toPx(), o)
                    drawCircle(GhostBlue, 22.dp.toPx(), o)
                    drawCircle(Color.White, 22.dp.toPx(), o, style = Stroke(2.5f.dp.toPx()))
                    digit(ring, mk.rank, o, Color.White, 20.sp.toPx())
                }
                mk.rank in 1..9 -> {
                    drawCircle(Color(0xFF111827), 15.dp.toPx(), o)
                    drawCircle(Color(0xFFD1D5DB), 15.dp.toPx(), o, style = Stroke(1.8f.dp.toPx()))
                    digit(ring, mk.rank, o, Color.White, 16.sp.toPx())
                }
                else -> drawCircle(Color(0xFFD1D5DB), 4.dp.toPx(), o)
            }
        }

        // Me: a directional arrow on a green disc (the map is heading-up, so the arrow always points up).
        drawCircle(MeGreen.copy(alpha = 0.28f), 34.dp.toPx(), centre)
        drawCircle(MeGreen, 22.dp.toPx(), centre)
        drawCircle(Color.White, 22.dp.toPx(), centre, style = Stroke(2.5f.dp.toPx()))
        val a = Path().apply {
            moveTo(centre.x, centre.y - 12.dp.toPx())
            lineTo(centre.x + 9.dp.toPx(), centre.y + 9.dp.toPx())
            lineTo(centre.x, centre.y + 4.dp.toPx())
            lineTo(centre.x - 9.dp.toPx(), centre.y + 9.dp.toPx())
            close()
        }
        drawPath(a, Color.White)
    }
}

private fun DrawScope.digit(paint: android.graphics.Paint, rank: Int, at: Offset, color: Color, textSizePx: Float) {
    paint.color = color.toArgb()
    paint.textSize = textSizePx
    drawContext.canvas.nativeCanvas.drawText(rank.toString(), at.x, at.y + textSizePx * 0.35f, paint)
}
