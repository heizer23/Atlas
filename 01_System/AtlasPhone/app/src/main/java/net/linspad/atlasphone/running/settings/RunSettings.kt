package net.linspad.atlasphone.running.settings

import android.content.Context
import net.linspad.atlasphone.running.hr.HrSmoothingMode
import net.linspad.atlasphone.running.metronome.MetronomeConfig
import net.linspad.atlasphone.running.metronome.MetronomeMode

/** Tiny key-value seam so JVM tests need no Android. */
interface SettingsStore {
    fun getString(key: String): String?
    fun putString(key: String, value: String)
}

/** Phone-local display settings (SharedPreferences atlas_run_settings). Not secret and never uploaded. */
class RunSettings(private val store: SettingsStore) {
    /** Stored mode; ROLLING_5S when unset or unknown. */
    fun hrSmoothing(): HrSmoothingMode = HrSmoothingMode.parse(store.getString(KEY_HR_SMOOTHING))

    fun setHrSmoothing(mode: HrSmoothingMode) = store.putString(KEY_HR_SMOOTHING, mode.name)

    /** Stored metronome mode; OFF when unset or unknown. */
    fun metronomeMode(): MetronomeMode = MetronomeMode.parse(store.getString(KEY_METRONOME_MODE))

    fun setMetronomeMode(mode: MetronomeMode) = store.putString(KEY_METRONOME_MODE, mode.name)

    /** Manual fixed cadence clamped to the target range; the default when unset or unparsable. */
    fun manualCadenceSpm(): Int =
        store.getString(KEY_MANUAL_CADENCE)?.toIntOrNull()?.let(::clampSpm) ?: MetronomeConfig.DEFAULT_MANUAL_SPM

    fun setManualCadenceSpm(spm: Int) = store.putString(KEY_MANUAL_CADENCE, clampSpm(spm).toString())

    /** Click volume 0..1; the default when unset or unparsable. */
    fun clickVolume(): Float =
        store.getString(KEY_CLICK_VOLUME)?.toFloatOrNull()?.takeIf { !it.isNaN() }?.coerceIn(0f, 1f) ?: MetronomeConfig.DEFAULT_VOLUME

    fun setClickVolume(volume: Float) = store.putString(KEY_CLICK_VOLUME, volume.coerceIn(0f, 1f).toString())

    private fun clampSpm(spm: Int) = spm.coerceIn(MetronomeConfig.MIN_TARGET_SPM.toInt(), MetronomeConfig.MAX_TARGET_SPM.toInt())

    companion object {
        const val KEY_HR_SMOOTHING = "hr_smoothing"
        const val KEY_METRONOME_MODE = "metronome_mode"
        const val KEY_MANUAL_CADENCE = "manual_cadence_spm"
        const val KEY_CLICK_VOLUME = "click_volume"

        fun create(context: Context): RunSettings {
            val prefs = context.applicationContext.getSharedPreferences("atlas_run_settings", Context.MODE_PRIVATE)
            return RunSettings(object : SettingsStore {
                override fun getString(key: String): String? = prefs.getString(key, null)
                override fun putString(key: String, value: String) { prefs.edit().putString(key, value).apply() }
            })
        }
    }
}
