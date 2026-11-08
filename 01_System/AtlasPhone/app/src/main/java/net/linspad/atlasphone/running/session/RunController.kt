package net.linspad.atlasphone.running.session

import android.app.Application
import android.content.Context
import android.os.SystemClock
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.linspad.atlasphone.mobile.MobilePlatform
import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.mobile.model.Stream
import net.linspad.atlasphone.running.PauseRecord
import net.linspad.atlasphone.running.RunEvent
import net.linspad.atlasphone.running.RunLifecycle
import net.linspad.atlasphone.running.RunMeta
import net.linspad.atlasphone.running.RunState
import net.linspad.atlasphone.running.SampleDecoder
import net.linspad.atlasphone.running.auth.TokenStore
import net.linspad.atlasphone.running.ghost.GhostCache
import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostSession
import net.linspad.atlasphone.running.metrics.LiveMetrics
import net.linspad.atlasphone.running.metrics.RunMetrics
import net.linspad.atlasphone.running.metrics.RunMetricsAccumulator
import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.net.PreparedRun
import net.linspad.atlasphone.running.net.UrlConnectionTransport
import net.linspad.atlasphone.running.sync.UploadScheduler

/** Everything the recording screen renders. [gpsState] / [hrState] are the Mobile Platform state names. */
class LiveRunState(val meta: RunMeta, val metrics: LiveMetrics, val gpsState: String, val hrState: String, val ghost: GhostLive? = null)

/** Whether the prepared run's ghost race can run offline: NONE (no ghost chosen), READY, or MISSING (download needed). */
enum class GhostReadiness { NONE, READY, MISSING }

/**
 * Process-wide owner of the active run (like MobilePlatform), so screen recreation reattaches to it.
 * Uses MobilePlatform only: no GPS/BLE code here. The foreground service from Sprint 01 stays the recording owner.
 * Persists RunMeta on every transition; the server never starts, pauses or stops a run.
 */
class RunController private constructor(private val app: Application) {
    private class Active(var meta: RunMeta, val acc: RunMetricsAccumulator, val monoStartMs: Long?, val jobs: List<Job>, val ghost: GhostSession?)

    private val platform = MobilePlatform.get(app)
    private val store get() = platform.store
    val tokens: TokenStore by lazy { TokenStore.create(app) }
    private val ghostCache = GhostCache(java.io.File(app.noBackupFilesDir, "ghost"))

    private val lock = Any()
    private var active: Active? = null
    private val _live = MutableStateFlow<LiveRunState?>(null)

    /** Observable state for the Running Screen; null when no run is active. */
    fun live(): StateFlow<LiveRunState?> = _live

    // ── Start ────────────────────────────────────────────────────────────────

    fun startFree(): String = start(null)

    fun startPrepared(prepared: PreparedRun): String = start(prepared)

    private fun start(prepared: PreparedRun?): String = synchronized(lock) {
        check(active == null) { "A run is already active" }
        val previous = prepared?.let { p -> store.getRunMeta(p.id)?.let(RunMeta::fromJson)?.state ?: RunState.PREPARED }
        val state = RunLifecycle.next(previous, RunEvent.START) ?: error("This run cannot be started")
        check(platform.location.start()) { "GPS cannot start (location permission or location services missing)" }
        val now = System.currentTimeMillis()
        val id = platform.recorder.start(prepared?.id)
        val meta = RunMeta(id, state, prepared?.shortId, prepared?.title, now, null, emptyList(), null, 0, null, false, prepared?.routeId, prepared?.ghostRunId)
        store.putRunMeta(id, meta.toJson())
        attach(meta, RunMetricsAccumulator(now), SystemClock.elapsedRealtime(), ghostFor(meta))
        platform.ensureForegroundService(app)
        id
    }

    /** The ghost race from locally cached data only; null (run without ghost) if none was chosen or the data is missing. */
    private fun ghostFor(meta: RunMeta): GhostSession? {
        val routeId = meta.routeId ?: return null
        val ghostId = meta.ghostRunId ?: return null
        val route = ghostCache.route(routeId) ?: return null
        val profile = ghostCache.profile(ghostId) ?: return null
        if (profile.routeId != route.routeId || profile.geometryVersion != route.geometryVersion) return null
        return GhostSession(route, profile, meta.startedAtMillis)
    }

