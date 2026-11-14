package net.linspad.atlasphone.running.recap

import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.hr.HrSmoothing

/** Same values as the backend HRR_* constants (backend/config.py); REMINDER_MS is phone only. */
object RecoveryConfig {
    const val END_BEFORE_S = 3.0
    const val END_AFTER_S = 2.0
    const val POINT_HALF_WINDOW_S = 3.0
    const val MIN_VALID_SAMPLES = 2
    const val T1_S = 60.0
    const val T2_S = 120.0
    const val REMINDER_MS = 900_000L
}

/** HRR1 scalars (the curve is server-only). Parity with backend/recovery.py via tests/fixtures/recovery_golden.json. */
object RecoveryMetrics {
    private fun ms(seconds: Double) = Math.round(seconds * 1000.0)

    private fun median(vals: List<Int>): Double {
        val s = vals.sorted()
        return if (s.size % 2 == 1) s[s.size / 2].toDouble() else (s[s.size / 2 - 1] + s[s.size / 2]) / 2.0
    }

    fun compute(hr: List<HrPoint>, runFinishedAtMillis: Long, trainingEndMillis: Long): RecoverySummary {
        val valid = HrSmoothing.validSamples(hr)
        fun point(offsetS: Double, beforeS: Double, afterS: Double): Double? {
            val a = runFinishedAtMillis + ms(offsetS - beforeS)
            val b = runFinishedAtMillis + ms(offsetS + afterS)
            if (b > trainingEndMillis) return null // window not fully observed
            val vals = valid.filter { it.tsMillis in a..b }.map { it.bpm }
            return if (vals.size < RecoveryConfig.MIN_VALID_SAMPLES) null else median(vals)
        }
        val end = point(0.0, RecoveryConfig.END_BEFORE_S, RecoveryConfig.END_AFTER_S)
        val h60 = point(RecoveryConfig.T1_S, RecoveryConfig.POINT_HALF_WINDOW_S, RecoveryConfig.POINT_HALF_WINDOW_S)
        val h120 = point(RecoveryConfig.T2_S, RecoveryConfig.POINT_HALF_WINDOW_S, RecoveryConfig.POINT_HALF_WINDOW_S)
        return RecoverySummary(end, h60, h120, if (end != null && h60 != null) end - h60 else null, if (end != null && h120 != null) end - h120 else null)
    }
}
