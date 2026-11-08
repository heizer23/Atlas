package net.linspad.atlasphone.mobile.location

import net.linspad.atlasphone.mobile.model.RawLocation

/** Pure mapping from provider values to [RawLocation]; unavailable values become null (never fabricated). */
object LocationMapper {
    fun map(
        timeMillis: Long, nowMillis: Long,
        latitude: Double, longitude: Double,
        hasAccuracy: Boolean, accuracy: Float,
        hasSpeed: Boolean, speed: Float,
        hasAltitude: Boolean, altitude: Double,
        hasBearing: Boolean, bearing: Float,
    ): RawLocation? {
        if (latitude.isNaN() || longitude.isNaN()) return null
        if (latitude !in -90.0..90.0 || longitude !in -180.0..180.0) return null
        return RawLocation(
            // A fix without its own time would otherwise get the epoch; use arrival time instead.
            timestampMillis = if (timeMillis > 0) timeMillis else nowMillis,
            latitude = latitude,
            longitude = longitude,
            accuracyMeters = accuracy.takeIf { hasAccuracy && it >= 0f && !it.isNaN() },
            speedMetersPerSecond = speed.takeIf { hasSpeed && it >= 0f && !it.isNaN() },
            altitudeMeters = altitude.takeIf { hasAltitude && !it.isNaN() },
            bearingDegrees = bearing.takeIf { hasBearing && it in 0f..360f },
        )
    }
}
