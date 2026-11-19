package net.linspad.atlasphone.running.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.live.RaceDiff
import net.linspad.atlasphone.running.live.RaceDiffSeries

private val Panel = Color(0xCC070B14)
private val Soft = Color(0xFF9AA3B2)
private val Ahead = Color(0xFF5BE584)
private val Behind = Color(0xFFFF6B6B)
private val HrLine = Color(0xFFFF4D6D)
private val PaceLine = Color(0xFFFFC107)
private val Num = TextStyle(fontWeight = FontWeight.SemiBold, fontFeatureSettings = "tnum", color = Color.White)

/** Signed whole number with a real minus sign: "+30", "−7", "0". */
internal fun signed(v: Double?): String {
    if (v == null) return DASH
    val r = Math.round(v)
    return if (r > 0) "+$r" else if (r < 0) "−${-r}" else "0"
}

/** Symmetric half-range around zero: the smallest multiple of [step] (at least [min]) covering every value. */
internal fun halfRange(values: List<Double>, step: Double, min: Double): Double =
    maxOf(min, Math.ceil((values.maxOfOrNull { Math.abs(it) } ?: 0.0) / step) * step)

/**
 * Left chart: accumulated distance gap to the selected ghost at equal elapsed time, in metres. Route position runs down
 * (now at the top, older below), the vertical line is zero, right = runner ahead. Nothing else is drawn on it.
 */
@Composable
internal fun GapChart(race: RaceDiffSeries?, modifier: Modifier = Modifier) {
    val pts = race?.gapM.orEmpty()
    val bound = halfRange(pts.mapNotNull { it.second }, 10.0, 20.0)
    val now = pts.lastOrNull()?.second
    Column(modifier.clip(RoundedCornerShape(10.dp)).background(Panel).padding(horizontal = 6.dp, vertical = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(signed(now), style = Num.copy(color = if (now == null || Math.abs(now) < 1) Color.White else if (now > 0) Ahead else Behind), fontSize = 22.sp)
        Text("m gap", color = Soft, fontSize = 11.sp)
        if (race == null) return@Column
        Canvas(Modifier.fillMaxSize().padding(top = 6.dp)) {
            val cx = size.width / 2
            drawLine(Soft, Offset(cx, 0f), Offset(cx, size.height), 1.5f.dp.toPx())          // zero = level with the ghost
            drawSeries(pts, race.nowS, size.width, size.height) { cx + (it / bound).toFloat() * cx * 0.92f }
        }
    }
}

/**
 * Right chart: HR difference (solid red, bpm) and pace difference (dashed amber, s/km), both by route position, now at
 * the top. Each has its own half-range around the shared zero line, so the two units never share a raw scale.
 * Positive (right) = runner's HR higher / runner slower.
 */
@Composable
internal fun DeltaChart(race: RaceDiffSeries?, modifier: Modifier = Modifier) {
    val hr = race?.hrDelta.orEmpty(); val pace = race?.paceDelta.orEmpty()
    val hrBound = halfRange(hr.mapNotNull { it.second }, 5.0, 10.0)
    val paceBound = halfRange(pace.mapNotNull { it.second }, 15.0, 30.0)
    val hrNow = hr.lastOrNull()?.second; val paceNow = pace.lastOrNull()?.second
    Column(modifier.clip(RoundedCornerShape(10.dp)).background(Panel).padding(horizontal = 6.dp, vertical = 6.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text(signed(hrNow), style = Num.copy(color = HrLine), fontSize = 20.sp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Canvas(Modifier.width(14.dp).height(6.dp)) { drawLine(HrLine, Offset(0f, 3.dp.toPx()), Offset(size.width, 3.dp.toPx()), 2.5f.dp.toPx()) }
                    Text(" Δbpm", color = Soft, fontSize = 11.sp)
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(signed(paceNow), style = Num.copy(color = PaceLine), fontSize = 20.sp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Canvas(Modifier.width(14.dp).height(6.dp)) {
                        drawLine(PaceLine, Offset(0f, 3.dp.toPx()), Offset(size.width, 3.dp.toPx()), 2.5f.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 5f)))
                    }
                    Text(" Δs/km", color = Soft, fontSize = 11.sp)
                }
            }
        }
        if (race == null) return@Column
        Canvas(Modifier.fillMaxSize().padding(top = 6.dp)) {
            val cx = size.width / 2
            drawLine(Soft, Offset(cx, 0f), Offset(cx, size.height), 1.5f.dp.toPx())
            drawSeries(pace, race.nowS, size.width, size.height, dashed = true, color = PaceLine) { cx + (it / paceBound).toFloat() * cx * 0.92f }
            drawSeries(hr, race.nowS, size.width, size.height, dashed = false, color = HrLine) { cx + (it / hrBound).toFloat() * cx * 0.92f }
        }
    }
}

/**
 * Draws [pts] (route position, value) with the latest position at the top and the last [RaceDiff.SPAN_M] below it. A null
 * value or a jump in position (off the route) breaks the line instead of inventing a connection.
 */
private fun DrawScope.drawSeries(
    pts: List<Pair<Double, Double?>>, nowS: Double, w: Float, h: Float, dashed: Boolean = false, color: Color = Color.White,
    x: (Double) -> Float,
) {
    if (pts.isEmpty()) return
    val span = (nowS - pts.first().first).coerceIn(200.0, RaceDiff.SPAN_M)
    fun y(s: Double) = ((nowS - s) / span).toFloat().coerceIn(0f, 1f) * h
    val stroke = Stroke(2.5f.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round, pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(10f, 8f)) else null)
    var path: Path? = null
    var prevS = 0.0
    var last: Offset? = null
    fun flush() { path?.let { drawPath(it, color, style = stroke) }; path = null }
    for ((s, v) in pts) {
        if (v == null || (path != null && s - prevS > RaceDiff.STEP_M * 2.5)) flush()
        if (v == null) continue
        val o = Offset(x(v), y(s))
        if (path == null) path = Path().apply { moveTo(o.x, o.y) } else path!!.lineTo(o.x, o.y)
        prevS = s; last = o
    }
    flush()
    last?.let { drawCircle(Color.White, 5.dp.toPx(), it); drawCircle(color, 3.dp.toPx(), it) }
}
