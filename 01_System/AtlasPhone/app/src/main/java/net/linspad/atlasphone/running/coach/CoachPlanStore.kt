package net.linspad.atlasphone.running.coach

import android.content.Context
import net.linspad.atlasphone.running.settings.SettingsStore

/**
 * Local cache of the active coach plan (SharedPreferences atlas_coach: plan_id, plan_json, fetched_at epoch ms for display only).
 * Recreatable from the server (P4); never uploaded. A cleared cache is stored as empty strings.
 */
class CoachPlanStore(private val store: SettingsStore) {
    /** Parse of the cached plan; null when nothing is cached. */
    fun load(): CoachPlanParse? {
        val id = store.getString(KEY_ID)?.takeIf { it.isNotEmpty() } ?: return null
        val json = store.getString(KEY_JSON)?.takeIf { it.isNotEmpty() } ?: return null
        return parseCoachPlan(id, json)
    }

    fun save(planId: String, planJson: String, nowMillis: Long) {
        store.putString(KEY_ID, planId)
        store.putString(KEY_JSON, planJson)
        store.putString(KEY_FETCHED, nowMillis.toString())
    }

    /** The server said there is no active plan. */
    fun clear() {
        store.putString(KEY_ID, "")
        store.putString(KEY_JSON, "")
        store.putString(KEY_FETCHED, "")
    }

    fun fetchedAtMillis(): Long? = store.getString(KEY_FETCHED)?.toLongOrNull()

    companion object {
        const val KEY_ID = "plan_id"
        const val KEY_JSON = "plan_json"
        const val KEY_FETCHED = "fetched_at"

        fun create(context: Context): CoachPlanStore {
            val prefs = context.applicationContext.getSharedPreferences("atlas_coach", Context.MODE_PRIVATE)
            return CoachPlanStore(object : SettingsStore {
                override fun getString(key: String): String? = prefs.getString(key, null)
                override fun putString(key: String, value: String) { prefs.edit().putString(key, value).apply() }
            })
        }
    }
}
