-- RunningTracker test world. Ids are fixed UUIDs (the id columns are uuid); the suffix names the fixture.
-- Device tokens / codes are hashed here exactly as the backend does (sha256 hex).
--
-- devices   fix-device-1 d1..01 active   token 'fix-token-1'
--           fix-device-2 d1..02 revoked  token 'fix-token-2'
--           fix-device-3 d1..03 active   token 'fix-token-3'
-- prepared  fix-prepared-fresh e1..f1 (short FIXPRE, +24h)   fix-prepared-expired e1..f2 (short FIXOLD, -1h)
-- runs      fix-run-complete c1..01 (device-1, 20 samples per stream, one pause, metrics)
--           fix-run-gap      c1..02 (device-1, uploading, seq 5-8 missing)
--           fix-run-revoked-uploading c1..03 (device-2, uploading)   fix-run-revoked-complete c1..04 (device-2, complete)
--           (Sprint02 recovery runs c1..05, c1..06, c1..07: see the block at the end of this file)
-- codes     fix-code-active 'FIXACTV2'   fix-code-expired 'FIXEXPD2'   fix-code-used 'FIXUSED2'

insert into runningtracker.devices (id, name, token_hash, created_at, last_used_at, revoked_at) values
 ('d1000000-0000-0000-0000-000000000001', 'fix-device-1', encode(sha256('fix-token-1'::bytea), 'hex'), now() - interval '10 days', now() - interval '1 day', null),
 ('d1000000-0000-0000-0000-000000000002', 'fix-device-2', encode(sha256('fix-token-2'::bytea), 'hex'), now() - interval '20 days', null, now() - interval '2 days'),
 ('d1000000-0000-0000-0000-000000000003', 'fix-device-3', encode(sha256('fix-token-3'::bytea), 'hex'), now() - interval '5 days', null, null);

insert into runningtracker.runs (id, status, short_id, title, expires_at, created_at) values
 ('e1000000-0000-0000-0000-0000000000f1', 'prepared', 'FIXPRE', 'Easy 5k', now() + interval '24 hours', now() - interval '1 hour'),
 ('e1000000-0000-0000-0000-0000000000f2', 'prepared', 'FIXOLD', 'Old plan',  now() - interval '1 hour',  now() - interval '3 days');

insert into runningtracker.runs (id, run_type, status, started_at, finished_at, elapsed_s, moving_s, distance_m, comment, device_id, created_at) values
 ('c1000000-0000-0000-0000-000000000001', 'continuous', 'complete',  '2026-01-10 08:00:00+00', '2026-01-10 08:10:00+00', 600, 540, 2000, 'tempo', 'd1000000-0000-0000-0000-000000000001', '2026-01-10 08:12:00+00'),
 ('c1000000-0000-0000-0000-000000000002', 'continuous', 'uploading', '2026-01-11 08:00:00+00', null, null, null, null, null, 'd1000000-0000-0000-0000-000000000001', '2026-01-11 08:00:00+00'),
 ('c1000000-0000-0000-0000-000000000003', 'continuous', 'uploading', '2026-01-05 08:00:00+00', null, null, null, null, null, 'd1000000-0000-0000-0000-000000000002', '2026-01-05 08:00:00+00'),
 ('c1000000-0000-0000-0000-000000000004', 'continuous', 'complete',  '2026-01-04 08:00:00+00', '2026-01-04 08:30:00+00', 1800, 1800, 5000, null, 'd1000000-0000-0000-0000-000000000002', '2026-01-04 08:31:00+00');

