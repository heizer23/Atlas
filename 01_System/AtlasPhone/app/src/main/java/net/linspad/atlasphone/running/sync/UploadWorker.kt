package net.linspad.atlasphone.running.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import net.linspad.atlasphone.mobile.MobilePlatform
import net.linspad.atlasphone.mobile.capture.CaptureStore
import net.linspad.atlasphone.running.RunEvent
import net.linspad.atlasphone.running.RunLifecycle
import net.linspad.atlasphone.running.RunMeta
import net.linspad.atlasphone.running.RunState
import net.linspad.atlasphone.running.auth.TokenStore
import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.net.StreamCountsLocal
import net.linspad.atlasphone.running.net.UrlConnectionTransport
import java.util.concurrent.TimeUnit

enum class UploadOutcome { SYNCED, RETRY, STOPPED, NOTHING_TO_DO }

/**
 * Runs one upload attempt for a run: begin -> resume from the server cursor -> batches -> finish -> (verified) ack.
 * Plain blocking code driven by [UploadPlanner] decisions so it can be tested with a fake transport and a real CaptureStore.
 * Local samples are acknowledged and purged only after the server answered `complete`.
 */
class UploadEngine(private val store: CaptureStore, private val client: AtlasClient) {

    fun upload(runId: String): UploadOutcome {
        val meta0 = store.getRunMeta(runId)?.let { RunMeta.fromJson(it) } ?: return UploadOutcome.NOTHING_TO_DO
        if (meta0.state != RunState.PENDING_UPLOAD) return UploadOutcome.NOTHING_TO_DO
        val info = store.info(runId) ?: return stop(meta0, "Local capture is missing.")
        val localLast = info.lastSequence
        var meta = meta0.copy(lastError = null)

        fun fail(action: UploadAction): UploadOutcome = when (action) {
            UploadAction.NeedsRepair -> { save(meta.copy(needsRepair = true, lastError = "Pairing was revoked. Pair this phone again.")); UploadOutcome.STOPPED }
            UploadAction.RetryLater -> { save(meta.copy(lastError = "Atlas not reachable. Sync will retry.")); UploadOutcome.RETRY }
            is UploadAction.FailVisible -> { save(meta.copy(lastError = action.reason)); UploadOutcome.STOPPED }
            else -> error("not a failure action: $action")
        }

        val begin = when (val r = client.begin(runId, meta.startedAtMillis)) {
            is AtlasResult.Success -> r.value
            else -> return fail(UploadPlanner.afterError(r))
        }
        meta = meta.copy(uploadCursor = begin.contiguousSeq, needsRepair = false)
        var action = UploadPlanner.afterBegin(begin, localLast)
        var round = 0
        while (true) {
            when (val a = action) {
                is UploadAction.SendFrom -> {
                    val batch = store.fetch(runId, a.afterSeq, UploadPlanner.BATCH_SIZE)
                    if (batch.isEmpty()) { action = UploadAction.Finish; continue }
                    when (val r = client.putSamples(runId, batch)) {
                        is AtlasResult.Success -> {
                            meta = meta.copy(uploadCursor = r.value.contiguousSeq)
                            action = UploadPlanner.afterBatch(batch.last().sequence, localLast)
                        }
                        else -> return fail(UploadPlanner.afterError(r))
                    }
                }
                UploadAction.Finish -> {
                    val counts = StreamCountsLocal(info.locationCount, info.heartRateCount)
                    when (val r = client.finish(runId, meta, counts, localLast, info.dropped)) {
                        is AtlasResult.Success -> {
                            action = UploadPlanner.afterFinish(r.value, localLast, round)
                            if (action is UploadAction.SendFrom) round++
                        }
                        else -> return fail(UploadPlanner.afterError(r))
                    }
                }
                is UploadAction.MarkSynced -> {
                    // Verified by the server: only now do local samples go away.
                    store.ack(runId, a.ackUpToSeq)
                    store.purgeAcked(runId)
                    val synced = RunLifecycle.next(meta.state, RunEvent.SYNCED) ?: meta.state
                    save(meta.copy(state = synced, uploadCursor = localLast, lastError = null, needsRepair = false))
                    return UploadOutcome.SYNCED
                }
                else -> return fail(a)
            }
        }
    }

    private fun stop(meta: RunMeta, reason: String): UploadOutcome {
        save(meta.copy(lastError = reason)); return UploadOutcome.STOPPED
    }

    private fun save(meta: RunMeta) = store.putRunMeta(meta.captureId, meta.toJson())
}

/** WorkManager worker: unique work per run id, network constraint, exponential backoff. */
class UploadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val runId = inputData.getString(KEY_RUN_ID) ?: return@withContext Result.failure()
        val tokens = TokenStore.create(applicationContext)
        val base = tokens.baseUrl()
        if (base == null || tokens.token() == null) return@withContext Result.failure() // not paired; UI offers pairing
        val client = AtlasClient(base, { tokens.token() }, UrlConnectionTransport())
        val store = MobilePlatform.get(applicationContext).store
        when (UploadEngine(store, client).upload(runId)) {
            UploadOutcome.RETRY -> Result.retry()
            else -> Result.success()
        }
    }

    companion object { const val KEY_RUN_ID = "run_id" }
}

object UploadScheduler {
    private fun name(runId: String) = "run-upload-$runId"

    /** Unique work per run, KEEP policy (a queued/running upload is not duplicated). */
    fun enqueue(context: Context, runId: String, replace: Boolean = false) {
        val request = OneTimeWorkRequestBuilder<UploadWorker>()
            .setInputData(workDataOf(UploadWorker.KEY_RUN_ID to runId))
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context.applicationContext)
            .enqueueUniqueWork(name(runId), if (replace) ExistingWorkPolicy.REPLACE else ExistingWorkPolicy.KEEP, request)
    }

    /** Called at app start and by "Retry sync": enqueue every run still pending upload. */
    fun enqueueAllPending(context: Context, replace: Boolean = false) {
        val store = MobilePlatform.get(context).store
        store.listRunMeta().map { RunMeta.fromJson(it) }.filter { it.state == RunState.PENDING_UPLOAD }
            .forEach { enqueue(context, it.captureId, replace) }
    }
}
