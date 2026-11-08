package net.linspad.atlasphone.running

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import net.linspad.atlasphone.mobile.capture.AppendResult
import net.linspad.atlasphone.mobile.capture.CaptureStore
import net.linspad.atlasphone.mobile.model.Stream
import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.net.BeginResult
import net.linspad.atlasphone.running.net.FinishResult
import net.linspad.atlasphone.running.net.HttpRequest
import net.linspad.atlasphone.running.net.HttpResponse
import net.linspad.atlasphone.running.sync.UploadAction
import net.linspad.atlasphone.running.sync.UploadEngine
import net.linspad.atlasphone.running.sync.UploadOutcome
import net.linspad.atlasphone.running.sync.UploadPlanner
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.IOException

private fun finish(complete: Boolean, missing: List<LongRange> = emptyList(), mismatched: List<String> = emptyList()) =
    FinishResult(complete, missing, mismatched, 0)

/** Pure planner decisions (no Android needed, but the test class shares the Robolectric file with the engine tests below). */
class UploadPlannerPureTest {
    @Test fun resumesFromTheServerCursor() {
        assertEquals(UploadAction.SendFrom(1200), UploadPlanner.afterBegin(BeginResult("uploading", 1200), 3000))
        assertEquals(UploadAction.Finish, UploadPlanner.afterBegin(BeginResult("uploading", 3000), 3000))
        assertEquals(UploadAction.Finish, UploadPlanner.afterBegin(BeginResult("uploading", 0), 0)) // empty capture
        assertEquals(UploadAction.SendFrom(2200), UploadPlanner.afterBatch(2200, 3000))
        assertEquals(UploadAction.Finish, UploadPlanner.afterBatch(3000, 3000))
    }

    @Test fun finishOutcomes() {
        assertEquals(UploadAction.MarkSynced(3000), UploadPlanner.afterFinish(finish(true), 3000, 0))
        // gap: resend from just before the first gap, for at most three rounds
        assertEquals(UploadAction.SendFrom(4), UploadPlanner.afterFinish(finish(false, listOf(5L..8L, 12L..13L)), 20, 0))
        assertEquals(UploadAction.SendFrom(4), UploadPlanner.afterFinish(finish(false, listOf(12L..13L, 5L..8L)), 20, 2))
        assertTrue(UploadPlanner.afterFinish(finish(false, listOf(5L..8L)), 20, 3) is UploadAction.FailVisible)
        // count mismatch without gaps cannot be fixed by resending
        assertTrue(UploadPlanner.afterFinish(finish(false, emptyList(), listOf("heart_rate")), 20, 0) is UploadAction.FailVisible)
    }

    @Test fun errorMapping() {
        assertEquals(UploadAction.NeedsRepair, UploadPlanner.afterError(AtlasResult.Unauthorized))
        assertEquals(UploadAction.RetryLater, UploadPlanner.afterError(AtlasResult.NetworkError("x")))
        assertEquals(UploadAction.RetryLater, UploadPlanner.afterError(AtlasResult.ServerError(503)))
        assertTrue(UploadPlanner.afterError(AtlasResult.NotFound) is UploadAction.FailVisible)
        assertTrue(UploadPlanner.afterError(AtlasResult.Rejected(409, "RUN_NOT_UPLOADABLE", "complete")) is UploadAction.FailVisible)
    }
}

