package net.linspad.atlasphone.running.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import net.linspad.atlasphone.running.metronome.MetronomeConfig
import net.linspad.atlasphone.running.metronome.MetronomeMode
import net.linspad.atlasphone.running.metronome.MetronomeState

private val ChipBg = Color(0xFF111827)
private val Soft = Color(0xFF9AA3B2)
private val Amber = Color(0xFFFFC107)

/**
 * Metronome control (display + input only, MET1): one tap on the chip cycles the mode; the label shows mode, target and,
 * when known, "you N". A ghost mode whose ghost has no cadence states that and offers the manual cadence. MANUAL shows -/+
 * steppers; a small slider sets the click volume. State null renders nothing.
 */
@Composable
internal fun MetronomeChip(
    state: MetronomeState?, cadenceSpm: Double?, onCycle: () -> Unit, onUseManual: () -> Unit,
    onManualSpm: (Int) -> Unit, onVolume: (Float) -> Unit,
) {
    if (state == null) return
    val ghostMode = state.mode == MetronomeMode.MATCH_GHOST || state.mode == MetronomeMode.ATTACK_102
    Column(Modifier.fillMaxWidth().background(ChipBg, RoundedCornerShape(10.dp)).padding(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onCycle, modifier = Modifier.height(36.dp)) { Text(if (state.mode == MetronomeMode.COACH) "Click: Coach" else "Click: ${state.mode.label}", fontSize = 14.sp) }
            Text(state.targetSpm?.let { "%.0f spm".format(it) } ?: DASH, color = Color.White, fontSize = 18.sp)
            Text("you " + (cadenceSpm?.let { "%.0f".format(it) } ?: DASH), color = Soft, fontSize = 14.sp)
        }
        if (ghostMode && state.ghostHasCadence == false) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("No cadence recorded for this ghost", color = Amber, fontSize = 13.sp, modifier = Modifier.weight(1f))
                OutlinedButton(onClick = onUseManual, modifier = Modifier.height(32.dp)) { Text("Use manual cadence", fontSize = 12.sp) }
            }
        }
        if (state.mode == MetronomeMode.MANUAL) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { onManualSpm(state.manualSpm - MetronomeConfig.MANUAL_STEP_SPM) }, modifier = Modifier.height(32.dp)) { Text("−") }
                Text("${state.manualSpm} spm", color = Color.White, fontSize = 16.sp)
                OutlinedButton(onClick = { onManualSpm(state.manualSpm + MetronomeConfig.MANUAL_STEP_SPM) }, modifier = Modifier.height(32.dp)) { Text("+") }
            }
        }
        if (state.mode != MetronomeMode.OFF) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Volume", color = Soft, fontSize = 12.sp, modifier = Modifier.width(52.dp))
                Slider(value = state.volume, onValueChange = onVolume, valueRange = 0f..1f)
            }
            if (state.engine == "ERROR") Text("Click audio is not available", color = Amber, fontSize = 12.sp)
        }
    }
}
