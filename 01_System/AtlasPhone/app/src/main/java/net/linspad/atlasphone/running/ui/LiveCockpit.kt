package net.linspad.atlasphone.running.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.live.HrTarget
import net.linspad.atlasphone.running.live.HrZone
import net.linspad.atlasphone.running.live.HeadingSmoother
import net.linspad.atlasphone.running.live.LocalMap
import net.linspad.atlasphone.running.live.LiveTrends
import net.linspad.atlasphone.running.live.Trend
import net.linspad.atlasphone.running.live.leadTransition
import net.linspad.atlasphone.running.live.trendOf
import net.linspad.atlasphone.running.metrics.LiveMetrics

private val PanelBg = Color(0xFF1B1B2F)
private val Green = Color(0xFF8CFF66)
private val Red = Color(0xFFFF8A80)
private val Blue = Color(0xFF64B5F6)
private val Amber = Color(0xFFFFC107)
private val GhostColor = Color(0xFFB388FF)
private val Grey = Color(0xFF9E9E9E)

internal fun zoneColor(z: HrZone): Color = when (z) {
    HrZone.BELOW -> Blue
    HrZone.NEAR -> Green
    HrZone.ABOVE -> Red
    HrZone.NO_SIGNAL -> Amber
}

/** "8 below target" / "on target" / "12 above target" / "no heart-rate signal". */
internal fun zoneText(zone: HrZone, hr: Int?, target: Int?): String = when (zone) {
    HrZone.NO_SIGNAL -> if (hr == null) "no heart-rate signal" else "no target"
    HrZone.NEAR -> "on target (±${HrTarget.TOLERANCE_BPM})"
    HrZone.BELOW -> "${target!! - hr!!} below target"
    HrZone.ABOVE -> "${hr!! - target!!} above target"
}

/**
 * Heart rate next to the target. Without a target it is just the current value. A lost signal is loud and offers a manual
 * reconnect (the monitor already retries automatically); the run keeps recording without it.
 */
@Composable
internal fun HrCard(m: LiveMetrics, hrState: String, targetHr: Int?, onReconnect: () -> Unit) {
    val zone = if (targetHr == null && m.currentHr != null) HrZone.NEAR else HrTarget.zone(m.currentHr, targetHr)
    val color = if (targetHr == null && m.currentHr != null) Color.White else zoneColor(zone)
    Column(Modifier.fillMaxWidth().background(PanelBg).padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
            Column {
                Text("Heart rate")
                Text(m.currentHr?.toString() ?: DASH, fontSize = 64.sp, color = color)
            }
            if (targetHr != null) Column {
                Text("Target")
                Text("$targetHr", fontSize = 40.sp, color = Color.White)
            }
        }
        if (targetHr != null) Text(zoneText(zone, m.currentHr, targetHr), fontSize = 20.sp, color = color)
        if (m.currentHr == null) {
            val state = hrState.lowercase().replace('_', ' ')
            Text("HR sensor: $state. Recording continues without it.", color = Amber)
            if (hrState != "CONNECTED" && hrState != "CONNECTING" && hrState != "RECONNECTING") {
                OutlinedButton(onClick = onReconnect) { Text("Reconnect sensor") }
            }
        }
    }
}

/** Current (smoothed) pace, rolling 2-minute and run-average pace, and the pace history graph (faster = higher). */
@Composable
internal fun PaceCard(m: LiveMetrics, trends: LiveTrends) {
    Column(Modifier.fillMaxWidth().background(PanelBg).padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
            Column { Text("Pace"); Text(fmtPace(trends.smoothedPaceSPerKm), fontSize = 28.sp) }
            Column { Text("Last 2 min"); Text(fmtPace(trends.rollingPaceSPerKm), fontSize = 28.sp) }
            Column { Text("Average"); Text(fmtPace(m.avgPaceSPerKm), fontSize = 28.sp) }
        }
        Sparkline(listOf(Line(trends.paceSeries, Color.White)), invertY = true, emptyText = "Pace history appears once GPS has a pace")
    }
}

internal class Line(val points: List<Pair<Double, Double>>, val color: Color)

/**
 * Tiny line graph over the shared x range of all lines. [guide] is a dashed target line; [invertY] puts smaller values
 * (faster pace) higher. Nothing is drawn with fewer than two points.
 */
@Composable
internal fun Sparkline(lines: List<Line>, guide: Double? = null, invertY: Boolean = false, emptyText: String) {
    val all = lines.flatMap { it.points }
    if (all.size < 2 || lines.none { it.points.size >= 2 }) { Text(emptyText, color = Grey, fontSize = 14.sp); return }
    val x0 = all.minOf { it.first }; val x1 = all.maxOf { it.first }.coerceAtLeast(x0 + 1.0)
    var lo = all.minOf { it.second }; var hi = all.maxOf { it.second }
    if (guide != null) { lo = minOf(lo, guide); hi = maxOf(hi, guide) }
    val pad = ((hi - lo) * 0.1).coerceAtLeast(2.0); lo -= pad; hi += pad
    Canvas(Modifier.fillMaxWidth().height(64.dp)) {
        fun px(x: Double) = ((x - x0) / (x1 - x0)).toFloat() * size.width
        fun py(y: Double): Float { val f = ((y - lo) / (hi - lo)).toFloat(); return (if (invertY) f else 1f - f) * size.height }
        guide?.let { g ->
            val y = py(g)
            drawLine(Grey, Offset(0f, y), Offset(size.width, y), strokeWidth = 1.dp.toPx(),
                pathEffect = androidx.compose.ui.graphics.PathEffect.dashPathEffect(floatArrayOf(10f, 10f)))
        }
        lines.forEach { l ->
            val path = androidx.compose.ui.graphics.Path()
            l.points.forEachIndexed { i, (x, y) -> if (i == 0) path.moveTo(px(x), py(y)) else path.lineTo(px(x), py(y)) }
            if (l.points.size >= 2) drawPath(path, l.color, style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round))
        }
    }
}
