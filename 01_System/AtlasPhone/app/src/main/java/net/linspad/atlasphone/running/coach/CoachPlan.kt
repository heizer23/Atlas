package net.linspad.atlasphone.running.coach

import org.json.JSONArray
import org.json.JSONObject

/**
 * Phone model and tolerant-but-safe parser of CoachPlanV1. The shape is declared once in
 * 03_Application/RunningTracker/backend/coach_plan.py; parity is enforced by tests/fixtures/coach_plan_golden.json.
 * The server already validated every bound; the phone only enforces what the engine needs to be safe.
 */
enum class SegmentKind(val wire: String) {
    WARMUP("warmup"), STEADY("steady"), WORK("work"), RECOVERY("recovery"), COOLDOWN("cooldown");

    companion object { fun parse(s: String): SegmentKind? = entries.firstOrNull { it.wire == s } }
}

enum class CoachTrigger(val wire: String) {
    HR_HIGH("hr_high"), HR_LOW("hr_low"), PACE_FAST("pace_fast"), PACE_SLOW("pace_slow"),
    CADENCE_LOW("cadence_low"), CADENCE_HIGH("cadence_high"), SEGMENT_CHANGE("segment_change"),
    KEEP_RHYTHM("keep_rhythm"), SENSOR_LOST("sensor_lost");

    companion object { fun parse(s: String): CoachTrigger? = entries.firstOrNull { it.wire == s } }
}

/** Inclusive range; for pace lo = fast_s_per_km (smaller), hi = slow_s_per_km. */
data class TargetRange(val lo: Double, val hi: Double)

/** null target = dimension not coached in this segment. */
data class CoachSegment(
    val kind: SegmentKind,
    val durationS: Int,
    val hr: TargetRange?,
    val pace: TargetRange?,
    val cadence: TargetRange?,
)

class CoachPlan(
    val planId: String,
    val type: String,
    val title: String,
    val targetDistanceM: Double?,
    val segments: List<CoachSegment>,
    /** Empty in the wire plan = all triggers. */
    val triggers: Set<CoachTrigger>,
) {
    fun totalS(): Int = segments.sumOf { it.durationS }

    fun segmentStartS(index: Int): Int = segments.take(index).sumOf { it.durationS }

    /** Index of the segment containing activeS ([start, end)); null at or after totalS (or before 0). */
    fun segmentIndexAt(activeS: Double): Int? {
        if (activeS < 0) return null
        var start = 0
        for ((i, s) in segments.withIndex()) {
            if (activeS >= start && activeS < start + s.durationS) return i
            start += s.durationS
        }
        return null
    }

    fun enabled(trigger: CoachTrigger): Boolean = triggers.isEmpty() || trigger in triggers
}

sealed class CoachPlanParse {
    data class Ok(val plan: CoachPlan) : CoachPlanParse()
    data class Unsupported(val schemaVersion: Int) : CoachPlanParse()
    data class Invalid(val reason: String) : CoachPlanParse()
}

const val COACH_PLAN_SCHEMA_VERSION = 1

/** Parses the `plan` object of NextPlanResponse. Never throws. */
fun parseCoachPlan(planId: String, planJson: String): CoachPlanParse = try {
    val o = JSONObject(planJson)
    val version = o.optInt("schema_version", -1)
    when {
        !o.has("schema_version") || version < 0 -> CoachPlanParse.Invalid("schema_version")
        version != COACH_PLAN_SCHEMA_VERSION -> CoachPlanParse.Unsupported(version)
        else -> parseV1(planId, o)
    }
} catch (e: Exception) {
    CoachPlanParse.Invalid("malformed")
}

private fun range(seg: JSONObject, key: String, loKey: String, hiKey: String): TargetRange? {
    if (!seg.has(key) || seg.isNull(key)) return null
    val r = seg.getJSONObject(key)
    val lo = r.getDouble(loKey)
    val hi = r.getDouble(hiKey)
    require(lo < hi) { "range" }
    return TargetRange(lo, hi)
}

private fun parseV1(planId: String, o: JSONObject): CoachPlanParse {
    val segs = o.getJSONArray("segments")
    if (segs.length() == 0) return CoachPlanParse.Invalid("segments")
    val segments = (0 until segs.length()).map { i ->
        val s = segs.getJSONObject(i)
        val kind = SegmentKind.parse(s.getString("kind")) ?: return CoachPlanParse.Invalid("segment_kind")
        val duration = s.getInt("duration_s")
        if (duration <= 0) return CoachPlanParse.Invalid("duration")
        CoachSegment(kind, duration, range(s, "hr", "min", "max"), range(s, "pace", "fast_s_per_km", "slow_s_per_km"), range(s, "cadence", "min", "max"))
    }
    val triggers = mutableSetOf<CoachTrigger>()
    val arr: JSONArray? = o.optJSONArray("triggers")
    if (arr != null) for (i in 0 until arr.length()) triggers += CoachTrigger.parse(arr.getString(i)) ?: return CoachPlanParse.Invalid("trigger")
    return CoachPlanParse.Ok(CoachPlan(
        planId, o.getString("type"), o.getString("title"),
        if (o.has("target_distance_m") && !o.isNull("target_distance_m")) o.getDouble("target_distance_m") else null,
        segments, triggers,
    ))
}