-- fix-run-complete: seq 1..40 (odd = location, even = heart_rate), one per second from the start, northward at 4 m/s
insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000001',
       case when n % 2 = 1 then 'location' else 'heart_rate' end, n,
       timestamptz '2026-01-10 08:00:00+00' + n * interval '1 second',
       case when n % 2 = 1 then
         jsonb_build_object('type', 'location.sample', 'timestamp', to_char(timestamptz '2026-01-10 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                            'latitude', 52.0 + (4.0 * n) / 111194.9266, 'longitude', 13.0, 'accuracyMeters', 5.0,
                            'speedMetersPerSecond', null, 'altitudeMeters', null, 'bearingDegrees', null, 'elapsedRealtimeNanos', null)
       else
         jsonb_build_object('type', 'heartRate.sample', 'timestamp', to_char(timestamptz '2026-01-10 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                            'bpm', 140 + n, 'rrIntervalsMs', null, 'source', 'bluetooth', 'elapsedRealtimeNanos', null)
       end
from generate_series(1, 40) as n;

insert into runningtracker.run_pauses (run_id, started_at, ended_at, started_elapsed_s, ended_elapsed_s) values
 ('c1000000-0000-0000-0000-000000000001', '2026-01-10 08:00:20+00', '2026-01-10 08:00:30+00', 20, 30);

insert into runningtracker.run_metrics (run_id, algo_version, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series) values
 ('c1000000-0000-0000-0000-000000000001', 1, 1990, 160, 180,
  '[{"km": 2, "distance_m": 1000, "duration_s": 280, "pace_s_per_km": 280, "avg_hr": 162, "partial": false},
    {"km": 1, "distance_m": 1000, "duration_s": 260, "pace_s_per_km": 260, "avg_hr": 158, "partial": false}]'::jsonb,
  '[[5, 262.5], [10, 258.0], [15, 270.0]]'::jsonb,
  '[[5, 150.0], [10, 155.0], [15, 160.0]]'::jsonb);

-- fix-run-gap: seq 1-4 and 9-20 stored (odd = location, even = heart_rate), seq 5-8 missing
insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000002',
       case when n % 2 = 1 then 'location' else 'heart_rate' end, n,
       timestamptz '2026-01-11 08:00:00+00' + n * interval '1 second',
       case when n % 2 = 1 then
         jsonb_build_object('type', 'location.sample', 'timestamp', to_char(timestamptz '2026-01-11 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                            'latitude', 52.0 + (4.0 * n) / 111194.9266, 'longitude', 13.0, 'accuracyMeters', 5.0)
       else
         jsonb_build_object('type', 'heartRate.sample', 'timestamp', to_char(timestamptz '2026-01-11 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                            'bpm', 150)
       end
from generate_series(1, 20) as n
where n not between 5 and 8;

insert into runningtracker.pairing_codes (code_hash, created_at, expires_at, used_at, device_id) values
 (encode(sha256('FIXACTV2'::bytea), 'hex'), now(), now() + interval '5 minutes', null, null),
 (encode(sha256('FIXEXPD2'::bytea), 'hex'), now() - interval '1 hour', now() - interval '55 minutes', null, null),
 (encode(sha256('FIXUSED2'::bytea), 'hex'), now() - interval '10 minutes', now() + interval '4 minutes', now() - interval '9 minutes', 'd1000000-0000-0000-0000-000000000001');

-- ── Sprint02_RunFinishAndRecovery ────────────────────────────────────────────
-- fix-run-recovery        c1..05 complete, device-1. started 2026-01-12 08:00:00, run_finished_at +600 s, finished_at +900 s.
--                         GPS 1..600 s (4 m/s north); HR 1..900 s with a spike (200 bpm at +599 s), a gap at +731..+750 s,
--                         150 bpm while running, then 150 - (t-600)/5 (integer division); counts 600 / 880, last_seq 1480. Golden: hr_end 150, hr_60 138, hr_120 126.
-- fix-run-recovery-nohr   c1..06 complete, device-1. run_finished_at +300 s, finished_at +480 s, GPS only, recovery all null.
-- fix-run-recovery-upload c1..07 uploading, device-1. started 2026-01-14 08:00:00; GPS 1..300 s (seq 1..300), HR 1..450 s (seq 301..750):
--                         150 bpm to +300 s, then 150 - (t-300)/5. Finish not yet called (run_finished_at +300 s, finished_at +450 s).
insert into runningtracker.runs (id, run_type, status, started_at, finished_at, run_finished_at, elapsed_s, moving_s, distance_m, device_id, created_at) values
 ('c1000000-0000-0000-0000-000000000005', 'continuous', 'complete',  '2026-01-12 08:00:00+00', '2026-01-12 08:15:00+00', '2026-01-12 08:10:00+00', 600, 600, 2396, 'd1000000-0000-0000-0000-000000000001', '2026-01-12 08:16:00+00'),
 ('c1000000-0000-0000-0000-000000000006', 'continuous', 'complete',  '2026-01-13 08:00:00+00', '2026-01-13 08:08:00+00', '2026-01-13 08:05:00+00', 300, 300, 1180, 'd1000000-0000-0000-0000-000000000001', '2026-01-13 08:09:00+00'),
 ('c1000000-0000-0000-0000-000000000007', 'continuous', 'uploading', '2026-01-14 08:00:00+00', null, null, null, null, null, 'd1000000-0000-0000-0000-000000000001', '2026-01-14 08:00:00+00');

-- fix-run-recovery samples: locations seq 1..600 (= t), heart rate seq 601..1480 (880 readings, contiguous across the gap)
insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000005', 'location', n, timestamptz '2026-01-12 08:00:00+00' + n * interval '1 second',
       jsonb_build_object('type', 'location.sample', 'timestamp', to_char(timestamptz '2026-01-12 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'latitude', 52.0 + (4.0 * n) / 111194.9266, 'longitude', 13.0, 'accuracyMeters', 5.0,
                          'speedMetersPerSecond', null, 'altitudeMeters', null, 'bearingDegrees', null, 'elapsedRealtimeNanos', null)
from generate_series(1, 600) as n;

insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000005', 'heart_rate', 600 + row_number() over (order by n), timestamptz '2026-01-12 08:00:00+00' + n * interval '1 second',
       jsonb_build_object('type', 'heartRate.sample', 'timestamp', to_char(timestamptz '2026-01-12 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'bpm', case when n = 599 then 200 when n <= 600 then 150 else 150 - (n - 600) / 5 end,
                          'rrIntervalsMs', null, 'source', 'bluetooth', 'elapsedRealtimeNanos', null)
from generate_series(1, 900) as n
where n not between 731 and 750;

-- stored metrics: running-phase values only (avg = (599 * 150 + 200) / 600); curve value is a plausible 150 - k, steps 135/140/145 absent (gap)
insert into runningtracker.run_metrics (run_id, algo_version, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series, recovery)
select 'c1000000-0000-0000-0000-000000000005', 3, 2396, 150.0833333, 200, '[]'::jsonb,
       '[[10, 250.0]]'::jsonb, '[[5, 150.0], [10, 150.0]]'::jsonb,
       jsonb_build_object('hr_end', 150, 'hr_60', 138, 'hr_120', 126, 'hrr60', 12, 'hrr120', 24,
                          'curve', (select jsonb_agg(jsonb_build_array(5 * k, 150 - k) order by k) from generate_series(0, 60) as k where 5 * k not in (135, 140, 145)));

-- fix-run-recovery-nohr: GPS every 5 s, no heart rate
insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000006', 'location', n / 5, timestamptz '2026-01-13 08:00:00+00' + n * interval '1 second',
       jsonb_build_object('type', 'location.sample', 'timestamp', to_char(timestamptz '2026-01-13 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'latitude', 52.0 + (4.0 * n) / 111194.9266, 'longitude', 13.0, 'accuracyMeters', 5.0)
from generate_series(5, 300, 5) as n;

insert into runningtracker.run_metrics (run_id, algo_version, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series, recovery) values
 ('c1000000-0000-0000-0000-000000000006', 3, 1180, null, null, '[]'::jsonb, '[[10, 250.0]]'::jsonb, '[]'::jsonb,
  '{"hr_end": null, "hr_60": null, "hr_120": null, "hrr60": null, "hrr120": null, "curve": []}'::jsonb);

-- fix-run-recovery-upload: all samples stored (running GPS + HR, recovery-phase HR); finish not yet called
insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000007', 'location', n, timestamptz '2026-01-14 08:00:00+00' + n * interval '1 second',
       jsonb_build_object('type', 'location.sample', 'timestamp', to_char(timestamptz '2026-01-14 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'latitude', 52.0 + (4.0 * n) / 111194.9266, 'longitude', 13.0, 'accuracyMeters', 5.0,
                          'speedMetersPerSecond', null, 'altitudeMeters', null, 'bearingDegrees', null, 'elapsedRealtimeNanos', null)
from generate_series(1, 300) as n;

insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000007', 'heart_rate', 300 + n, timestamptz '2026-01-14 08:00:00+00' + n * interval '1 second',
       jsonb_build_object('type', 'heartRate.sample', 'timestamp', to_char(timestamptz '2026-01-14 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'bpm', case when n <= 300 then 150 else 150 - (n - 300) / 5 end,
                          'rrIntervalsMs', null, 'source', 'bluetooth', 'elapsedRealtimeNanos', null)
from generate_series(1, 450) as n;

-- ---- Sprint03 cadence fixtures --------------------------------------------------------------------------------
-- fix-run-cadence        c1..08 complete, device-1. started 2026-01-15 08:00:00, run_finished_at = finished_at = +300 s.
--                        GPS seq 1..300 (4 m/s north), HR seq 301..600 (150 bpm), steps seq 601..1450 (one every 353 ms = 170 spm).
--                        Stored metrics (algo 3) carry a cadence object (series t=5..295, 170 spm). No route; tests link one via POST /routes.
-- fix-run-cadence-empty  c1..09 complete, device-1. started 2026-01-17 08:00:00. GPS seq 1..300, 3 irregular steps (seq 301..303): cadence object, empty series.
-- fix-run-cadence-upload c1..0a uploading, device-1. started 2026-01-16 08:00:00. GPS seq 1..150, steps seq 151..574 (every 353 ms, 0..150 s).
--                        Tests send finish with run_finished_at +120 s, finished_at +130 s, pause +60..+70 s (steps after +120 and inside the pause).
insert into runningtracker.runs (id, run_type, status, started_at, finished_at, run_finished_at, elapsed_s, moving_s, distance_m, device_id, created_at) values
 ('c1000000-0000-0000-0000-000000000008', 'continuous', 'complete',  '2026-01-15 08:00:00+00', '2026-01-15 08:05:00+00', '2026-01-15 08:05:00+00', 300, 300, 1200, 'd1000000-0000-0000-0000-000000000001', '2026-01-15 08:06:00+00'),
 ('c1000000-0000-0000-0000-000000000009', 'continuous', 'complete',  '2026-01-17 08:00:00+00', '2026-01-17 08:05:00+00', '2026-01-17 08:05:00+00', 300, 300, 1200, 'd1000000-0000-0000-0000-000000000001', '2026-01-17 08:06:00+00'),
 ('c1000000-0000-0000-0000-00000000000a', 'continuous', 'uploading', '2026-01-16 08:00:00+00', null, null, null, null, null, 'd1000000-0000-0000-0000-000000000001', '2026-01-16 08:00:00+00');

insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select r.id, 'location', n, r.t0 + n * interval '1 second',
       jsonb_build_object('type', 'location.sample', 'timestamp', to_char(r.t0 + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'latitude', 52.0 + (4.0 * n) / 111194.9266, 'longitude', 13.0, 'accuracyMeters', 5.0,
                          'speedMetersPerSecond', null, 'altitudeMeters', null, 'bearingDegrees', null, 'elapsedRealtimeNanos', null)
from (values ('c1000000-0000-0000-0000-000000000008'::uuid, timestamptz '2026-01-15 08:00:00+00', 300),
             ('c1000000-0000-0000-0000-000000000009'::uuid, timestamptz '2026-01-17 08:00:00+00', 300),
             ('c1000000-0000-0000-0000-00000000000a'::uuid, timestamptz '2026-01-16 08:00:00+00', 150)) as r(id, t0, n_max),
     generate_series(1, 300) as n
where n <= r.n_max;

insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000008', 'heart_rate', 300 + n, timestamptz '2026-01-15 08:00:00+00' + n * interval '1 second',
       jsonb_build_object('type', 'heartRate.sample', 'timestamp', to_char(timestamptz '2026-01-15 08:00:00+00' + n * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'bpm', 150, 'rrIntervalsMs', null, 'source', 'bluetooth', 'elapsedRealtimeNanos', null)
from generate_series(1, 300) as n;

-- steps: n-th step at start + n * 353 ms
insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000008', 'step', 600 + n, timestamptz '2026-01-15 08:00:00+00' + n * interval '353 milliseconds',
       jsonb_build_object('type', 'step.sample', 'captureId', 'c1000000-0000-0000-0000-000000000008', 'sequence', 600 + n,
                          'timestamp', to_char(timestamptz '2026-01-15 08:00:00+00' + n * interval '353 milliseconds', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'elapsedRealtimeNanos', null)
from generate_series(1, 850) as n;

insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-00000000000a', 'step', 150 + n, timestamptz '2026-01-16 08:00:00+00' + n * interval '353 milliseconds',
       jsonb_build_object('type', 'step.sample', 'captureId', 'c1000000-0000-0000-0000-00000000000a', 'sequence', 150 + n,
                          'timestamp', to_char(timestamptz '2026-01-16 08:00:00+00' + n * interval '353 milliseconds', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'elapsedRealtimeNanos', null)
from generate_series(1, 424) as n;

-- fix-run-cadence-empty: three irregular steps, none usable
insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
select 'c1000000-0000-0000-0000-000000000009', 'step', 300 + n, timestamptz '2026-01-17 08:00:00+00' + (array[10, 20, 35])[n] * interval '1 second',
       jsonb_build_object('type', 'step.sample', 'captureId', 'c1000000-0000-0000-0000-000000000009', 'sequence', 300 + n,
                          'timestamp', to_char(timestamptz '2026-01-17 08:00:00+00' + (array[10, 20, 35])[n] * interval '1 second', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
                          'elapsedRealtimeNanos', null)
from generate_series(1, 3) as n;

insert into runningtracker.run_metrics (run_id, algo_version, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series, recovery, cadence)
select 'c1000000-0000-0000-0000-000000000008', 3, 1196, 150, 150, '[]'::jsonb, '[[10, 250.0]]'::jsonb, '[[5, 150.0], [10, 150.0]]'::jsonb, null,
       jsonb_build_object('avg_spm', 170.0, 'algo', 1,
                          'series', (select jsonb_agg(jsonb_build_object('t', 5.0 * k, 'spm', 170.0, 'conf', 0.95) order by k) from generate_series(1, 59) as k));

insert into runningtracker.run_metrics (run_id, algo_version, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series, recovery, cadence) values
 ('c1000000-0000-0000-0000-000000000009', 3, 1196, null, null, '[]'::jsonb, '[[10, 250.0]]'::jsonb, '[]'::jsonb, null,
  '{"avg_spm": null, "series": [], "algo": 1}'::jsonb);
