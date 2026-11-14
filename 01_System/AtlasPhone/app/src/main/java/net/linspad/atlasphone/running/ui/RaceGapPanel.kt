package net.linspad.atlasphone.running.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.live.LiveTrends

private val GainGreen = Color(0xFF5BE584)
private val LossRed = Color(0xFFFF6B6B)
private val Soft = Color(0xFF9AA3B2)

/**
 * Left half of the lower race area (RC1): the current gap with the gaining/losing arrow, a 1-2 minute gap history and the
 * 20 s pace next to the ghost's pace on the same route section. Gap (seconds, own chart) and pace (two text figures) never
 * share an axis. Display only; every unknown value renders as the existing dash.
 */
@Composable
internal fun RaceGapPanel(gapS: Double?, trends: LiveTrends, racePaceSPerKm: Double?, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        GapLine(gapS, trends.gapChangeS)
        GapHistory(trends.gapSeries)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Column {
                Text(paceValue(racePaceSPerKm), color = Color.White, fontSize = 22.sp)
                Text("you 20 s", color = Soft, fontSize = 12.sp)
            }
            Column {
                Text(paceValue(trends.ghostSectionPaceSPerKm), color = Color(0xFF3B8EFF), fontSize = 22.sp)
                Text("ghost", color = Soft, fontSize = 12.sp)
            }
            Text("min/km", color = Soft, fontSize = 12.sp)
        }
    }
}

/** Gap history in seconds: zero line = level, above = ahead (green), below = behind (red). Nothing with fewer than two points. */
@Composable
private fun GapHistory(series: List<Pair<Double, Double>>) {
    if (series.size < 2) { Text("Gap history appears once the comparison runs", color = Soft, fontSize = 12.sp); return }
    val x0 = series.first().first; val x1 = series.last().first.coerceAtLeast(x0 + 1.0)
    val bound = series.maxOf { Math.abs(it.second) }.coerceAtLeast(5.0)
    Canvas(Modifier.fillMaxWidth().height(56.dp)) {
        fun px(x: Double) = ((x - x0) / (x1 - x0)).toFloat() * size.width
        fun py(gap: Double) = (0.5f - (-gap / bound).toFloat() / 2f) * size.height   // negative gap (ahead) is drawn higher
        drawLine(Soft, Offset(0f, size.height / 2), Offset(size.width, size.height / 2), strokeWidth = 1.dp.toPx())
        val path = Path()
        series.forEachIndexed { i, (x, g) -> if (i == 0) path.moveTo(px(x), py(g)) else path.lineTo(px(x), py(g)) }
        drawPath(path, if (series.last().second < 0) GainGreen else LossRed, style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round))
    }
}
