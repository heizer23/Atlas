package net.linspad.atlasphone.mobile.capture

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import net.linspad.atlasphone.mobile.model.CaptureSample
import net.linspad.atlasphone.mobile.model.Stream
import java.util.UUID

data class CaptureInfo(
    val id: String,
    val startedAtMillis: Long,
    val endedAtMillis: Long?,
    val locationCount: Long,
    val heartRateCount: Long,
    /** Samples stored and not yet acknowledged. */
    val unacked: Long,
    /** Samples refused because the unacknowledged limit was reached (data is never deleted to make room). */
    val dropped: Long,
    val lastSequence: Long,
) {
    val isOpen: Boolean get() = endedAtMillis == null
}

sealed interface AppendResult {
    data class Stored(val sequence: Long) : AppendResult
    /** Limit of unacknowledged samples reached; sample refused, counted in [CaptureInfo.dropped]. */
    data object Overflow : AppendResult
    data object UnknownCapture : AppendResult
}

/**
 * Durable, ordered, bounded buffer of sensor samples (SQLite). Temporary device infrastructure, not the training
 * database. Guarantees:
 *  - `sequence` is assigned inside the same transaction as the insert: unique, strictly increasing per capture
 *    (one counter shared by both streams), continues correctly after a process restart;
 *  - committed samples survive process death and page reloads; nothing is deleted except by explicit [purgeAcked]
 *    or [deleteCapture], and only samples the consumer acknowledged;
 *  - [fetch] uses a sequence cursor, so a consumer never receives a sample twice;
 *  - at most [maxUnackedPerCapture] unacknowledged samples per capture: beyond that new samples are refused
 *    (and counted), old unacknowledged data is kept.
 */
