package net.linspad.atlasphone.running.sync

import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.net.BeginResult
import net.linspad.atlasphone.running.net.FinishResult

sealed interface UploadAction {
    /** Send local samples with sequence greater than [afterSeq]. */
    data class SendFrom(val afterSeq: Long) : UploadAction
    data object Finish : UploadAction
    /** The server verified the run: local samples up to [ackUpToSeq] may now be acknowledged and purged. */
    data class MarkSynced(val ackUpToSeq: Long) : UploadAction
    /** Keep samples, stay pending_upload, show the reason. */
    data class FailVisible(val reason: String) : UploadAction
    data object NeedsRepair : UploadAction
    data object RetryLater : UploadAction
}

/** Pure upload decisions (no Android, no I/O): where to resume, when to finish, what a finish outcome means. */
object UploadPlanner {
    const val MAX_RESEND_ROUNDS = 3
    const val BATCH_SIZE = 1000

    fun afterBegin(begin: BeginResult, localLastSeq: Long): UploadAction =
        if (begin.contiguousSeq >= localLastSeq) UploadAction.Finish else UploadAction.SendFrom(begin.contiguousSeq)

    fun afterBatch(sentUpToSeq: Long, localLastSeq: Long): UploadAction =
        if (sentUpToSeq >= localLastSeq) UploadAction.Finish else UploadAction.SendFrom(sentUpToSeq)

    /**
     * [round] = number of resend rounds already done. Local samples are never acknowledged before MarkSynced
     * (the verified `complete` answer).
     */
    fun afterFinish(result: FinishResult, localLastSeq: Long, round: Int): UploadAction = when {
        result.complete -> UploadAction.MarkSynced(localLastSeq)
        result.missingRanges.isNotEmpty() && round < MAX_RESEND_ROUNDS ->
            UploadAction.SendFrom(result.missingRanges.minOf { it.first } - 1)
        result.missingRanges.isEmpty() ->
            UploadAction.FailVisible("Server and phone disagree on sample counts (${result.mismatchedStreams.joinToString()}). Keep the phone data and retry later.")
        else -> UploadAction.FailVisible("Upload still incomplete after $MAX_RESEND_ROUNDS resend rounds. Phone data is kept.")
    }

    fun afterError(result: AtlasResult<*>): UploadAction = when (result) {
        AtlasResult.Unauthorized -> UploadAction.NeedsRepair
        is AtlasResult.NetworkError, is AtlasResult.ServerError -> UploadAction.RetryLater
        AtlasResult.NotFound -> UploadAction.FailVisible("Atlas does not know this run or the device is not its owner.")
        is AtlasResult.Rejected -> UploadAction.FailVisible("Atlas rejected the upload: ${result.message}")
        is AtlasResult.Success -> throw IllegalArgumentException("not an error")
    }
}