    private fun attach(meta: RunMeta, acc: RunMetricsAccumulator, monoStartMs: Long?, ghost: GhostSession?) {
        val jobs = listOf(
            platform.scope.launch {
                platform.location.samples.collect { fix ->
                    synchronized(lock) {
                        active?.let { a ->
                            a.acc.addFix(fix)
                            a.ghost?.addFix(fix.timestampMillis, fix.latitude, fix.longitude, fix.accuracyMeters?.toDouble(), a.meta.pauses)
                        }
                    }
                }
            },
            platform.scope.launch { platform.heartRate.samples.collect { synchronized(lock) { active?.acc?.addHeartRate(it) } } },
            platform.scope.launch { while (isActive) { publish(); delay(1000) } },
        )
        active = Active(meta, acc, monoStartMs, jobs, ghost)
        publish()
    }

    private fun publish() {
        val live = synchronized(lock) {
            active?.let {
                val now = System.currentTimeMillis()
                LiveRunState(it.meta, it.acc.snapshot(now), platform.location.state.value.name, platform.heartRate.state.value.name, it.ghost?.snapshot(now))
            }
        }
        _live.value = live
    }

    /** Seconds since run start: monotonic when this process started the run, wall clock after a recovery. */
    private fun offsetS(a: Active, nowMillis: Long): Double =
        if (a.monoStartMs != null) (SystemClock.elapsedRealtime() - a.monoStartMs) / 1000.0 else (nowMillis - a.meta.startedAtMillis) / 1000.0

    // ── Pause / resume / finish ──────────────────────────────────────────────

    /** Manual pause: distinct from poor GPS or missing HR; samples keep being stored raw but are ignored by the metrics. */
    fun pause() {
        synchronized(lock) {
            val a = active ?: return
            val state = RunLifecycle.next(a.meta.state, RunEvent.PAUSE) ?: return
            val now = System.currentTimeMillis()
            a.acc.pause(now)
            a.meta = a.meta.copy(state = state, pauses = a.meta.pauses + PauseRecord(now, null, offsetS(a, now), null))
            store.putRunMeta(a.meta.captureId, a.meta.toJson())
        }
        publish()
    }

    fun resume() {
        synchronized(lock) {
            val a = active ?: return
            val state = RunLifecycle.next(a.meta.state, RunEvent.RESUME) ?: return
            val now = System.currentTimeMillis()
            a.acc.resume(now)
            a.meta = a.meta.copy(state = state, pauses = closeOpenPause(a.meta.pauses, now, offsetS(a, now)))
            store.putRunMeta(a.meta.captureId, a.meta.toJson())
        }
        publish()
    }

    private fun closeOpenPause(pauses: List<PauseRecord>, nowMillis: Long, offsetS: Double): List<PauseRecord> =
        pauses.map { if (it.endedAtMillis == null) it.copy(endedAtMillis = nowMillis, endedElapsedS = offsetS) else it }

    /**
     * Stop, drain the buffer, store metadata, compute the initial stats, move to pending_upload and enqueue the upload.
     * A short delay lets in-flight samples reach the buffer before the recorder stops.
     */
    suspend fun finish(): RunMeta {
        synchronized(lock) { check(active != null) { "No active run" } }
        delay(DRAIN_MS)
        return withContext(Dispatchers.IO) {
            val (meta, runId) = synchronized(lock) {
                val a = active ?: error("No active run")
                RunLifecycle.next(a.meta.state, RunEvent.FINISH) ?: error("This run cannot be finished")
                a.jobs.forEach { it.cancel() }
                val now = System.currentTimeMillis()
                val pauses = closeOpenPause(a.meta.pauses, now, offsetS(a, now))
                val elapsed = offsetS(a, now)
                platform.stopAll() // recorder.stop() marks the capture finished; GPS and HR are released
                active = null
                val (locations, heartRates) = loadSamples(a.meta.captureId)
                var summary = RunMetrics.summarize(locations, heartRates, pauses, a.meta.startedAtMillis, now)
                // Durations come from the monotonic clock (T1); wall time is the fallback after a recovery.
                if (a.monoStartMs != null) {
                    val pausedS = pauses.sumOf { (it.endedElapsedS ?: it.startedElapsedS) - it.startedElapsedS }
                    val moving = (elapsed - pausedS).coerceAtLeast(0.0)
                    summary = summary.copy(elapsedS = elapsed, movingS = moving,
                        avgPaceSPerKm = if (summary.distanceM > 0 && moving > 0) moving / (summary.distanceM / 1000.0) else null)
                }
                val local = a.meta.copy(state = RunState.COMPLETED_LOCAL, finishedAtMillis = now, pauses = pauses, summary = summary)
                store.putRunMeta(local.captureId, local.toJson())
                val pending = local.copy(state = RunLifecycle.next(RunState.COMPLETED_LOCAL, RunEvent.QUEUE_UPLOAD)!!)
                store.putRunMeta(pending.captureId, pending.toJson())
                pending to pending.captureId
            }
            _live.value = null
            UploadScheduler.enqueue(app, runId, replace = true)
            meta
        }
    }

