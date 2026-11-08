"""Finish verification V1 and resume cursors R1."""

from backend.models import CountMismatch, FinishResponse, SeqRange, StreamCounts


def compute_gaps(present_seqs: list[int], last_seq: int) -> list[tuple[int, int]]:
    """Inclusive ranges missing from 1..last_seq. Seqs > last_seq are ignored (they surface as count mismatch)."""
    gaps: list[tuple[int, int]] = []
    expected = 1
    for seq in sorted(set(s for s in present_seqs if 1 <= s <= last_seq)):
        if seq > expected:
            gaps.append((expected, seq - 1))
        expected = seq + 1
    if expected <= last_seq:
        gaps.append((expected, last_seq))
    return gaps


def contiguous_prefix(present_seqs: list[int]) -> int:
    """Largest N with 1..N all present (0 if none)."""
    n = 0
    for seq in sorted(set(present_seqs)):
        if seq != n + 1:
            break
        n = seq
    return n


def _stored(conn, run_id: str) -> tuple[StreamCounts, StreamCounts, list[int]]:
    """(stored counts, high seq) per stream and the sorted union of stored seqs."""
    counts = {"location": 0, "heart_rate": 0}
    highs = {"location": 0, "heart_rate": 0}
    with conn.cursor() as cur:
        cur.execute(
            "select stream, count(*) as n, max(seq) as hi from runningtracker.run_samples where run_id = %s group by stream",
            (run_id,),
        )
        for row in cur.fetchall():
            counts[row["stream"]] = row["n"]
            highs[row["stream"]] = row["hi"]
        cur.execute("select distinct seq from runningtracker.run_samples where run_id = %s order by seq", (run_id,))
        seqs = [r["seq"] for r in cur.fetchall()]
    return StreamCounts(**counts), StreamCounts(**highs), seqs


def read_cursors(conn, run_id: str) -> tuple[StreamCounts, int]:
    """Per-stream max seq and the contiguous prefix of the union."""
    _, highs, seqs = _stored(conn, run_id)
    return highs, contiguous_prefix(seqs)


def verify_run(conn, run_id: str, expected_counts: StreamCounts, last_seq: int) -> FinishResponse:
    """Apply V1; returns the response record without changing run status."""
    stored, highs, seqs = _stored(conn, run_id)
    gaps = compute_gaps(seqs, last_seq)
    mismatch = [
        CountMismatch(stream=stream, expected=getattr(expected_counts, stream), stored=getattr(stored, stream))
        for stream in ("location", "heart_rate")
        if getattr(expected_counts, stream) != getattr(stored, stream)
    ]
    beyond = bool(seqs) and seqs[-1] > last_seq
    complete = not gaps and not mismatch and not beyond
    return FinishResponse(
        result="complete" if complete else "incomplete",
        run_id=run_id,
        verified_counts=stored,
        missing_seq_ranges=[SeqRange(start=a, end=b) for a, b in gaps],
        count_mismatch=mismatch,
        high_seq=highs,
        contiguous_seq=contiguous_prefix(seqs),
    )
