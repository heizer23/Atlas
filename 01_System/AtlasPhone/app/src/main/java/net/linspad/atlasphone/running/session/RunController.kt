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
import net.linspad.atlasphone.mobile.model.CaptureSample
import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.mobile.model.Stream
import net.linspad.atlasphone.running.PauseRecord
import net.linspad.atlasphone.running.RunEvent
import net.linspad.atlasphone.running.RunLifecycle
import net.linspad.atlasphone.running.RunMeta
import net.linspad.atlasphone.running.RunState
import net.linspad.atlasphone.running.RunSummary
import net.linspad.atlasphone.running.SampleDecoder
import net.linspad.atlasphone.running.auth.TokenStore
import net.linspad.atlasphone.running.ghost.FieldRanking
import net.linspad.atlasphone.running.ghost.GhostCache
import net.linspad.atlasphone.running.cadence.CadenceConfig
import net.linspad.atlasphone.running.cadence.CadenceEstimator
import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostProfile
import net.linspad.atlasphone.running.ghost.GhostSession
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.ghost.Library
import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.hr.HrSmoothing
import net.linspad.atlasphone.running.recap.RecapBuilder
import net.linspad.atlasphone.running.recap.RecoveryLive
import net.linspad.atlasphone.running.recap.RecoveryMetrics
import net.linspad.atlasphone.running.recap.RecoveryConfig
import net.linspad.atlasphone.running.recap.RecoveryTracker
import net.linspad.atlasphone.running.settings.RunSettings
import net.linspad.atlasphone.running.ghost.LibraryRun
import net.linspad.atlasphone.running.coach.CoachController
import net.linspad.atlasphone.running.coach.CoachFrequency
import net.linspad.atlasphone.running.coach.CoachInput
import net.linspad.atlasphone.running.coach.CoachPlanParse
import net.linspad.atlasphone.running.coach.CoachPlanStore
import net.linspad.atlasphone.running.coach.CoachUiState
import net.linspad.atlasphone.running.live.HrTarget
import net.linspad.atlasphone.running.live.LiveHistory
import net.linspad.atlasphone.running.live.LiveTrends
import net.linspad.atlasphone.running.metrics.LiveMetrics
import net.linspad.atlasphone.running.metronome.MetronomeController
import net.linspad.atlasphone.running.metronome.MetronomeMode
import net.linspad.atlasphone.running.metronome.MetronomeState
import net.linspad.atlasphone.running.metrics.RunMetrics
import net.linspad.atlasphone.running.metrics.RunMetricsAccumulator
import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.net.PreparedRun
import net.linspad.atlasphone.running.net.UrlConnectionTransport
import net.linspad.atlasphone.running.sync.UploadScheduler

/** Everything the recording screen renders. [gpsState] / [hrState] are the Mobile Platform state names. */
class LiveRunState(
    val meta: RunMeta, val metrics: LiveMetrics, val gpsState: String, val hrState: String, val ghost: GhostLive? = null,
    val trends: LiveTrends = LiveTrends.EMPTY,
    /** Non-null only in RECOVERY. */
    val recovery: RecoveryLive? = null,
    /** HR2 live value (smoothed per the user's setting); null = no valid heart rate (never 0). */
    val hrDisplay: Double? = null,
    /** Live user cadence (display only, CAD1 over the last 30 s of steps); null = no valid cadence, never 0. */
    val cadenceSpm: Double? = null,
    /** Metronome chip state; null when no run is active or in RECOVERY. */
    val metronome: MetronomeState? = null,
    /** Coach strip state (Sprint04); null without a coach session. */
    val coach: CoachUiState? = null,
) {
    val targetHr: Int? get() = meta.targetHr
}

/** Whether the prepared run's ghost race can run offline: NONE (no ghost chosen), READY, or MISSING (download needed). */
enum class GhostReadiness { NONE, READY, MISSING }

/**
 * Process-wide owner of the active run (like MobilePlatform), so screen recreation reattaches to it.
 * Uses MobilePlatform only: no GPS/BLE code here. The foreground service from Sprint 01 stays the recording owner.
 * Persists RunMeta on every transition; the server never starts, pauses or stops a run.
 */
