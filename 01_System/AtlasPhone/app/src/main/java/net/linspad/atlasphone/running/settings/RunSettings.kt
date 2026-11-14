package net.linspad.atlasphone.running.settings

import android.content.Context
import net.linspad.atlasphone.running.hr.HrSmoothingMode

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

    companion object {
        const val KEY_HR_SMOOTHING = "hr_smoothing"

        fun create(context: Context): RunSettings {
            val prefs = context.applicationContext.getSharedPreferences("atlas_run_settings", Context.MODE_PRIVATE)
            return RunSettings(object : SettingsStore {
                override fun getString(key: String): String? = prefs.getString(key, null)
                override fun putString(key: String, value: String) { prefs.edit().putString(key, value).apply() }
            })
        }
    }
}