class CaptureStore(
    context: Context,
    name: String? = "mobile_captures.db",
    private val maxUnackedPerCapture: Long = 100_000,
) : SQLiteOpenHelper(context, name, null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE captures (
                id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, ended_at INTEGER,
                next_seq INTEGER NOT NULL DEFAULT 1,
                location_count INTEGER NOT NULL DEFAULT 0, hr_count INTEGER NOT NULL DEFAULT 0,
                unacked INTEGER NOT NULL DEFAULT 0, dropped INTEGER NOT NULL DEFAULT 0)""",
        )
        db.execSQL(
            """CREATE TABLE samples (
                capture_id TEXT NOT NULL, seq INTEGER NOT NULL, stream TEXT NOT NULL, ts INTEGER NOT NULL,
                payload TEXT NOT NULL, acked INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (capture_id, seq))""",
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    /** Creates a capture (or returns the existing one with that id, e.g. to continue after a restart). */
    fun createCapture(id: String? = null, nowMillis: Long = System.currentTimeMillis()): String {
        val captureId = id ?: UUID.randomUUID().toString()
        val db = writableDatabase
        val cv = ContentValues().apply { put("id", captureId); put("started_at", nowMillis) }
        db.insertWithOnConflict("captures", null, cv, SQLiteDatabase.CONFLICT_IGNORE)
        return captureId
    }

    fun finishCapture(id: String, nowMillis: Long = System.currentTimeMillis()) {
        val cv = ContentValues().apply { put("ended_at", nowMillis) }
        writableDatabase.update("captures", cv, "id = ? AND ended_at IS NULL", arrayOf(id))
    }

    /** Re-opens a finished capture so that recording can continue (same id, sequence continues). */
    fun reopenCapture(id: String) {
        val cv = ContentValues().apply { putNull("ended_at") }
        writableDatabase.update("captures", cv, "id = ?", arrayOf(id))
    }

    fun info(id: String): CaptureInfo? = readableDatabase.rawQuery(
        "SELECT id, started_at, ended_at, location_count, hr_count, unacked, dropped, next_seq FROM captures WHERE id = ?",
        arrayOf(id),
    ).use { if (it.moveToFirst()) it.toInfo() else null }

    fun list(): List<CaptureInfo> = readableDatabase.rawQuery(
        "SELECT id, started_at, ended_at, location_count, hr_count, unacked, dropped, next_seq FROM captures ORDER BY started_at DESC",
        null,
    ).use { c -> buildList { while (c.moveToNext()) add(c.toInfo()) } }

    /** Captures that were never finished (e.g. the process was killed while recording). */
    fun openCaptures(): List<CaptureInfo> = list().filter { it.isOpen }

    /** Stores one sample; [payload] receives the assigned sequence and returns the JSON to persist. */
    fun append(captureId: String, stream: Stream, timestampMillis: Long, payload: (sequence: Long) -> String): AppendResult {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val row = db.rawQuery("SELECT next_seq, unacked FROM captures WHERE id = ?", arrayOf(captureId)).use {
                if (it.moveToFirst()) it.getLong(0) to it.getLong(1) else null
            } ?: return AppendResult.UnknownCapture
            val (seq, unacked) = row
            if (unacked >= maxUnackedPerCapture) {
                db.execSQL("UPDATE captures SET dropped = dropped + 1 WHERE id = ?", arrayOf(captureId))
                db.setTransactionSuccessful()
                return AppendResult.Overflow
            }
            val cv = ContentValues().apply {
                put("capture_id", captureId); put("seq", seq); put("stream", stream.name)
                put("ts", timestampMillis); put("payload", payload(seq))
            }
            db.insertOrThrow("samples", null, cv)
            val counter = if (stream == Stream.LOCATION) "location_count" else "hr_count"
            db.execSQL(
                "UPDATE captures SET next_seq = next_seq + 1, unacked = unacked + 1, $counter = $counter + 1 WHERE id = ?",
                arrayOf(captureId),
            )
            db.setTransactionSuccessful()
            return AppendResult.Stored(seq)
        } finally {
            db.endTransaction()
        }
    }

    /** Samples with sequence > [afterSequence], in order. Never returns a sample twice for a moving cursor. */
    fun fetch(captureId: String, afterSequence: Long = 0, limit: Int = 1000): List<CaptureSample> =
        readableDatabase.rawQuery(
            "SELECT seq, stream, ts, payload FROM samples WHERE capture_id = ? AND seq > ? ORDER BY seq LIMIT ?",
            arrayOf(captureId, afterSequence.toString(), limit.toString()),
        ).use { c ->
            buildList {
                while (c.moveToNext()) add(CaptureSample(captureId, c.getLong(0), Stream.valueOf(c.getString(1)), c.getLong(2), c.getString(3)))
            }
        }

    /** Marks every sample with sequence <= [upToSequence] as safely transferred. Returns how many changed. */
    fun ack(captureId: String, upToSequence: Long): Int {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val cv = ContentValues().apply { put("acked", 1) }
            val n = db.update("samples", cv, "capture_id = ? AND seq <= ? AND acked = 0", arrayOf(captureId, upToSequence.toString()))
            if (n > 0) db.execSQL("UPDATE captures SET unacked = unacked - ? WHERE id = ?", arrayOf(n, captureId))
            db.setTransactionSuccessful()
            return n
        } finally {
            db.endTransaction()
        }
    }

    /** Deletes acknowledged samples only. Returns how many were removed. */
    fun purgeAcked(captureId: String): Int =
        writableDatabase.delete("samples", "capture_id = ? AND acked = 1", arrayOf(captureId))

    /** Deletes a capture. Refuses (returns false) while unacknowledged samples exist, unless [force]. */
    fun deleteCapture(captureId: String, force: Boolean = false): Boolean {
        val i = info(captureId) ?: return false
        if (i.unacked > 0 && !force) return false
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.delete("samples", "capture_id = ?", arrayOf(captureId))
            db.delete("captures", "id = ?", arrayOf(captureId))
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return true
    }

    /**
     * Reads the whole capture twice with different page sizes and checks order and uniqueness; used by the
     * diagnostic screen to prove "retrieval without duplicates".
     */
    fun verifyRetrieval(captureId: String): String {
        fun readAll(page: Int): List<Long> {
            val seqs = ArrayList<Long>()
            var cursor = 0L
            while (true) {
                val batch = fetch(captureId, cursor, page)
                if (batch.isEmpty()) break
                seqs.addAll(batch.map { it.sequence })
                cursor = batch.last().sequence
            }
            return seqs
        }
        val a = readAll(7)
        val b = readAll(500)
        val ascending = a.zipWithNext().all { (x, y) -> x < y }
        return when {
            a != b -> "FAIL: paged reads differ (${a.size} vs ${b.size})"
            !ascending || a.toSet().size != a.size -> "FAIL: out of order or duplicate sequence"
            else -> "OK: ${a.size} samples, strictly ascending, no duplicates"
        }
    }

    private fun android.database.Cursor.toInfo() = CaptureInfo(
        id = getString(0), startedAtMillis = getLong(1), endedAtMillis = if (isNull(2)) null else getLong(2),
        locationCount = getLong(3), heartRateCount = getLong(4), unacked = getLong(5), dropped = getLong(6),
        lastSequence = getLong(7) - 1,
    )
}