class RunController private constructor(private val app: Application) {
    private class Active(
        var meta: RunMeta, val acc: RunMetricsAccumulator, val monoStartMs: Long?, val jobs: List<Job>, val ghost: GhostSession?,
        val history: LiveHistory = LiveHistory(),
        /** The GPS collector; cancelled alone at Finish Run while HR and the publisher keep running. Null when recovered into RECOVERY. */
        val locationJob: Job? = null,
        /** Set while in RECOVERY: the only consumer of HR then (the running accumulator no longer gets it). */
        var recovery: RecoveryTracker? = null,
        /** Recent raw HR readings for the display smoothing (a few seconds). */
        val hrRecent: ArrayDeque<HrPoint> = ArrayDeque(),
        /** Recent step times (epoch ms), last LIVE_LOOKBACK_S only: in-memory display state, lost with the process. */
        val recentSteps: ArrayList<Long> = ArrayList(),
        /** The main ghost's profile (cadence list for the metronome, section pace for the race panel); null without ghost. */
        val ghostProfile: GhostProfile? = null,
    )

    private val platform = MobilePlatform.get(app)
    private val store get() = platform.store
    val tokens: TokenStore by lazy { TokenStore.create(app) }
    private val ghostCache = GhostCache(java.io.File(app.noBackupFilesDir, "ghost"))
    private val settings = RunSettings.create(app)
    private val metronome = MetronomeController(platform.click, platform.quickAction, settings)
    private val coach = CoachController(platform.speech, CoachPlanStore.create(app), settings, platform::log)

    private val lock = Any()
    private var active: Active? = null
    private val _live = MutableStateFlow<LiveRunState?>(null)

    /** Observable state for the Running Screen; null when no run is active. */
    fun live(): StateFlow<LiveRunState?> = _live

    // ── Start ────────────────────────────────────────────────────────────────

    fun startFree(targetHr: Int? = null): String = start(null, targetHr)

    fun startPrepared(prepared: PreparedRun, targetHr: Int? = null): String = start(prepared, targetHr)

    /** A race chosen on the phone: route and ghost come from the local library, no prepared run and no Atlas needed. */
    fun startRace(routeId: String, ghostRunId: String, targetHr: Int? = null): String = start(null, targetHr, routeId, ghostRunId)

    private fun start(prepared: PreparedRun?, targetHr: Int?, raceRouteId: String? = null, raceGhostId: String? = null): String = synchronized(lock) {
        check(active == null) { "A run is already active" }
        val previous = prepared?.let { p -> store.getRunMeta(p.id)?.let(RunMeta::fromJson)?.state ?: RunState.PREPARED }
        val state = RunLifecycle.next(previous, RunEvent.START) ?: error("This run cannot be started")
        check(platform.location.start()) { "GPS cannot start (location permission or location services missing)" }
        val now = System.currentTimeMillis()
        val id = platform.recorder.start(prepared?.id)
        val routeId = prepared?.routeId ?: raceRouteId
        val routeLengthM = routeId?.let { ghostCache.route(it)?.referenceDistanceM }
        // COACH3: the cached plan of 'Coach this run'; any failure only means no coaching (REL2).
        val coachPlanId = runCatching { coach.sessionPlanId()?.takeIf { coach.begin(it, 0.0) } }.getOrNull()
        val meta = RunMeta(id, state, prepared?.shortId, prepared?.title, now, null, emptyList(), null, 0, null, false, routeId, prepared?.ghostRunId ?: raceGhostId,
            targetHr, HrTarget.category(targetHr, routeLengthM), coachPlanId = coachPlanId)
        store.putRunMeta(id, meta.toJson())
        platform.steps.start() // result ignored: no permission / no sensor never blocks a run (S1)
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
        // The rest of the field: every other cached run on this route (same route + geometry version as the main ghost).
        val others = ghostCache.library().runsOn(routeId).filter { it.runId != ghostId }
            .mapNotNull { ghostCache.profile(it.runId) }
            .filter { it.routeId == route.routeId && it.geometryVersion == route.geometryVersion }
        return GhostSession(route, profile, meta.startedAtMillis, others)
    }

