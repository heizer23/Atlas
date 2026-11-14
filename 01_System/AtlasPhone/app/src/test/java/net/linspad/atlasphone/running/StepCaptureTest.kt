package net.linspad.atlasphone.running

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import net.linspad.atlasphone.mobile.capture.AppendResult
import net.linspad.atlasphone.mobile.capture.CaptureStore
import net.linspad.atlasphone.mobile.model.RawStep
import net.linspad.atlasphone.mobile.model.SampleJson
import net.linspad.atlasphone.mobile.model.Stream
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionLogic
import net.linspad.atlasphone.mobile.steps.StepDetector
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class StepCaptureTest {
    private lateinit var context: Context
    private val dbName = "test_steps.db"
    private val stores = mutableListOf<CaptureStore>()

    @Before fun setUp() { context = ApplicationProvider.getApplicationContext(); context.deleteDatabase(dbName) }
    @After fun tearDown() { stores.forEach { it.close() }; context.deleteDatabase(dbName) }

    @Test fun batchedStepKeepsItsEventTime() {
        // event happened 800 ms before it was delivered
        val raw = StepDetector.toRaw(eventNanos = 10_000_000_000L, nowMillis = 1_700_000_000_000L, nowElapsedNanos = 10_800_000_000L)
        assertEquals(1_700_000_000_000L - 800, raw.timestampMillis)
        assertEquals(10_000_000_000L, raw.elapsedRealtimeNanos)
        val json = SampleJson.step(raw, "cap", 7)
        assertEquals("step.sample", json.getString("type")); assertEquals("cap", json.getString("captureId")); assertEquals(7L, json.getLong("sequence"))
        assertEquals(SampleJson.iso(1_700_000_000_000L - 800), json.getString("timestamp"))
        assertEquals(10_000_000_000L, json.getLong("elapsedRealtimeNanos"))
    }

    @Test fun streamApiNames() {
        assertEquals(listOf("location", "heart_rate", "step"), Stream.entries.map { it.apiName })
        assertEquals("step.sample", Stream.STEP.wireName)
    }

    @Test fun storeCountsStepsSeparatelyAndSharesOneSequence() {
        val store = CaptureStore(context, dbName).also { stores += it }
        val id = store.createCapture("c")
        assertTrue(store.append(id, Stream.LOCATION, 1) { "{}" } is AppendResult.Stored)
        assertTrue(store.append(id, Stream.STEP, 2) { "{}" } is AppendResult.Stored)
        assertTrue(store.append(id, Stream.STEP, 3) { "{}" } is AppendResult.Stored)
        assertTrue(store.append(id, Stream.HEART_RATE, 4) { "{}" } is AppendResult.Stored)
        val i = store.info(id)!!
        assertEquals(1L, i.locationCount); assertEquals(1L, i.heartRateCount); assertEquals(2L, i.stepCount)
        assertEquals(4L, i.lastSequence)
        val fetched = store.fetch(id)
        assertEquals(listOf(1L, 2L, 3L, 4L), fetched.map { it.sequence })
        assertEquals(listOf(Stream.LOCATION, Stream.STEP, Stream.STEP, Stream.HEART_RATE), fetched.map { it.stream })
    }

    @Test fun versionTwoDatabaseUpgradesKeepingCapturesAndSamples() {
        val v2 = context.openOrCreateDatabase(dbName, Context.MODE_PRIVATE, null)
        v2.execSQL("""CREATE TABLE captures (id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, ended_at INTEGER, next_seq INTEGER NOT NULL DEFAULT 1,
            location_count INTEGER NOT NULL DEFAULT 0, hr_count INTEGER NOT NULL DEFAULT 0, unacked INTEGER NOT NULL DEFAULT 0, dropped INTEGER NOT NULL DEFAULT 0)""")
        v2.execSQL("""CREATE TABLE samples (capture_id TEXT NOT NULL, seq INTEGER NOT NULL, stream TEXT NOT NULL, ts INTEGER NOT NULL,
            payload TEXT NOT NULL, acked INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (capture_id, seq))""")
        v2.execSQL("CREATE TABLE run_meta (capture_id TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at INTEGER NOT NULL)")
        v2.execSQL("INSERT INTO captures (id, started_at, next_seq, location_count, hr_count, unacked) VALUES ('old', 1000, 3, 1, 1, 2)")
        v2.execSQL("INSERT INTO samples (capture_id, seq, stream, ts, payload) VALUES ('old', 1, 'LOCATION', 1001, '{}'), ('old', 2, 'HEART_RATE', 1002, '{}')")
        v2.execSQL("INSERT INTO run_meta VALUES ('old', '{\"x\":1}', 5)")
        v2.version = 2
        v2.close()

        val store = CaptureStore(context, dbName).also { stores += it }
        val info = store.info("old")!!
        assertEquals(1L, info.locationCount); assertEquals(1L, info.heartRateCount); assertEquals(0L, info.stepCount); assertEquals(2L, info.unacked)
        assertEquals(listOf(1L, 2L), store.fetch("old").map { it.sequence })
        assertEquals("""{"x":1}""", store.getRunMeta("old"))
        assertTrue(store.append("old", Stream.STEP, 1003) { "{}" } is AppendResult.Stored)
        assertEquals(1L, store.info("old")!!.stepCount); assertEquals(1L, store.info("old")!!.heartRateCount)
    }

    @Test fun activityRecognitionPermissionOnlyFromAndroid10() {
        assertEquals(emptyList<String>(), PermissionLogic.required(Capability.ACTIVITY_RECOGNITION, 28))
        assertEquals(listOf(PermissionLogic.ACTIVITY_RECOGNITION), PermissionLogic.required(Capability.ACTIVITY_RECOGNITION, 29))
        assertEquals(listOf(PermissionLogic.ACTIVITY_RECOGNITION), PermissionLogic.required(Capability.ACTIVITY_RECOGNITION, 34))
        assertEquals(PermissionLogic.required(Capability.ACTIVITY_RECOGNITION, 34), PermissionLogic.toRequest(Capability.ACTIVITY_RECOGNITION, 34))
        assertEquals(listOf(PermissionLogic.FINE_LOCATION), PermissionLogic.required(Capability.LOCATION, 34))
        assertEquals(listOf(PermissionLogic.BLUETOOTH_SCAN, PermissionLogic.BLUETOOTH_CONNECT), PermissionLogic.required(Capability.BLUETOOTH, 34))
    }
}
