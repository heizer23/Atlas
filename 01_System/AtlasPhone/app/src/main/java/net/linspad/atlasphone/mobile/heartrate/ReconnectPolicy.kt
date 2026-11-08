package net.linspad.atlasphone.mobile.heartrate

/** Bounded exponential backoff: attempts 1..maxAttempts, then give up until a manual reconnect. */
class ReconnectPolicy(
    val maxAttempts: Int = 5,
    private val baseDelayMs: Long = 1_000,
    private val maxDelayMs: Long = 16_000,
) {
    /** Delay before attempt number [attempt] (1-based), or null when attempts are exhausted. */
    fun delayFor(attempt: Int): Long? {
        if (attempt < 1 || attempt > maxAttempts) return null
        val shift = (attempt - 1).coerceAtMost(20)
        return minOf(maxDelayMs, baseDelayMs shl shift)
    }
}