    /** [recovery] non-null = attach to an already finished run in RECOVERY: no GPS collector, HR goes to the tracker. */
    private fun attach(meta: RunMeta, acc: RunMetricsAccumulator, monoStartMs: Long?, ghost: GhostSession?, recovery: RecoveryTracker? = null) {
        val locationJob = if (recovery != null) null else platform.scope.launch {
            platform.location.samples.collect { fix ->
                synchronized(lock) {
                    active?.let { a ->
                        a.acc.addFix(fix)
                        a.ghost?.addFix(fix.timestampMillis, fix.latitude, fix.longitude, fix.accuracyMeters?.toDouble(), a.meta.pauses)
                    }
                }
            }
        }
        // Steps: the collector only appends to a short in-memory list (lock held for the append only; REL1). Not in RECOVERY.
        val stepsJob = if (recovery != null) null else platform.scope.launch(Dispatchers.Default) {
            platform.steps.samples.collect { step ->
                synchronized(lock) {
                    active?.recentSteps?.let { list ->
                        list.add(step.timestampMillis)
                        val cutoff = step.timestampMillis - (CadenceConfig.LIVE_LOOKBACK_S * 1000).toLong()
                        while (list.isNotEmpty() && list.first() < cutoff) list.removeAt(0)
                    }
                }
            }
        }
        val jobs = listOfNotNull(
            locationJob,
            stepsJob,
            platform.scope.launch { platform.heartRate.samples.collect { onHeartRate(it) } },
            platform.scope.launch { while (isActive) { publish(); delay(1000) } },
        )
        val ghostProfile = if (ghost != null) meta.ghostRunId?.let(ghostCache::profile) else null
        active = Active(meta, acc, monoStartMs, jobs, ghost, locationJob = locationJob, recovery = recovery, ghostProfile = ghostProfile)
        if (recovery == null) metronome.begin(ghost != null, ghostProfile?.cadenceByProgress, hasCoach = coach.hasCadenceTarget())
        publish()
    }

    /** RECORDING/PAUSED: the running accumulator; RECOVERY: the recovery tracker only (no pollution of running averages). */
    private fun onHeartRate(sample: RawHeartRate) {
        synchronized(lock) {
            val a = active ?: return
            a.hrRecent.addLast(HrPoint(sample.timestampMillis, sample.bpm))
            while (a.hrRecent.isNotEmpty() && a.hrRecent.first().tsMillis < sample.timestampMillis - HR_RECENT_MS) a.hrRecent.removeFirst()
            if (a.meta.state == RunState.RECOVERY) a.recovery?.addHeartRate(HrPoint(sample.timestampMillis, sample.bpm)) else a.acc.addHeartRate(sample)
        }
    }

    /** What publish() reads under the lock; the coach and the metronome run on it outside the lock (REL2: no speech call with a lock held). */
    private class Snapshot(
        val a: Active, val metrics: LiveMetrics, val ghost: GhostLive?, val hrDisplay: Double?,
        val cadence: Double?, val running: Boolean, val paused: Boolean, val ghostProgress: Double?, val now: Long, val coachInput: CoachInput?,
    )

