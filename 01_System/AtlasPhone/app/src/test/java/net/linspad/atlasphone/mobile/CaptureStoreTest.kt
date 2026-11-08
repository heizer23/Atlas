package net.linspad.atlasphone.mobile

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.runBlocking
import net.linspad.atlasphone.mobile.capture.AppendResult
import net.linspad.atlasphone.mobile.capture.CaptureRecorder
import net.linspad.atlasphone.mobile.capture.CaptureStore
import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.mobile.model.SampleJson
import net.linspad.atlasphone.mobile.model.Stream
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CaptureStoreTest {
    private lateinit var context: Context
    private val dbName = "test_captures.db"
    private val stores = mutableListOf<CaptureStore>()

    private fun open(max: Long = 100_000) = CaptureStore(context, dbName, max).also { stores.add(it) }

    @Before fun setUp() { context = ApplicationProvider.getApplicationContext(); context.deleteDatabase(dbName) }
    @After fun tearDown() { stores.forEach { it.close() }; context.deleteDatabase(dbName) }

    private fun CaptureStore.add(id: String, stream: Stream = Stream.LOCATION, ts: Long = 1000L) =
        append(id, stream, ts) { "{\"s\":$it}" }

    @Test fun sequencesAreUniqueAndSharedAcrossStreams() {
        val s = open(); val id = s.createCapture()
        val seqs = listOf(Stream.LOCATION, Stream.HEART_RATE, Stream.LOCATION).map { (s.add(id, it) as AppendResult.Stored).sequence }
        assertEquals(listOf(1L, 2L, 3L), seqs)
        val info = s.info(id)!!
        assertEquals(2, info.locationCount); assertEquals(1, info.heartRateCount); assertEquals(3, info.lastSequence)
    }

    @Test fun fetchUsesCursorSoNothingIsDeliveredTwice() {
        val s = open(); val id = s.createCapture()
        repeat(5) { s.add(id) }
        val first = s.fetch(id, 0, 3)
        assertEquals(listOf(1L, 2L, 3L), first.map { it.sequence })
        val second = s.fetch(id, first.last().sequence, 10)
        assertEquals(listOf(4L, 5L), second.map { it.sequence })
        assertTrue(s.fetch(id, 5).isEmpty())
    }

    @Test fun samplesSurviveReopeningTheDatabase() {
        val s = open(); val id = s.createCapture()
        repeat(3) { s.add(id) }
        s.close()
        val again = open()
        assertEquals(listOf(1L, 2L, 3L), again.fetch(id).map { it.sequence })
        // sequence continues, no reuse after restart
        assertEquals(4L, (again.add(id) as AppendResult.Stored).sequence)
        assertEquals(listOf(id), again.openCaptures().map { it.id })
    }

    @Test fun ackAndPurgeOnlyRemoveAcknowledgedSamples() {
        val s = open(); val id = s.createCapture()
        repeat(5) { s.add(id) }
        assertEquals(3, s.ack(id, 3))
        assertEquals(2, s.info(id)!!.unacked)
        assertEquals(0, s.ack(id, 3)) // idempotent
        assertEquals(3, s.purgeAcked(id))
        assertEquals(listOf(4L, 5L), s.fetch(id).map { it.sequence })
    }

    @Test fun unacknowledgedDataIsNeverDeletedWithoutForce() {
        val s = open(); val id = s.createCapture()
        s.add(id)
        assertFalse(s.deleteCapture(id))
        assertNotNull(s.info(id))
        s.ack(id, 1)
        assertTrue(s.deleteCapture(id))
        assertEquals(null, s.info(id))
    }

    @Test fun overflowRefusesNewSamplesButKeepsOldOnes() {
        val s = open(max = 3); val id = s.createCapture()
        val results = (1..5).map { s.add(id) }
        assertEquals(3, results.count { it is AppendResult.Stored })
        assertEquals(2, results.count { it == AppendResult.Overflow })
        assertEquals(2, s.info(id)!!.dropped)
        assertEquals(listOf(1L, 2L, 3L), s.fetch(id).map { it.sequence })
        // acknowledging frees room again
        s.ack(id, 3)
        assertTrue(s.add(id) is AppendResult.Stored)
    }

    @Test fun verifyRetrievalReportsOkForAHealthyCapture() {
        val s = open(); val id = s.createCapture()
        repeat(20) { s.add(id) }
        assertTrue(s.verifyRetrieval(id), s.verifyRetrieval(id).startsWith("OK: 20"))
    }

    @Test fun appendToUnknownCaptureIsReported() = assertEquals(AppendResult.UnknownCapture, open().add("nope"))

    @Test fun finishAndReopenKeepTheSameId() {
        val s = open(); val id = s.createCapture("fixed-id")
        assertEquals("fixed-id", id)
        s.finishCapture(id)
        assertFalse(s.info(id)!!.isOpen)
        s.reopenCapture(id)
        assertTrue(s.info(id)!!.isOpen)
        assertEquals("fixed-id", s.createCapture("fixed-id")) // idempotent
        assertEquals(1, s.list().size)
    }

    @Test fun payloadJsonMatchesTheContract() {
        val loc = SampleJson.location(RawLocation(1_762_511_415_000, 53.5753, 10.0153, 4.2f, null, 18.4, null), "cap", 7)
        assertEquals("location.sample", loc.getString("type"))
        assertEquals("2025-11-07T10:30:15.000Z", loc.getString("timestamp"))
        assertTrue(loc.isNull("speedMetersPerSecond")); assertTrue(loc.isNull("bearingDegrees"))
        assertEquals(7L, loc.getLong("sequence")); assertEquals("cap", loc.getString("captureId"))
        val hr = SampleJson.heartRate(RawHeartRate(1_762_511_415_123, 152, listOf(400, 410)), "cap", 8)
        assertEquals("heartRate.sample", hr.getString("type")); assertEquals(152, hr.getInt("bpm"))
        assertEquals("bluetooth", hr.getString("source")); assertEquals(2, hr.getJSONArray("rrIntervalsMs").length())
        assertEquals("2025-11-07T10:30:15.123Z", hr.getString("timestamp"))
        assertTrue(SampleJson.heartRate(RawHeartRate(1, 60, null), null, null).isNull("rrIntervalsMs"))
    }

    // ── recorder ────────────────────────────────────────────────────────────

    @Test fun recorderStoresBothStreamsWithIndependentTimestamps() = runBlocking<Unit> {
        val s = open()
        val locations = MutableSharedFlow<RawLocation>(extraBufferCapacity = 16)
        val hrs = MutableSharedFlow<RawHeartRate>(extraBufferCapacity = 16)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val rec = CaptureRecorder(s, scope, Dispatchers.IO, locations, hrs)
        val id = rec.start()
        waitUntil { locations.subscriptionCount.value > 0 && hrs.subscriptionCount.value > 0 }

        locations.emit(RawLocation(10_000, 53.0, 10.0, 5f, 2f, null, null))
        hrs.emit(RawHeartRate(10_400, 150, null))
        locations.emit(RawLocation(11_000, 53.0001, 10.0, 5f, 2f, null, null))
        waitUntil { s.info(id)!!.lastSequence == 3L }

        val stored = s.fetch(id)
        assertEquals(3, stored.size)
        assertEquals(listOf(10_000L, 10_400L, 11_000L), stored.map { it.timestampMillis }.sorted())
        stored.forEach { assertEquals(id, JSONObject(it.json).getString("captureId")); assertEquals(it.sequence, JSONObject(it.json).getLong("sequence")) }

        rec.stop()
        assertEquals(null, rec.active.value)
        assertFalse(s.info(id)!!.isOpen)
        locations.emit(RawLocation(12_000, 1.0, 1.0, null, null, null, null))
        Thread.sleep(150)
        assertEquals(3, s.info(id)!!.locationCount + s.info(id)!!.heartRateCount) // nothing recorded after stop
        scope.coroutineContext[kotlinx.coroutines.Job]?.cancel()
    }

    @Test fun recorderCanContinueAnInterruptedCapture() = runBlocking<Unit> {
        val s = open()
        val locations = MutableSharedFlow<RawLocation>(extraBufferCapacity = 16)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val id = s.createCapture(); s.add(id); s.add(id) // pretend the process died after 2 samples
        val rec = CaptureRecorder(s, scope, Dispatchers.IO, locations, MutableSharedFlow())
        assertEquals(id, rec.start(id))
        waitUntil { locations.subscriptionCount.value > 0 }
        locations.emit(RawLocation(1, 1.0, 1.0, null, null, null, null))
        waitUntil { s.info(id)!!.lastSequence == 3L }
        rec.stop()
        scope.coroutineContext[kotlinx.coroutines.Job]?.cancel()
    }

    private fun waitUntil(cond: () -> Boolean) {
        val end = System.currentTimeMillis() + 5000
        while (System.currentTimeMillis() < end && !cond()) Thread.sleep(10)
        assertTrue("condition not reached", cond())
    }
}
