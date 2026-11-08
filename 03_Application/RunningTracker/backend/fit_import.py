"""One-off import of a Polar/Garmin FIT activity as a complete run (source 'fit_import').

Raw values only: lat/long, heart rate, speed, altitude exactly as recorded; fields the file lacks stay null
(accuracy, bearing, RR intervals). The run id is derived from the file content, so re-importing the same file is a no-op.

    python -m backend.fit_import FILE.FIT --category "Easy Continuous" [--dry-run]
"""

import argparse
import hashlib
import json
import struct
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from psycopg2.extras import execute_values

from backend.database import get_db, init_pool, init_schema
from backend.metrics import recompute_and_store

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
SEMI = 180.0 / 2**31
IMPORT_NAMESPACE = uuid.UUID("7a1c5e0e-52d8-4b0b-9a53-0f1d6a2c4e10")

_BASE = {0: "B", 1: "b", 2: "B", 3: "h", 4: "H", 5: "i", 6: "I", 8: "f", 9: "d", 10: "B", 11: "H", 12: "I",
         13: "B", 14: "q", 15: "Q", 16: "Q"}
_INVALID = {"B": 0xFF, "b": 0x7F, "h": 0x7FFF, "H": 0xFFFF, "i": 0x7FFFFFFF, "I": 0xFFFFFFFF}


def parse_fit(data: bytes) -> dict[int, list[dict[int, object]]]:
    """FIT global message number -> list of {field number: value}. Invalid-marker values are dropped."""
    header = data[0]
    end = header + struct.unpack("<I", data[4:8])[0]
    pos, defs, out = header, {}, {}
    while pos < end:
        h = data[pos]
        pos += 1
        if h & 0x80:                       # compressed timestamp header
            d = defs[(h >> 5) & 3]
        elif h & 0x40:                     # definition message
            local = h & 15
            arch = data[pos + 1]
            e = ">" if arch else "<"
            glob = struct.unpack(e + "H", data[pos + 2:pos + 4])[0]
            n = data[pos + 4]
            pos += 5
            fields = [tuple(data[pos + i * 3:pos + i * 3 + 3]) for i in range(n)]
            pos += n * 3
            if h & 0x20:
                pos += 1 + data[pos] * 3
            defs[local] = {"e": e, "g": glob, "f": fields}
            continue
        else:
            d = defs[h & 15]
        rec = {}
        for num, size, base in d["f"]:
            raw = data[pos:pos + size]
            pos += size
            fmt = _BASE.get(base & 0x1F)
            if fmt is None or size % struct.calcsize(fmt):
                continue
            vals = struct.unpack(d["e"] + fmt * (size // struct.calcsize(fmt)), raw)
            if len(vals) == 1 and vals[0] != _INVALID.get(fmt):
                rec[num] = vals[0]
        out.setdefault(d["g"], []).append(rec)
    return out


def _iso(fit_ts: int) -> str:
    return (FIT_EPOCH + timedelta(seconds=fit_ts)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_run(data: bytes) -> dict:
    """Pure conversion: run row values plus samples with one shared sequence over both streams."""
    msgs = parse_fit(data)
    records = [r for r in msgs.get(20, []) if 253 in r]
    if not records:
        raise ValueError("FIT file has no record messages")
    samples, seq = [], 0
    for r in records:
        ts = _iso(r[253])
        if 0 in r and 1 in r:
            seq += 1
            samples.append(("location", seq, {
                "type": "location", "sequence": seq, "timestamp": ts,
                "latitude": r[0] * SEMI, "longitude": r[1] * SEMI,
                "accuracyMeters": None,
                "speedMetersPerSecond": r[6] / 1000.0 if 6 in r else None,
                "altitudeMeters": (r[2] / 5.0 - 500.0) if 2 in r else None,
                "bearingDegrees": None, "elapsedRealtimeNanos": None, "source": "fit_import",
            }))
        if 3 in r and r[3] > 0:
            seq += 1
            samples.append(("heart_rate", seq, {
                "type": "heart_rate", "sequence": seq, "timestamp": ts,
                "bpm": r[3], "rrIntervalsMs": None, "source": "fit_import", "elapsedRealtimeNanos": None,
            }))
    session = (msgs.get(18) or [{}])[0]
    started = FIT_EPOCH + timedelta(seconds=records[0][253])
    finished = FIT_EPOCH + timedelta(seconds=records[-1][253])
    elapsed = session[7] / 1000.0 if 7 in session else (finished - started).total_seconds()
    moving = session[8] / 1000.0 if 8 in session else elapsed
    distance = session[9] / 100.0 if 9 in session else (records[-1][5] / 100.0 if 5 in records[-1] else None)
    return {"started_at": started, "finished_at": finished, "elapsed_s": elapsed, "moving_s": moving,
            "distance_m": distance, "samples": samples}


def import_fit(path: Path, category: Optional[str], comment: Optional[str] = None) -> tuple[str, bool]:
    """Insert the run if it is not there yet. Returns (run_id, created)."""
    data = path.read_bytes()
    run_id = str(uuid.uuid5(IMPORT_NAMESPACE, hashlib.sha256(data).hexdigest()))
    run = build_run(data)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from runningtracker.runs where id = %s", (run_id,))
            if cur.fetchone():
                return run_id, False
            cur.execute(
                """
                insert into runningtracker.runs
                    (id, run_type, status, started_at, finished_at, elapsed_s, moving_s, distance_m,
                     category, comment, source)
                values (%s, 'continuous', 'complete', %s, %s, %s, %s, %s, %s, %s, 'fit_import')
                """,
                (run_id, run["started_at"], run["finished_at"], run["elapsed_s"], run["moving_s"],
                 run["distance_m"], category, comment),
            )
            execute_values(
                cur,
                "insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload) values %s",
                [(run_id, stream, seq, p["timestamp"], json.dumps(p)) for stream, seq, p in run["samples"]],
            )
        recompute_and_store(conn, run_id)
        conn.commit()
    return run_id, True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path)
    ap.add_argument("--category")
    ap.add_argument("--comment")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        r = build_run(a.file.read_bytes())
        n = {s: sum(1 for x in r["samples"] if x[0] == s) for s in ("location", "heart_rate")}
        print(f"{r['started_at']} .. {r['finished_at']}  {r['distance_m']} m  {r['elapsed_s']} s  samples {n}")
        return
    init_pool()
    init_schema()
    run_id, created = import_fit(a.file, a.category, a.comment)
    print(("imported " if created else "already imported ") + run_id)


if __name__ == "__main__":
    main()
