package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.SampleJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RunLifecycleTest {
    /** Every legal (state, event) -> state transition; everything else must be illegal. */
    private val legal: Map<Pair<RunState?, RunEvent>, RunState> = mapOf(
        (null to RunEvent.START) to RunState.RECORDING,                    // free run
        (RunState.PREPARED to RunEvent.START) to RunState.RECORDING,
        (RunState.RECORDING to RunEvent.PAUSE) to RunState.PAUSED,
        (RunState.PAUSED to RunEvent.RESUME) to RunState.RECORDING,
        (RunState.RECORDING to RunEvent.FINISH) to RunState.COMPLETED_LOCAL,
        (RunState.PAUSED to RunEvent.FINISH) to RunState.COMPLETED_LOCAL,
        (RunState.COMPLETED_LOCAL to RunEvent.QUEUE_UPLOAD) to RunState.PENDING_UPLOAD,
        (RunState.PENDING_UPLOAD to RunEvent.SYNCED) to RunState.SYNCED,
        (null to RunEvent.RECOVER) to RunState.PAUSED,                     // recovery enters paused
        (RunState.RECORDING to RunEvent.RECOVER) to RunState.PAUSED,
        (RunState.PAUSED to RunEvent.RECOVER) to RunState.PAUSED,
    )

    @Test fun allEventsAppliedToAllStates() {
        for (state in listOf<RunState?>(null) + RunState.entries) {
            for (event in RunEvent.entries) {
                assertEquals("$state + $event", legal[state to event], RunLifecycle.next(state, event))
            }
        }
    }

    @Test fun happyPathWalksTheWholeLifecycle() {
        var s: RunState? = null
        for (e in listOf(RunEvent.START, RunEvent.PAUSE, RunEvent.RESUME, RunEvent.PAUSE, RunEvent.RESUME, RunEvent.FINISH, RunEvent.QUEUE_UPLOAD, RunEvent.SYNCED)) {
            s = RunLifecycle.next(s, e)!!
        }
        assertEquals(RunState.SYNCED, s)
        assertNull(RunLifecycle.next(RunState.SYNCED, RunEvent.START)) // a synced run cannot be restarted
    }

    @Test fun runMetaSurvivesAJsonRoundTrip() {
        val meta = RunMeta(
            "run-1", RunState.PENDING_UPLOAD, "ABC234", "Easy 5k", 1_700_000_000_000, 1_700_001_800_000,
            listOf(PauseRecord(1_700_000_100_000, 1_700_000_160_000, 100.0, 160.0), PauseRecord(1_700_000_900_000, null, 900.0, null)),
            RunSummary(1800.0, 1740.5, 5012.3, 347.2, 151.25), 1200, "Atlas not reachable", true,
        )
        assertEquals(meta, RunMeta.fromJson(meta.toJson()))
        val bare = RunMeta("free", RunState.RECORDING, null, null, 5, null, emptyList(), null, 0, null, false)
        assertEquals(bare, RunMeta.fromJson(bare.toJson()))
    }

    @Test fun sampleDecoderReadsStoredPayloads() {
        val loc = net.linspad.atlasphone.mobile.model.RawLocation(1_700_000_000_123, 52.5, 13.4, 4.5f, null, null, null, 77L)
        val decoded = SampleDecoder.location(SampleJson.location(loc, "c", 1).toString())!!
        assertEquals(1_700_000_000_123, decoded.timestampMillis)
        assertEquals(77L, decoded.elapsedRealtimeNanos)
        assertEquals(4.5f, decoded.accuracyMeters)
        val hr = SampleDecoder.heartRate(SampleJson.heartRate(net.linspad.atlasphone.mobile.model.RawHeartRate(1_700_000_000_500, 142, null), "c", 2).toString())!!
        assertEquals(142, hr.bpm); assertNull(hr.elapsedRealtimeNanos)
        assertNull(SampleDecoder.location("not json"))
    }
}
