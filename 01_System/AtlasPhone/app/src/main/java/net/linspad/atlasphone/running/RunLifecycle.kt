package net.linspad.atlasphone.running

enum class RunEvent { START, PAUSE, RESUME, FINISH, QUEUE_UPLOAD, SYNCED, RECOVER }

/**
 * Pure lifecycle state machine: prepared -> recording <-> paused -> completed_local -> pending_upload -> synced.
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
        RunEvent.RECOVER -> if (state == null || state == RunState.RECORDING || state == RunState.PAUSED) RunState.PAUSED else null
    }
}
