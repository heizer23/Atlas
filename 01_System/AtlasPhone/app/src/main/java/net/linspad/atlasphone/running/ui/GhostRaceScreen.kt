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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
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
import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.session.LiveRunState
import net.linspad.atlasphone.running.live.GapTrend
import net.linspad.atlasphone.running.live.HeadingSmoother
import net.linspad.atlasphone.running.live.HrByDistance
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
private val GainGreen = Color(0xFF5BE584)
private val LossRed = Color(0xFFFF6B6B)

private val Big = TextStyle(fontWeight = FontWeight.SemiBold, fontFeatureSettings = "tnum", color = Color.White)

/**
 * The ghost race screen: a full-screen heading-up map with everything else laid over it (see the Ghost Runner mockup).
 * Display only: it reads [live] and never touches recording. The map, markers and chart glide between the 1 Hz updates.
 */
@Composable
internal fun GhostRaceScreen(
    live: LiveRunState, ghost: GhostLive, paused: Boolean, finishing: Boolean, gpsText: String, gpsGood: Boolean,
    onReconnectHr: () -> Unit, onPause: () -> Unit, onResume: () -> Unit, onFinish: () -> Unit,
) {
    val m = live.metrics
    val trends = live.trends
    val reading = ghost.reading
    BoxWithConstraints(Modifier.fillMaxSize().background(Bg)) {
        if (ghost.progressM != null && ghost.route.size >= 2 && ghost.status != GhostStatus.WAITING_FOR_START) {
            RaceMap(ghost, aspect = (maxHeight / maxWidth).toDouble())
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
                HrPair(m.currentHr, reading?.ghostHrAtPosition)
            }
            StatusLines(live, ghost, paused, gpsText, gpsGood, onReconnectHr)
            Row(Modifier.weight(1f).fillMaxWidth()) {
                Spacer(Modifier.weight(1f))
                HrDistanceChart(trends, ghost, live.targetHr, reading?.ghostHrAtPosition, m.currentHr, Modifier.width(158.dp).fillMaxHeight().padding(top = 8.dp, bottom = 8.dp))
            }
            BottomStats(m, trends, reading?.timeGapS)
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (paused) Button(modifier = Modifier.weight(1f).height(40.dp), onClick = onResume) { Text("Resume") }
                else OutlinedButton(modifier = Modifier.weight(1f).height(40.dp), onClick = onPause) { Text("Pause") }
                OutlinedButton(modifier = Modifier.weight(1f).height(40.dp), enabled = !finishing, onClick = onFinish) { Text("Finish") }
            }
        }
    }
}

// ── Top row ──────────────────────────────────────────────────────────────────

/** "♥ 142 vs ♥ 149": my heart rate (red) and the raced ghost's at my route position (blue). */
@Composable
private fun HrPair(mine: Int?, ghostAtSpot: Double?) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("♥", color = HrRed, fontSize = 26.sp)
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(mine?.toString() ?: DASH, style = Big, fontSize = 40.sp)
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
private fun BottomStats(m: LiveMetrics, trends: LiveTrends, gapS: Double?) {
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
            GapLine(gapS, trends.gapChangeS)
        }
        Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(fmtDuration(m.elapsedS), style = Big, fontSize = 34.sp)
            Text("time", color = Soft, fontSize = 14.sp)
        }
    }
}

/** "+0:18" = ahead of the ghost, "−0:18" = behind (green / red), with the 20-30 s trend arrow. */
@Composable
private fun GapLine(gapS: Double?, change: Double?) {
    if (gapS == null) { Text(DASH, color = Soft, fontSize = 18.sp); return }
    val ahead = gapS < 0
    val level = Math.abs(gapS) < 1.0
    val color = if (level) Color.White else if (ahead) GainGreen else LossRed
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        val arrow = when {
            change == null -> null
            change <= -GapTrend.STEADY_S -> "↗" to GainGreen
            change >= GapTrend.STEADY_S -> "↘" to LossRed
            else -> "→" to Soft
        }
        arrow?.let { Text(it.first, color = it.second, fontSize = 20.sp, fontWeight = FontWeight.Bold) }
        Text(gapText(gapS), style = Big.copy(color = color), fontSize = 20.sp)
    }
}

/** Mockup's "+0:18": a plus means a lead on the ghost, a minus means a deficit. */
internal fun gapText(timeGapS: Double): String {
    val abs = Math.abs(timeGapS)
    if (abs < 1.0) return "0:00"
    return (if (timeGapS < 0) "+" else "−") + fmtDuration(abs)
}

