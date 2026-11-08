package net.linspad.atlasphone.mobile

import net.linspad.atlasphone.mobile.heartrate.HeartRateParser
import net.linspad.atlasphone.mobile.heartrate.ReconnectPolicy
import net.linspad.atlasphone.mobile.location.LocationMapper
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionLogic
import net.linspad.atlasphone.mobile.permissions.PermissionStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HeartRateParserTest {
    private fun b(vararg v: Int) = ByteArray(v.size) { v[it].toByte() }

    @Test fun eightBitValueWithoutExtras() {
        val p = HeartRateParser.parse(b(0x00, 152))!!
        assertEquals(152, p.bpm); assertNull(p.rrIntervalsMs); assertNull(p.sensorContact)
    }

    @Test fun sixteenBitValue() {
        // 0x012C = 300
        assertEquals(300, HeartRateParser.parse(b(0x01, 0x2C, 0x01))!!.bpm)
    }

    @Test fun rrIntervalsAreConvertedFromOneOver1024Seconds() {
        // flags: RR present (0x10); RR 1024 -> 1000 ms, 512 -> 500 ms
        val p = HeartRateParser.parse(b(0x10, 60, 0x00, 0x04, 0x00, 0x02))!!
        assertEquals(listOf(1000, 500), p.rrIntervalsMs)
    }

    @Test fun energyExpendedFieldIsSkipped() {
        // flags: energy (0x08) + RR (0x10); bpm 70, energy 2 bytes, RR 1024
        val p = HeartRateParser.parse(b(0x18, 70, 0xAA, 0xBB, 0x00, 0x04))!!
        assertEquals(70, p.bpm); assertEquals(listOf(1000), p.rrIntervalsMs)
    }

    @Test fun sensorContactBits() {
        assertEquals(true, HeartRateParser.parse(b(0x06, 80))!!.sensorContact)   // 3 = detected
        assertEquals(false, HeartRateParser.parse(b(0x04, 80))!!.sensorContact)  // 2 = not detected
        assertNull(HeartRateParser.parse(b(0x02, 80))!!.sensorContact)           // 1 = not supported
    }

    @Test fun rejectsTruncatedOrEmptyPayloads() {
        assertNull(HeartRateParser.parse(null)); assertNull(HeartRateParser.parse(b())); assertNull(HeartRateParser.parse(b(0x00)))
        assertNull(HeartRateParser.parse(b(0x01, 0x10))) // 16-bit flag but only one value byte
    }

    @Test fun trailingOddByteInRrBlockIsIgnored() {
        assertEquals(listOf(1000), HeartRateParser.parse(b(0x10, 60, 0x00, 0x04, 0x07))!!.rrIntervalsMs)
    }
}

class ReconnectPolicyTest {
    @Test fun backsOffExponentiallyAndCaps() {
        val p = ReconnectPolicy(maxAttempts = 6, baseDelayMs = 1000, maxDelayMs = 8000)
        assertEquals(listOf(1000L, 2000L, 4000L, 8000L, 8000L, 8000L), (1..6).map { p.delayFor(it) })
    }

    @Test fun givesUpAfterMaxAttempts() {
        val p = ReconnectPolicy(maxAttempts = 3)
        assertNull(p.delayFor(4)); assertNull(p.delayFor(0))
    }
}

class PermissionLogicTest {
    @Test fun statusMapping() {
        assertEquals(PermissionStatus.GRANTED, PermissionLogic.status(true, false, false))
        assertEquals(PermissionStatus.GRANTED, PermissionLogic.status(true, true, false))
        assertEquals(PermissionStatus.NOT_REQUESTED, PermissionLogic.status(false, false, false))
        assertEquals(PermissionStatus.DENIED, PermissionLogic.status(false, true, true))
        assertEquals(PermissionStatus.BLOCKED, PermissionLogic.status(false, true, false))
    }

    @Test fun bluetoothPermissionsDependOnAndroidVersion() {
        assertEquals(listOf(PermissionLogic.BLUETOOTH_SCAN, PermissionLogic.BLUETOOTH_CONNECT), PermissionLogic.required(Capability.BLUETOOTH, 33))
        assertEquals(listOf(PermissionLogic.FINE_LOCATION), PermissionLogic.required(Capability.BLUETOOTH, 30))
    }

    @Test fun locationRequestIncludesCoarseButRequiresFine() {
        assertEquals(listOf(PermissionLogic.FINE_LOCATION), PermissionLogic.required(Capability.LOCATION, 34))
        assertTrue(PermissionLogic.toRequest(Capability.LOCATION, 34).contains(PermissionLogic.COARSE_LOCATION))
    }
}

class LocationMapperTest {
    private fun map(
        time: Long = 1000, lat: Double = 53.5, lon: Double = 10.0,
        acc: Pair<Boolean, Float> = true to 4.2f, speed: Pair<Boolean, Float> = true to 2.1f,
        alt: Pair<Boolean, Double> = true to 18.4, bearing: Pair<Boolean, Float> = true to 92f,
    ) = LocationMapper.map(time, 5000, lat, lon, acc.first, acc.second, speed.first, speed.second, alt.first, alt.second, bearing.first, bearing.second)

    @Test fun mapsAllValues() {
        val l = map()!!
        assertEquals(4.2f, l.accuracyMeters); assertEquals(2.1f, l.speedMetersPerSecond); assertEquals(18.4, l.altitudeMeters!!, 0.0)
        assertEquals(92f, l.bearingDegrees); assertEquals(1000, l.timestampMillis)
    }

    @Test fun missingValuesAreNullNotZero() {
        val l = map(acc = false to 0f, speed = false to 0f, alt = false to 0.0, bearing = false to 0f)!!
        assertNull(l.accuracyMeters); assertNull(l.speedMetersPerSecond); assertNull(l.altitudeMeters); assertNull(l.bearingDegrees)
    }

    @Test fun fixWithoutTimeUsesArrivalTime() = assertEquals(5000, map(time = 0)!!.timestampMillis)

    @Test fun rejectsInvalidCoordinates() {
        assertNull(map(lat = Double.NaN)); assertNull(map(lat = 91.0)); assertNull(map(lon = 181.0))
    }

    @Test fun rejectsNegativeOrNanSpeedAndAccuracy() {
        val l = map(speed = true to -1f, acc = true to Float.NaN)!!
        assertNull(l.speedMetersPerSecond); assertNull(l.accuracyMeters)
    }
}
