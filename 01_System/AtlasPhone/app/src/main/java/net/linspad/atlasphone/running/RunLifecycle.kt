package net.linspad.atlasphone.running

enum class RunEvent { START, PAUSE, RESUME, FINISH, QUEUE_UPLOAD, SYNCED, RECOVER, FINISH_RUN, FINISH_TRAINING }

/**
 * Pure lifecycle state machine: prepared -> recording <-> paused -> completed_local -> pending_upload -> synced.
 * With a heart-rate sensor the run ends in two steps: FINISH_RUN (RECORDING|PAUSED -> RECOVERY, running frozen, HR continues) and
 * FINISH_TRAINING (RECOVERY -> COMPLETED_LOCAL). FINISH stays the one-step end for a run without recovery.
 * A free run enters at RECORDING (previous state null). Recovery of an interrupted capture enters at PAUSED.
 * [next] returns null for an illegal transition; callers must not change state on null.
 */
object RunLifecycle {
    fun next(state: RunState?, event: RunEvent): RunState? = when (event) {
        RunEvent.START -> if (state == null || state == RunState.PREPARED) RunState.RECORDING else null
        RunEvent.PAUSE -> if (state == RunState.RECORDING) RunState.PAUSED else null
        RunEvent.RESUME -> if (state == RunState.PAUSED) RunState.RECORDING else null
        RunEvent.FINISH -> if (state == RunState.RECORDING || state == RunState.PAUSED) RunState.COMPLETED_LOCAL else null
        RunEvent.QUEUE_UPLOAD -> if (state == RunState.COMPLETED_LOCAL) RunState.PENDING_UPLOAD else null
        RunEvent.SYNCED -> if (state == RunState.PENDING_UPLOAD) RunState.SYNCED else null
        // An interrupted capture was last persisted as RECORDING or PAUSED (or has no metadata at all).
        // An interrupted recovery phase stays a recovery phase.
        RunEvent.RECOVER -> when (state) {
            null, RunState.RECORDING, RunState.PAUSED -> RunState.PAUSED
            RunState.RECOVERY -> RunState.RECOVERY
            else -> null
        }
        RunEvent.FINISH_RUN -> if (state == RunState.RECORDING || state == RunState.PAUSED) RunState.RECOVERY else null
        RunEvent.FINISH_TRAINING -> if (state == RunState.RECOVERY) RunState.COMPLETED_LOCAL else null
    }
}

/** O1: recovery is only offered when a live HR reading exists at the button press; otherwise plain Finish (no recovery phase). */
object RecoveryGate {
    /** [currentHr] = LiveMetrics.currentHr, already staleness-gated. True -> Finish Run (FINISH_RUN); false -> Finish (FINISH). */
    fun offersRecovery(currentHr: Int?): Boolean = currentHr != null
}