/** "7:15" from seconds per km (the unit label is drawn separately). */
internal fun paceValue(sPerKm: Double?): String = fmtPace(sPerKm).removeSuffix(" /km")

// ── Map ──────────────────────────────────────────────────────────────────────

@Composable
private fun RaceMap(ghost: GhostLive, aspect: Double) {
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

    Canvas(Modifier.fillMaxSize()) {
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
                    drawCircle(GhostBlue.copy(alpha = 0.25f), 32.dp.toPx(), o)
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

// ── Heart-rate comparison by route distance ──────────────────────────────────

/**
 * Slim vertical graph: bpm left to right, route progress top to bottom. Both traces are aligned by distance, not time.
 * Mine covers the part run so far; the ghost's covers its whole run, faded and dashed beyond my position. No frame, legend or title.
 */
@Composable
private fun HrDistanceChart(trends: LiveTrends, ghost: GhostLive, targetHr: Int?, ghostNow: Double?, myNow: Int?, modifier: Modifier) {
    val my = trends.hrByProgress
    val gh = ghost.ghostHrProfile
    val len = ghost.routeLengthM
    val myS = ghost.progressM
    if (len <= 0 || myS == null || (my.isEmpty() && gh.isEmpty())) return
    val (lo, hi) = HrByDistance.axis((my + gh).map { it.second }, targetHr?.toDouble())
    val labelPaint = remember { android.graphics.Paint().apply { isAntiAlias = true; textAlign = android.graphics.Paint.Align.CENTER; color = 0xFF9AA3B2.toInt() } }
    Canvas(modifier) {
        val top = 26.dp.toPx()
        val h = size.height - top
        fun x(bpm: Double) = ((bpm - lo) / (hi - lo)).toFloat().coerceIn(0f, 1f) * size.width
        fun y(s: Double) = top + (s / len).toFloat().coerceIn(0f, 1f) * h

        // Axis along the top, every 10 bpm (20 when the range is wide).
        val step = if (hi - lo > 50) 20 else 10
        labelPaint.textSize = 11.dp.toPx()
        var t = lo
        while (t <= hi) {
            val tx = x(t.toDouble())
            drawLine(Soft.copy(alpha = 0.5f), Offset(tx, top - 5.dp.toPx()), Offset(tx, top), 1.dp.toPx())
            drawContext.canvas.nativeCanvas.drawText(t.toString(), tx.coerceIn(12.dp.toPx(), size.width - 12.dp.toPx()), top - 9.dp.toPx(), labelPaint)
            t += step
        }
        drawLine(Soft.copy(alpha = 0.5f), Offset(0f, top), Offset(size.width, top), 1.dp.toPx())

        targetHr?.let {
            val tx = x(it.toDouble())
            drawLine(Color.White.copy(alpha = 0.45f), Offset(tx, top), Offset(tx, size.height), 1.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 8f)))
        }

        fun trace(points: List<Pair<Double, Double>>, color: Color, dashed: Boolean) {
            if (points.size < 2) return
            val p = Path()
            points.forEachIndexed { i, (s, bpm) -> if (i == 0) p.moveTo(x(bpm), y(s)) else p.lineTo(x(bpm), y(s)) }
            drawPath(p, if (dashed) color.copy(alpha = 0.4f) else color, style = Stroke(
                2.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round,
                pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(7f, 7f)) else null))
        }
        // The ghost: solid up to my position, then faded and dashed (the first point past it keeps the line joined).
        val firstPast = gh.indexOfFirst { it.first > myS }
        if (firstPast < 0) trace(gh, GhostBlue, false)
        else {
            trace(gh.subList(0, firstPast + 1), GhostBlue, false)
            trace(gh.subList(firstPast, gh.size), GhostBlue, true)
        }
        trace(my, HrRed, false)

        myNow?.let { drawCircle(Color.White, 4.5f.dp.toPx(), Offset(x(it.toDouble()), y(myS))); drawCircle(HrRed, 3.dp.toPx(), Offset(x(it.toDouble()), y(myS))) }
        ghostNow?.let { drawCircle(Color.White, 4.5f.dp.toPx(), Offset(x(it), y(myS))); drawCircle(GhostBlue, 3.dp.toPx(), Offset(x(it), y(myS))) }
    }
}
