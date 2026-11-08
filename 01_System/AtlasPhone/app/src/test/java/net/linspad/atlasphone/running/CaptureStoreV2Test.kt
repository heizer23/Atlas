package net.linspad.atlasphone.running

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.test.core.app.ApplicationProvider
import net.linspad.atlasphone.mobile.capture.AppendResult
import net.linspad.atlasphone.mobile.capture.CaptureStore
import net.linspad.atlasphone.mobile.model.Stream
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Sprint 01 data must survive the CaptureStore v1 -> v2 upgrade (run_meta added, nothing else touched). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CaptureStoreV2Test {
    private lateinit var context: Context
    private val dbName = "test_upgrade.db"
    private val stores = mutableListOf<CaptureStore>()

    @Before fun setUp() { context = ApplicationProvider.getApplicationContext(); context.deleteDatabase(dbName) }
    @After fun tearDown() { stores.forEach { it.close() }; context.deleteDatabase(dbName) }

    @Test fun versionOneDatabaseUpgradesWithoutLosingCapturesOrSamples() {
        // Build a genuine v1 database by hand (the Sprint 01 schema) with one open capture and two samples.
        val v1 = context.openOrCreateDatabase(dbName, Context.MODE_PRIVATE, null)
        v1.execSQL("""CREATE TABLE captures (id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, ended_at INTEGER, next_seq INTEGER NOT NULL DEFAULT 1,
            location_count INTEGER NOT NULL DEFAULT 0, hr_count INTEGER NOT NULL DEFAULT 0, unacked INTEGER NOT NULL DEFAULT 0, dropped INTEGER NOT NULL DEFAULT 0)""")
        v1.execSQL("""CREATE TABLE samples (capture_id TEXT NOT NULL, seq INTEGER NOT NULL, stream TEXT NOT NULL, ts INTEGER NOT NULL,
            payload TEXT NOT NULL, acked INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (capture_id, seq))""")
        v1.execSQL("INSERT INTO captures (id, started_at, next_seq, location_count, hr_count, unacked) VALUES ('old', 1000, 3, 1, 1, 2)")
        v1.execSQL("INSERT INTO samples (capture_id, seq, stream, ts, payload) VALUES ('old', 1, 'LOCATION', 1001, '{\"a\":1}'), ('old', 2, 'HEART_RATE', 1002, '{\"b\":2}')")
        v1.version = 1
        v1.close()

        val store = CaptureStore(context, dbName).also { stores += it }
        val info = store.info("old")!!
        assertEquals(1L, info.locationCount); assertEquals(1L, info.heartRateCount); assertEquals(2L, info.unacked)
        assertTrue(info.isOpen)
        assertEquals(listOf(1L, 2L), store.fetch("old", 0).map { it.sequence })
        assertEquals(1, store.openCaptures().size)

        // the upgraded store still records into the old capture and supports run metadata
        assertTrue(store.append("old", Stream.LOCATION, 1003) { "{\"a\":$it}" } is AppendResult.Stored)
        assertNull(store.getRunMeta("old"))
        store.putRunMeta("old", """{"x":1}""")
        assertEquals("""{"x":1}""", store.getRunMeta("old"))
        store.putRunMeta("old", """{"x":2}""")
        assertEquals(listOf("""{"x":2}"""), store.listRunMeta())
    }

    @Test fun deletingACaptureAlsoRemovesItsRunMeta() {
        val store = CaptureStore(context, dbName).also { stores += it }
        val id = store.createCapture("c1")
        store.putRunMeta(id, "{}")
        assertNotNull(store.getRunMeta(id))
        assertTrue(store.deleteCapture(id))
        assertNull(store.getRunMeta(id))
        store.putRunMeta("x", "{}")
        store.deleteRunMeta("x")
        assertTrue(store.listRunMeta().isEmpty())
    }
}