    private fun publish() {
        val snap = synchronized(lock) {
            active?.let {
                val now = System.currentTimeMillis()
                val metrics = it.acc.snapshot(now)
                val ghost = it.ghost?.snapshot(now)
                val hrDisplay = HrSmoothing.valueAt(it.hrRecent.toList(), settings.hrSmoothing(), now, centered = false)
                if (it.meta.state == RunState.RECORDING) it.history.record(metrics, ghost, hrDisplay, it.ghostProfile) // no history while paused
                val running = it.meta.state == RunState.RECORDING || it.meta.state == RunState.PAUSED
                // Display only (CAD1 over the last 30 s of steps); never persisted or uploaded, not used for the metronome target.
                val cadence = if (running) CadenceEstimator.at(it.recentSteps.toList(), pauseRanges(it.meta.pauses), now)?.spm else null
                val ghostProgress = ghost?.takeIf { g -> g.status == GhostStatus.ON_COURSE }?.progressM
                val paused = it.meta.state == RunState.PAUSED
                // OQ2: the plan clock is LiveMetrics.movingS (= elapsed minus pauses; the name is A1's, standing still is not excluded).
                val lastHr = it.hrRecent.lastOrNull()
                val coachInput = if (running) CoachInput(
                    metrics.movingS, paused, hrDisplay, lastHr?.let { h -> (now - h.tsMillis) / 1000.0 }, metrics.racePaceSPerKm, cadence,
                ) else null
                Snapshot(it, metrics, ghost, hrDisplay, cadence, running, paused, ghostProgress, now, coachInput)
            }
        }
        if (snap == null) { _live.value = null; return }
        // Coach (COACH1) and metronome outside the RunController lock; coach failures are contained in CoachController (REL2).
        val coachUi = snap.coachInput?.let { coach.tick(it) }
        val coachCadence = snap.coachInput?.let { coach.cadenceTarget(it.activeS) }
        val metro = if (snap.running) metronome.tick(snap.ghostProgress, snap.paused, snap.now, coachCadence) else null
        val a = snap.a
        _live.value = LiveRunState(a.meta, snap.metrics, platform.location.state.value.name, platform.heartRate.state.value.name, snap.ghost,
            a.history.snapshot(), a.recovery?.snapshot(snap.now), snap.hrDisplay, snap.cadence, metro, coachUi)
    }