/** UploadEngine against a scripted fake server and the real CaptureStore (SQLite via Robolectric). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class UploadEngineTest {
    private lateinit var context: Context
    private val dbName = "test_upload.db"
    private lateinit var store: CaptureStore
    private val runId = "run-1"

    @Before fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase(dbName)
        store = CaptureStore(context, dbName)
    }

    @After fun tearDown() { store.close(); context.deleteDatabase(dbName) }

    /** A finished local capture with [n] samples (interleaved streams) and pending_upload metadata. */
    private fun pendingRun(n: Int) {
        store.createCapture(runId, nowMillis = 1_700_000_000_000)
        for (i in 1..n) {
            val stream = if (i % 3 == 0) Stream.HEART_RATE else Stream.LOCATION
            assertTrue(store.append(runId, stream, 1_700_000_000_000L + i) { "{\"timestamp\":\"2026-01-01T00:00:00.000Z\",\"n\":$it}" } is AppendResult.Stored)
        }
        store.finishCapture(runId)
        val meta = RunMeta(runId, RunState.PENDING_UPLOAD, null, null, 1_700_000_000_000, 1_700_000_100_000, emptyList(),
            RunSummary(100.0, 100.0, 300.0, 333.0, null), 0, null, false)
        store.putRunMeta(runId, meta.toJson())
    }

    private class FakeServer(val beginCursor: Long = 0, val finishAnswers: MutableList<String> = mutableListOf()) {
        val puts = mutableListOf<List<Long>>()
        var finishCalls = 0
        var failWith: (HttpRequest) -> HttpResponse? = { null }
        var onFinish: () -> Unit = {}

        fun handle(r: HttpRequest): HttpResponse {
            failWith(r)?.let { return it }
            return when {
                r.url.endsWith("/begin") -> HttpResponse(200, """{"run_id":"run-1","status":"uploading","high_seq":{"location":0,"heart_rate":0},"contiguous_seq":$beginCursor}""")
                r.url.endsWith("/samples") -> {
                    val seqs = JSONObject(r.body!!).getJSONArray("samples").let { a -> (0 until a.length()).map { a.getJSONObject(it).getLong("seq") } }
                    puts += seqs
                    HttpResponse(200, """{"stored":${seqs.size},"duplicates":0,"high_seq":{"location":0,"heart_rate":0},"contiguous_seq":${seqs.last()}}""")
                }
                else -> { finishCalls++; onFinish(); HttpResponse(200, finishAnswers.removeFirstOrNull() ?: COMPLETE) }
            }
        }

        companion object {
            const val COMPLETE = """{"result":"complete","run_id":"run-1","verified_counts":{"location":0,"heart_rate":0},"missing_seq_ranges":[],"count_mismatch":[],"high_seq":{"location":0,"heart_rate":0},"contiguous_seq":0}"""
            fun incomplete(start: Int, end: Int) = """{"result":"incomplete","run_id":"run-1","verified_counts":{"location":0,"heart_rate":0},"missing_seq_ranges":[{"start":$start,"end":$end}],"count_mismatch":[],"high_seq":{"location":0,"heart_rate":0},"contiguous_seq":${start - 1}}"""
        }
    }

    private fun engine(server: FakeServer) = UploadEngine(store, AtlasClient("https://atlas.example", { "token" }, FakeTransportAdapter(server)))
    private class FakeTransportAdapter(val server: FakeServer) : net.linspad.atlasphone.running.net.HttpTransport {
        override fun execute(request: HttpRequest) = server.handle(request)
    }
    private fun meta() = RunMeta.fromJson(store.getRunMeta(runId)!!)

    @Test fun uploadResumesFromTheServerCursorInBoundedBatches() {
        pendingRun(3000)
        val server = FakeServer(beginCursor = 1200)
        assertEquals(UploadOutcome.SYNCED, engine(server).upload(runId))
        assertEquals(1201L, server.puts.first().first())
        assertTrue(server.puts.all { it.size <= 1000 })
        assertEquals(listOf(1000, 800), server.puts.map { it.size })
        assertEquals(3000L, server.puts.last().last())
        assertEquals(1, server.finishCalls) // finish after the last batch
        assertEquals(RunState.SYNCED, meta().state)
    }

    @Test fun nothingIsAckedBeforeAVerifiedFinish() {
        pendingRun(30)
        val unackedAtFinish = mutableListOf<Long>()
        val server = FakeServer(beginCursor = 4, finishAnswers = mutableListOf(FakeServer.incomplete(5, 8), FakeServer.COMPLETE))
        server.onFinish = { unackedAtFinish += store.info(runId)!!.unacked }
        assertEquals(UploadOutcome.SYNCED, engine(server).upload(runId))
        assertEquals(listOf(30L, 30L), unackedAtFinish)              // still nothing acked when finish said incomplete
        assertEquals(2, server.finishCalls)
        assertEquals(5L, server.puts[1].first())                     // gap 5-8 => resend from seq 5 (after seq 4)
        assertEquals(0L, store.info(runId)!!.unacked)                // acked after the complete answer
        assertTrue(store.fetch(runId, 0).isEmpty())                  // purged
    }

    @Test fun unresolvedMismatchStaysPendingUploadWithAVisibleErrorAfterThreeRounds() {
        pendingRun(20)
        val server = FakeServer(finishAnswers = MutableList(10) { FakeServer.incomplete(5, 8) })
        assertEquals(UploadOutcome.STOPPED, engine(server).upload(runId))
        assertEquals(4, server.finishCalls)                          // first finish + three resend rounds
        val m = meta()
        assertEquals(RunState.PENDING_UPLOAD, m.state)
        assertNotNull(m.lastError)
        assertEquals(20L, store.info(runId)!!.unacked)               // local data untouched
        assertEquals(20, store.fetch(runId, 0).size)
    }

    @Test fun errorsKeepLocalDataAndSetTheRightFlags() {
        // 401 -> needs re-pair, stops
        pendingRun(10)
        val unauthorized = FakeServer().apply { failWith = { HttpResponse(401, """{"error":{"code":"DEVICE_UNAUTHORIZED","message":"x"}}""") } }
        assertEquals(UploadOutcome.STOPPED, engine(unauthorized).upload(runId))
        assertTrue(meta().needsRepair); assertEquals(RunState.PENDING_UPLOAD, meta().state)
        assertEquals(10L, store.info(runId)!!.unacked)

        // network failure -> retry later, state unchanged
        val offline = FakeServer().apply { failWith = { throw IOException("offline") } }
        assertEquals(UploadOutcome.RETRY, engine(offline).upload(runId))
        assertNotNull(meta().lastError); assertEquals(RunState.PENDING_UPLOAD, meta().state)
        assertEquals(10L, store.info(runId)!!.unacked)

        // 404 -> fails visibly, stops
        val notFound = FakeServer().apply { failWith = { HttpResponse(404, """{"error":{"code":"NOT_FOUND","message":"x"}}""") } }
        assertEquals(UploadOutcome.STOPPED, engine(notFound).upload(runId))
        assertNotNull(meta().lastError); assertEquals(RunState.PENDING_UPLOAD, meta().state)
        assertEquals(10, store.fetch(runId, 0).size)

        // a later successful attempt clears the flags and syncs
        assertEquals(UploadOutcome.SYNCED, engine(FakeServer()).upload(runId))
        assertFalse(meta().needsRepair); assertNull(meta().lastError)
    }

    @Test fun runsThatAreNotPendingAreLeftAlone() {
        pendingRun(5)
        store.putRunMeta(runId, meta().copy(state = RunState.SYNCED).toJson())
        val server = FakeServer()
        assertEquals(UploadOutcome.NOTHING_TO_DO, engine(server).upload(runId))
        assertTrue(server.puts.isEmpty() && server.finishCalls == 0)
        assertEquals(UploadOutcome.NOTHING_TO_DO, engine(server).upload("unknown"))
    }
}