    private fun loadSamples(captureId: String): Pair<List<RawLocation>, List<RawHeartRate>> {
        val locations = ArrayList<RawLocation>()
        val heartRates = ArrayList<RawHeartRate>()
        var cursor = 0L
        while (true) {
            val batch = store.fetch(captureId, cursor, 1000)
            if (batch.isEmpty()) break
            for (s in batch) {
                if (s.stream == Stream.LOCATION) SampleDecoder.location(s.json)?.let(locations::add)
                else SampleDecoder.heartRate(s.json)?.let(heartRates::add)
            }
            cursor = batch.last().sequence
        }
        return locations to heartRates
    }

    // ── Interrupted captures: Recover / Discard, never auto-finalized ───────────

    /** Runs whose capture was left open (process killed). Includes open captures without metadata. */
    fun interruptedRuns(): List<RunMeta> {
        val activeId = synchronized(lock) { active?.meta?.captureId }
        val diagnosticId = platform.recorder.active.value?.id // a capture of the Sprint 01 test screen is not interrupted
        val metas = store.listRunMeta().map(RunMeta::fromJson)
        val interrupted = metas.filter { (it.state == RunState.RECORDING || it.state == RunState.PAUSED) && it.captureId != activeId }
        val known = metas.map { it.captureId }.toSet()
        val orphans = store.openCaptures()
            .filter { it.id !in known && it.id != activeId && it.id != diagnosticId }
            .map { RunMeta(it.id, RunState.RECORDING, null, null, it.startedAtMillis, null, emptyList(), null, 0, null, false) }
        return interrupted + orphans
    }

    /** Reopens an interrupted capture as PAUSED with a synthetic pause starting at the last stored sample. */
    fun recover(runId: String) {
        synchronized(lock) {
            check(active == null) { "A run is already active" }
            val meta0 = interruptedRuns().firstOrNull { it.captureId == runId } ?: error("Not an interrupted run")
            val info = store.info(runId) ?: error("Capture is missing")
            val state = RunLifecycle.next(if (store.getRunMeta(runId) == null) null else meta0.state, RunEvent.RECOVER)!!
            val lastTs = if (info.lastSequence > 0) store.fetch(runId, info.lastSequence - 1, 1).lastOrNull()?.timestampMillis else null
            val pauseStart = (lastTs ?: info.startedAtMillis).coerceAtLeast(meta0.startedAtMillis)
            val pauses = if (meta0.pauses.lastOrNull()?.endedAtMillis == null && meta0.pauses.isNotEmpty()) meta0.pauses
            else meta0.pauses + PauseRecord(pauseStart, null, (pauseStart - meta0.startedAtMillis) / 1000.0, null)
            val meta = meta0.copy(state = state, pauses = pauses)
            platform.location.start() // best effort; resuming needs it, finishing does not
            platform.recorder.start(runId)
            val acc = RunMetricsAccumulator(meta.startedAtMillis, pauses)
            val (locations, heartRates) = loadSamples(runId)
            locations.forEach(acc::addFix)
            heartRates.forEach(acc::addHeartRate)
            store.putRunMeta(runId, meta.toJson())
            // Rebuild the ghost race by replaying the stored fixes through the same engine.
            val ghost = ghostFor(meta)
            locations.forEach { ghost?.addFix(it.timestampMillis, it.latitude, it.longitude, it.accuracyMeters?.toDouble(), pauses) }
            attach(meta, acc, null, ghost)
            platform.ensureForegroundService(app)
        }
    }

    /** Explicit user discard: deletes the capture even though samples are unacknowledged. */
    fun discard(runId: String) {
        synchronized(lock) {
            val a = active
            if (a != null && a.meta.captureId == runId) {
                a.jobs.forEach { it.cancel() }
                platform.stopAll()
                active = null
            }
            store.deleteCapture(runId, force = true)
            store.deleteRunMeta(runId)
        }
        publish()
    }

    // ── Stored runs ──────────────────────────────────────────────────────────

    fun allRuns(): List<RunMeta> = store.listRunMeta().map(RunMeta::fromJson)
    fun meta(runId: String): RunMeta? = store.getRunMeta(runId)?.let(RunMeta::fromJson)
    fun preparedRuns(): List<RunMeta> = allRuns().filter { it.state == RunState.PREPARED }
    fun pendingUploads(): List<RunMeta> = allRuns().filter { it.state == RunState.PENDING_UPLOAD }