    /** Pauses as inclusive ms ranges [start, end) for CadenceEstimator; an open pause runs to the end of time. */
    private fun pauseRanges(pauses: List<PauseRecord>): List<LongRange> =
        pauses.map { p -> p.startedAtMillis until (p.endedAtMillis ?: Long.MAX_VALUE) }

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
            platform.steps.stop() // paused time records no steps (S1)
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
            platform.steps.start()
            a.acc.resume(now)
            a.meta = a.meta.copy(state = state, pauses = closeOpenPause(a.meta.pauses, now, offsetS(a, now)))
            store.putRunMeta(a.meta.captureId, a.meta.toJson())
        }
        publish()
    }

    // ── Metronome (flow step 23): chip taps, notification action (same cycleMode) and settings ───────────

    /** One-tap mode cycle for the chip. */
    fun cycleMetronome() { metronome.cycleMode(); publish() }

    /** Explicit mode, e.g. "Use manual cadence" from the no-ghost-cadence notice. */
    fun selectMetronomeMode(mode: MetronomeMode) { metronome.setMode(mode); publish() }

    /** Manual fixed cadence (persisted, clamped). */
    fun setManualCadence(spm: Int) { metronome.setManualSpm(spm); publish() }

    /** Click volume 0..1 (persisted). */
    fun setClickVolume(volume: Float) { metronome.setVolume(volume); publish() }

    // ── Coach (Sprint04): session switches and the plan cache; everything is contained, nothing reaches recording (REL2) ─────────

    /** Session mute from the coach strip. */
    fun setCoachMuted(muted: Boolean) { coach.setMuted(muted); publish() }

    /** Persisted 'Coach this run' switch; affects the next start only. */
    fun setCoachEnabled(enabled: Boolean) { settings.setCoachEnabled(enabled) }

    /** Persisted frequency; applied to a running session at the next tick. */
    fun setCoachFrequency(frequency: CoachFrequency) { settings.setCoachFrequency(frequency); publish() }

    fun coachEnabled(): Boolean = settings.coachEnabled()
    fun coachFrequency(): CoachFrequency = settings.coachFrequency()

    /** The cached plan for the home card (no network). */
    fun cachedCoachPlan(): CoachPlanParse? = coach.cachedPlan()

    /** Whether the system speech engine is usable; false only after it failed to initialise. */
    fun speechAvailable(): Boolean = platform.speech.isAvailable()

    /** Blocking (call from IO): fetches the active plan and refreshes the cache (COACH3). Null when nothing is cached. */
    fun refreshCoachPlan(): CoachPlanParse? {
        val c = client() ?: return coach.cachedPlan()
        return coach.refreshPlan(c)
    }

    /** Active seconds at the start of the last open pause (the recovered run is PAUSED there). */
    private fun activeAtOpenPause(pauses: List<PauseRecord>): Double {
        val open = pauses.lastOrNull { it.endedAtMillis == null }
        val closed = pauses.filter { it.endedAtMillis != null }.sumOf { (it.endedElapsedS ?: it.startedElapsedS) - it.startedElapsedS }
        return ((open?.startedElapsedS ?: 0.0) - closed).coerceAtLeast(0.0)
    }

    private fun closeOpenPause(pauses: List<PauseRecord>, nowMillis: Long, offsetS: Double): List<PauseRecord> =
        pauses.map { if (it.endedAtMillis == null) it.copy(endedAtMillis = nowMillis, endedElapsedS = offsetS) else it }

    /** The most recent library run on the route (by start time): the "previous run" of ST1. */
    private fun previousRunId(routeId: String?): String? =
        routeId?.let { id -> ghostCache.library().runsOn(id).maxByOrNull { it.startedAtMillis }?.runId }

    /**
     * Legacy one-step finish (a run without live heart rate, O1): stop, drain the buffer, store metadata, compute the
     * initial stats and the recap, move to pending_upload and enqueue the upload.
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
                metronome.stop() // O4: never during or after the end of the run
                coach.end()
                platform.stopAll() // recorder.stop() marks the capture finished; GPS, HR and steps are released
                active = null
                val (locations, heartRates) = loadSamples(a.meta.captureId)
                val summary = runningSummary(a, locations, heartRates, pauses, now, elapsed)
                val recap = RecapBuilder.build(locations, heartRates, pauses, null, a.ghost?.finalStanding(previousRunId(a.meta.routeId)))
                val local = a.meta.copy(state = RunState.COMPLETED_LOCAL, finishedAtMillis = now, pauses = pauses, summary = summary, recap = recap)
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

    /** A1 summary of the samples given; durations come from the monotonic clock (T1) when this process started the run. */
    private fun runningSummary(
        a: Active, locations: List<RawLocation>, heartRates: List<RawHeartRate>, pauses: List<PauseRecord>, endMillis: Long, elapsed: Double,
    ): RunSummary {
        var summary = RunMetrics.summarize(locations, heartRates, pauses, a.meta.startedAtMillis, endMillis)
        if (a.monoStartMs != null) {
            val pausedS = pauses.sumOf { (it.endedElapsedS ?: it.startedElapsedS) - it.startedElapsedS }
            val moving = (elapsed - pausedS).coerceAtLeast(0.0)
            summary = summary.copy(elapsedS = elapsed, movingS = moving,
                avgPaceSPerKm = if (summary.distanceM > 0 && moving > 0) moving / (summary.distanceM / 1000.0) else null)
        }
        return summary
    }

    /**
     * Finish Run (RS1): the running phase ends now. Distance, time and pace are frozen, GPS stops (location only; recorder, HR and
     * the foreground service keep running) and the run moves to RECOVERY. The final running summary and ghost standing are
     * persisted here and never recomputed at Finish Training.
     */
    suspend fun finishRun(): RunMeta {
        // The running phase ends at the button press; samples that arrive during the drain are stored but not counted.
        val t0 = System.currentTimeMillis()
        val monoNow = SystemClock.elapsedRealtime()
        synchronized(lock) {
            val a = active ?: error("No active run")
            RunLifecycle.next(a.meta.state, RunEvent.FINISH_RUN) ?: error("This run cannot be finished")
        }
        delay(DRAIN_MS)
        return withContext(Dispatchers.IO) {
            val meta = synchronized(lock) {
                val a = active ?: error("No active run")
                val state = RunLifecycle.next(a.meta.state, RunEvent.FINISH_RUN) ?: error("This run cannot be finished")
                a.locationJob?.cancel() // GPS collector and ghost feed stop; HR collector and publisher stay
                val elapsed = if (a.monoStartMs != null) (monoNow - a.monoStartMs) / 1000.0 else (t0 - a.meta.startedAtMillis) / 1000.0
                val pauses = closeOpenPause(a.meta.pauses, t0, elapsed)
                platform.steps.stop() // the running phase is over: no steps in recovery (S1)
                metronome.stop()      // O4: the click stops at Finish Run, not during recovery
                coach.end()           // Sprint04: coaching ends with the running phase
                platform.location.stop() // not stopAll: recorder, HR and the foreground service continue
                val (allLocations, allHeartRates) = loadSamples(a.meta.captureId)
                val locations = allLocations.filter { it.timestampMillis <= t0 }
                val heartRates = allHeartRates.filter { it.timestampMillis <= t0 }
                val summary = runningSummary(a, locations, heartRates, pauses, t0, elapsed)
                val standing = a.ghost?.finalStanding(previousRunId(a.meta.routeId))
                val recap = RecapBuilder.build(locations, heartRates, pauses, t0, standing)
                val next = a.meta.copy(state = state, pauses = pauses, summary = summary, finishedAtMillis = null, runFinishedAtMillis = t0, recap = recap)
                store.putRunMeta(next.captureId, next.toJson())
                val seed = allHeartRates.filter { it.timestampMillis >= t0 - (RecoveryConfig.END_BEFORE_S * 1000).toLong() }.map { HrPoint(it.timestampMillis, it.bpm) }
                a.meta = next
                a.recovery = RecoveryTracker(t0, seed)
                next
            }
            publish()
            meta
        }
    }

    /**
     * Finish Training: ends the recovery phase. Stops everything, computes HRR (HRR1) over all stored HR, rebuilds the recap
     * (standing is carried over from RunMeta.recap), moves to pending_upload and enqueues the upload. The running summary is kept.
     */
    suspend fun finishTraining(): RunMeta {
        synchronized(lock) {
            val a = active ?: error("No active run")
            RunLifecycle.next(a.meta.state, RunEvent.FINISH_TRAINING) ?: error("Training can only be finished from the recovery phase")
        }
        delay(DRAIN_MS)
        return withContext(Dispatchers.IO) {
            val (meta, runId) = synchronized(lock) {
                val a = active ?: error("No active run")
                RunLifecycle.next(a.meta.state, RunEvent.FINISH_TRAINING) ?: error("Training can only be finished from the recovery phase")
                val t0 = a.meta.runFinishedAtMillis ?: error("Run has no end of running")
                a.jobs.forEach { it.cancel() }
                val tEnd = System.currentTimeMillis()
                platform.stopAll() // recorder.stop() marks the capture finished
                active = null
                val captureThere = store.info(a.meta.captureId) != null
                val (locations, heartRates) = loadSamples(a.meta.captureId)
                val hr = heartRates.map { HrPoint(it.timestampMillis, it.bpm) }
                // Without the local capture the Finish Run recap stays as it is (upload then reports the missing capture).
                val recovery = if (captureThere && hr.isNotEmpty()) RecoveryMetrics.compute(hr, t0, tEnd) else null
                val recap = if (captureThere) RecapBuilder.build(locations, heartRates, a.meta.pauses, t0, a.meta.recap?.standing) else a.meta.recap
                val local = a.meta.copy(state = RunState.COMPLETED_LOCAL, finishedAtMillis = tEnd, recovery = recovery, recap = recap)
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
            decodeSamples(batch, locations, heartRates)
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
        val interrupted = metas.filter {
            (it.state == RunState.RECORDING || it.state == RunState.PAUSED || it.state == RunState.RECOVERY) && it.captureId != activeId
        }
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
            if (meta0.state == RunState.RECOVERY) { recoverRecovery(meta0); return }
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
            // Coaching resumes from the cached plan at the active time reached when the capture was interrupted (no replayed announcements).
            meta.coachPlanId?.let { planId -> runCatching { coach.begin(planId, activeAtOpenPause(pauses)) } }
            attach(meta, acc, null, ghost)
            platform.ensureForegroundService(app)
        }
    }

    /**
     * Interrupted RECOVERY (flow step 15): the running result is already persisted. Reopen the capture, do NOT start GPS,
     * reconnect HR best-effort, rebuild the tracker from the stored HR and resume the recovery screen. Never finalized here.
     */
    private fun recoverRecovery(meta0: RunMeta) {
        val t0 = meta0.runFinishedAtMillis ?: error("Run has no end of running")
        val state = RunLifecycle.next(meta0.state, RunEvent.RECOVER)!! // RECOVERY
        val meta = meta0.copy(state = state)
        platform.recorder.start(meta.captureId)
        platform.heartRate.connectLast()
        val seed = loadSamples(meta.captureId).second.filter { it.timestampMillis >= t0 - (RecoveryConfig.END_BEFORE_S * 1000).toLong() }
            .map { HrPoint(it.timestampMillis, it.bpm) }
        store.putRunMeta(meta.captureId, meta.toJson())
        attach(meta, RunMetricsAccumulator(meta.startedAtMillis, meta.pauses), null, null, RecoveryTracker(t0, seed))
        platform.ensureForegroundService(app)
    }

    /** Explicit user discard: deletes the capture even though samples are unacknowledged. */
    fun discard(runId: String) {
        synchronized(lock) {
            val a = active
            if (a != null && a.meta.captureId == runId) {
                a.jobs.forEach { it.cancel() }
                metronome.stop()
                coach.end()
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

    // ── Library: all routes and all qualified runs, kept on the phone ────────────────────────────────────

    /** The locally stored library (offline). */
    fun library(): Library = ghostCache.library()

    /** Rank by finishing time (1 = fastest) of every cached run on [routeId]; runs without a cached profile have no rank. */
    fun fieldRanks(routeId: String): Map<String, Int> =
        FieldRanking.ranks(ghostCache.library().runsOn(routeId).mapNotNull { ghostCache.profile(it.runId) })

    /** True when both route and ghost profile of this library run are stored (the race can start offline). */
    fun raceReady(run: LibraryRun): Boolean = ghostCache.isReady(run.routeId, run.runId)

    /**
     * Downloads the library list, then every route and ghost profile that is missing or whose route/geometry version
     * changed. Existing files are kept, so later refreshes only fetch what is new. Returns an error text or null.
     */
    suspend fun refreshLibrary(): String? = withContext(Dispatchers.IO) {
        val c = client() ?: return@withContext "This phone is not paired yet."
        val lib = when (val r = c.library()) {
            is AtlasResult.Success -> r.value
            AtlasResult.Unauthorized -> { tokens.clear(); return@withContext "Pairing was revoked. Pair this phone again." }
            is AtlasResult.NetworkError -> return@withContext "Atlas is not reachable. Is Tailscale running on this phone?"
            else -> return@withContext "Could not load the run library."
        }
        ghostCache.saveLibrary(lib)
        var failed = 0
        for (route in lib.routes) {
            if (lib.runsOn(route.routeId).isEmpty()) continue
            val cached = ghostCache.route(route.routeId)
            if (cached != null && cached.geometryVersion == route.geometryVersion) continue
            val g = (c.route(route.routeId) as? AtlasResult.Success)?.value
            if (g == null) failed++ else ghostCache.saveRoute(g)
        }
        for (run in lib.runs) {
            val cached = ghostCache.profile(run.runId)
            if (cached != null && cached.routeId == run.routeId && cached.geometryVersion == run.geometryVersion && cached.algoVersion == run.algoVersion) continue
            val p = (c.ghostProfile(run.runId) as? AtlasResult.Success)?.value
            if (p == null) failed++ else ghostCache.saveProfile(p)
        }
        if (failed > 0) "$failed items could not be downloaded. Refresh again with Atlas reachable." else null
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
        /** How much raw HR is kept for the display smoothing (covers the 10 s window). */
        private const val HR_RECENT_MS = 12_000L
        @Volatile private var instance: RunController? = null

        fun get(context: Context): RunController =
            instance ?: synchronized(this) {
                instance ?: RunController(context.applicationContext as Application).also { instance = it }
            }
    }
}

/** Splits stored samples by stream; steps are never decoded as location or heart rate. */
internal fun decodeSamples(batch: List<CaptureSample>, locations: MutableList<RawLocation>, heartRates: MutableList<RawHeartRate>) {
    for (s in batch) {
        when (s.stream) {
            Stream.LOCATION -> SampleDecoder.location(s.json)?.let(locations::add)
            Stream.HEART_RATE -> SampleDecoder.heartRate(s.json)?.let(heartRates::add)
            Stream.STEP -> Unit
        }
    }
}
