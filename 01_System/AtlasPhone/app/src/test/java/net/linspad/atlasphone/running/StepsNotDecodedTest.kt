package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.CaptureSample
import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.mobile.model.RawStep
import net.linspad.atlasphone.mobile.model.SampleJson
import net.linspad.atlasphone.mobile.model.Stream
import net.linspad.atlasphone.running.session.decodeSamples
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

// Robolectric only because org.json needs the Android implementation on the JVM.
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class StepsNotDecodedTest {
    @Test fun stepsAreNeverDecodedAsHeartRateOrLocation() {
        val t = 1_700_000_000_000L
        val step = SampleJson.step(RawStep(t, 1L), "cap", 2).toString()
        val loc = SampleJson.location(RawLocation(t, 50.0, 8.0, 5f, 3f, null, null), "cap", 1).toString()
        val hr = SampleJson.heartRate(RawHeartRate(t, 150, null), "cap", 3).toString()
        val batch = listOf(
            CaptureSample("cap", 1, Stream.LOCATION, t, loc),
            CaptureSample("cap", 2, Stream.STEP, t, step),
            CaptureSample("cap", 3, Stream.HEART_RATE, t, hr),
            CaptureSample("cap", 4, Stream.STEP, t, step),
        )
        val locations = ArrayList<RawLocation>(); val heartRates = ArrayList<RawHeartRate>()
        decodeSamples(batch, locations, heartRates)
        assertEquals(1, locations.size)
        assertEquals(1, heartRates.size)
        assertEquals(150, heartRates[0].bpm)
    }
}