    /** Stores a downloaded prepared run so it can be started offline. */
    private fun savePrepared(p: PreparedRun) {
        val existing = store.getRunMeta(p.id)?.let(RunMeta::fromJson)
        if (existing != null) {
            if (existing.state == RunState.PREPARED && (existing.routeId != p.routeId || existing.ghostRunId != p.ghostRunId)) {
                store.putRunMeta(p.id, existing.copy(routeId = p.routeId, ghostRunId = p.ghostRunId).toJson())
            }
            return
        }
        store.putRunMeta(p.id, RunMeta(p.id, RunState.PREPARED, p.shortId, p.title, 0, null, emptyList(), null, 0, null, false, p.routeId, p.ghostRunId).toJson())
    }

    fun removePrepared(runId: String) {
        if (meta(runId)?.state == RunState.PREPARED) store.deleteRunMeta(runId)
    }

    fun retrySync() = UploadScheduler.enqueueAllPending(app, replace = true)

    // ── Atlas (pairing and prepared runs). The run itself never depends on these. ──────────────────────────

    private fun client(baseUrl: String? = tokens.baseUrl()): AtlasClient? =
        baseUrl?.let { AtlasClient(it, { tokens.token() }, UrlConnectionTransport()) }

    /** Returns an error text, or null when paired. The text is generic on purpose. */
    suspend fun pair(baseUrl: String, code: String, deviceName: String): String? = withContext(Dispatchers.IO) {
        if (!baseUrl.startsWith("https://")) return@withContext "The server URL must start with https://"
        when (val r = AtlasClient(baseUrl, { null }, UrlConnectionTransport()).pair(code, deviceName)) {
            is AtlasResult.Success -> { tokens.savePairing(baseUrl, r.value.deviceId, r.value.deviceToken); retrySync(); null }
            is AtlasResult.NetworkError -> "Atlas is not reachable. Is Tailscale running on this phone?"
            else -> "Pairing failed. Check the code or create a new one."
        }
    }

    /** Downloads the prepared-run list and keeps it locally. Returns an error text or null. */
    suspend fun refreshPrepared(): String? = withContext(Dispatchers.IO) {
        val c = client() ?: return@withContext "This phone is not paired yet."
        when (val r = c.preparedRuns()) {
            is AtlasResult.Success -> {
                val ids = r.value.map { it.id }.toSet()
                preparedRuns().filter { it.captureId !in ids }.forEach { removePrepared(it.captureId) }
                r.value.forEach(::savePrepared)
                downloadGhostData(c, r.value)
            }
            AtlasResult.Unauthorized -> { tokens.clear(); "Pairing was revoked. Pair this phone again." }
            is AtlasResult.NetworkError -> "Atlas is not reachable. Is Tailscale running on this phone?"
            else -> "Could not load prepared runs."
        }
    }

    /** Downloads route + ghost profile for prepared runs that still lack them. Returns an error text or null. */
    private fun downloadGhostData(c: AtlasClient, prepared: List<PreparedRun>): String? {
        var failed = false
        for (p in prepared) {
            val routeId = p.routeId ?: continue
            val ghostId = p.ghostRunId ?: continue
            if (ghostCache.isReady(routeId, ghostId)) continue
            val route = (c.route(routeId) as? AtlasResult.Success)?.value
            val profile = (c.ghostProfile(ghostId) as? AtlasResult.Success)?.value
            if (route == null || profile == null) { failed = true; continue }
            ghostCache.saveRoute(route)
            ghostCache.saveProfile(profile)
        }
        return if (failed) "Ghost data could not be downloaded for some runs. Refresh again with Atlas reachable." else null
    }

    /** Offline readiness of the ghost race of a prepared run (local storage only). */
    fun ghostReadiness(meta: RunMeta): GhostReadiness {
        val routeId = meta.routeId; val ghostId = meta.ghostRunId
        if (routeId == null || ghostId == null) return GhostReadiness.NONE
        return if (ghostCache.isReady(routeId, ghostId)) GhostReadiness.READY else GhostReadiness.MISSING
    }

    /** The prepared run data needed to start it, from local storage (no network). */
    fun preparedRunFor(meta: RunMeta): PreparedRun = PreparedRun(meta.captureId, meta.preparedShortId ?: "", meta.title, null, 0, meta.routeId, meta.ghostRunId)

    companion object {
        private const val DRAIN_MS = 400L
        @Volatile private var instance: RunController? = null

        fun get(context: Context): RunController =
            instance ?: synchronized(this) {
                instance ?: RunController(context.applicationContext as Application).also { instance = it }
            }
    }
}
