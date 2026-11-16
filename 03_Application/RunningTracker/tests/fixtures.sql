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

-- ---- Sprint04 Ghost Coach fixtures ------------------------------------------------------------------------------
-- coach_settings  id 1, AI off. (re-seeded here because conftest truncates the table)
-- runs            fix-run-coach-1 c2..01 2026-03-12 (newest; comment/category markers, one GPS sample, cadence 168; tests add route/recovery themselves)
--                 fix-run-coach-2 c2..02 2026-03-08 (cadence 170)   fix-run-coach-3 c2..03 2026-03-04 (cadence 172)
--                 fix-run-coach-4 c2..04 2026-03-01 (no cadence). All complete, device-1, metrics stored. The Sprint01-03 complete
--                 runs with metrics (all earlier, Jan 2026) belong to the history/window as well.
-- plans           fix-plan-recommended   c3..01 easy_continuous, recommended, created -1 day (HR/pace/cadence on the steady segment)
--                 fix-plan-accepted      c3..02 accepted, no run, decided -2 days
--                 fix-plan-accepted-linked c3..03 accepted, run = fix-run-coach-2, outcome null
--                 fix-plan-disregarded   c3..04 disregarded
--                 fix-plan-interval      c3..05 interval, completed (no run), created -12 hours: the newest non-disregarded plan
-- profile         one measured (natural_cadence_spm) and one inferred (aerobic_endurance) row
insert into runningtracker.coach_settings (id, goal_text) values (1, 'Run a relaxed half marathon') on conflict (id) do nothing;

insert into runningtracker.runs (id, run_type, status, started_at, finished_at, elapsed_s, moving_s, distance_m, comment, category, route_id, device_id, created_at) values
 ('c2000000-0000-0000-0000-000000000001', 'continuous', 'complete', '2026-03-12 07:00:00+00', '2026-03-12 07:26:00+00', 1560, 1500, 5000, 'SECRET-COMMENT', 'SECRET-CATEGORY', null, 'd1000000-0000-0000-0000-000000000001', '2026-03-12 07:30:00+00'),
 ('c2000000-0000-0000-0000-000000000002', 'continuous', 'complete', '2026-03-08 07:00:00+00', '2026-03-08 07:32:00+00', 1920, 1800, 6000, null, null, null, 'd1000000-0000-0000-0000-000000000001', '2026-03-08 07:35:00+00'),
 ('c2000000-0000-0000-0000-000000000003', 'continuous', 'complete', '2026-03-04 07:00:00+00', '2026-03-04 07:26:00+00', 1560, 1520, 5000, null, null, null, 'd1000000-0000-0000-0000-000000000001', '2026-03-04 07:30:00+00'),
 ('c2000000-0000-0000-0000-000000000004', 'continuous', 'complete', '2026-03-01 07:00:00+00', '2026-03-01 07:45:00+00', 2700, 2640, 8000, null, null, null, 'd1000000-0000-0000-0000-000000000001', '2026-03-01 07:50:00+00');

insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload) values
 ('c2000000-0000-0000-0000-000000000001', 'location', 1, '2026-03-12 07:00:01+00',
  '{"type": "location.sample", "timestamp": "2026-03-12T07:00:01.000Z", "latitude": 52.123456, "longitude": 13.654321, "accuracyMeters": 5.0}'::jsonb);

insert into runningtracker.run_pauses (run_id, started_at, ended_at, started_elapsed_s, ended_elapsed_s) values
 ('c2000000-0000-0000-0000-000000000002', '2026-03-08 07:10:00+00', '2026-03-08 07:12:00+00', 600, 720);

insert into runningtracker.run_metrics (run_id, algo_version, server_distance_m, avg_hr, max_hr, splits, pace_series, hr_series, recovery, cadence) values
 ('c2000000-0000-0000-0000-000000000001', 3, 4990, 145, 160,
  '[{"km": 1, "distance_m": 1000, "duration_s": 310, "pace_s_per_km": 310, "avg_hr": 140, "partial": false},
    {"km": 2, "distance_m": 1000, "duration_s": 300, "pace_s_per_km": 300, "avg_hr": 144, "partial": false},
    {"km": 3, "distance_m": 1000, "duration_s": 295, "pace_s_per_km": 295, "avg_hr": 146, "partial": false},
    {"km": 4, "distance_m": 1000, "duration_s": 298, "pace_s_per_km": 298, "avg_hr": 148, "partial": false},
    {"km": 5, "distance_m": 990, "duration_s": 296, "pace_s_per_km": 299, "avg_hr": 150, "partial": true}]'::jsonb,
  '[[5, 310.0], [65, 302.0], [125, 298.0], [605, 296.0], [1205, 300.0]]'::jsonb,
  '[[5, 130.0], [65, 140.0], [125, 144.0], [605, 150.0], [1205, 152.0]]'::jsonb,
  null,
  '{"avg_spm": 168.0, "algo": 1, "series": [{"t": 60.0, "spm": 166.0, "conf": 0.9}, {"t": 600.0, "spm": 168.0, "conf": 0.9}]}'::jsonb),
 ('c2000000-0000-0000-0000-000000000002', 3, 5990, 148, 165, '[]'::jsonb,
  '[[5, 300.0], [305, 300.0], [905, 300.0]]'::jsonb, '[[5, 140.0], [305, 148.0], [905, 150.0]]'::jsonb, null,
  '{"avg_spm": 170.0, "algo": 1, "series": [{"t": 305.0, "spm": 170.0, "conf": 0.9}]}'::jsonb),
 ('c2000000-0000-0000-0000-000000000003', 3, 4990, 150, 170, '[]'::jsonb,
  '[[5, 304.0]]'::jsonb, '[[5, 150.0]]'::jsonb, null,
  '{"avg_spm": 172.0, "algo": 1, "series": [{"t": 5.0, "spm": 172.0, "conf": 0.9}]}'::jsonb),
 ('c2000000-0000-0000-0000-000000000004', 3, 7990, 152, 172,
  '[{"km": 1, "distance_m": 1000, "duration_s": 290, "pace_s_per_km": 290, "avg_hr": 150, "partial": false}]'::jsonb,
  '[[5, 330.0]]'::jsonb, '[[5, 152.0]]'::jsonb, null, null);

insert into runningtracker.coach_plans (id, plan_schema_version, plan_type, status, plan, active_plan, run_id, outcome, created_at, decided_at) values
 ('c3000000-0000-0000-0000-000000000001', 1, 'easy_continuous', 'recommended',
  '{"schema_version": 1, "type": "easy_continuous", "title": "Easy 40", "rationale": "Keep it relaxed.", "target_distance_m": null,
    "segments": [{"kind": "warmup", "duration_s": 300, "hr": null, "pace": null, "cadence": null},
                 {"kind": "steady", "duration_s": 1800, "hr": {"min": 130, "max": 145}, "pace": {"fast_s_per_km": 330, "slow_s_per_km": 390}, "cadence": {"min": 165, "max": 175}},
                 {"kind": "cooldown", "duration_s": 300, "hr": null, "pace": null, "cadence": null}],
    "triggers": []}'::jsonb, null, null, null, now() - interval '1 day', null),
 ('c3000000-0000-0000-0000-000000000002', 1, 'easy_continuous', 'accepted',
  '{"schema_version": 1, "type": "easy_continuous", "title": "Easy accepted", "rationale": null, "target_distance_m": null,
    "segments": [{"kind": "warmup", "duration_s": 300, "hr": null, "pace": null, "cadence": null},
                 {"kind": "steady", "duration_s": 1800, "hr": {"min": 130, "max": 145}, "pace": null, "cadence": {"min": 165, "max": 175}},
                 {"kind": "cooldown", "duration_s": 300, "hr": null, "pace": null, "cadence": null}],
    "triggers": []}'::jsonb,
  '{"schema_version": 1, "type": "easy_continuous", "title": "Easy accepted", "rationale": null, "target_distance_m": null,
    "segments": [{"kind": "warmup", "duration_s": 300, "hr": null, "pace": null, "cadence": null},
                 {"kind": "steady", "duration_s": 1800, "hr": {"min": 130, "max": 145}, "pace": null, "cadence": {"min": 165, "max": 175}},
                 {"kind": "cooldown", "duration_s": 300, "hr": null, "pace": null, "cadence": null}],
    "triggers": []}'::jsonb, null, null, now() - interval '3 days', now() - interval '2 days'),
 ('c3000000-0000-0000-0000-000000000003', 1, 'recovery', 'accepted',
  '{"schema_version": 1, "type": "recovery", "title": "Linked", "rationale": null, "target_distance_m": null,
    "segments": [{"kind": "steady", "duration_s": 1200, "hr": null, "pace": null, "cadence": null}], "triggers": []}'::jsonb,
  '{"schema_version": 1, "type": "recovery", "title": "Linked", "rationale": null, "target_distance_m": null,
    "segments": [{"kind": "steady", "duration_s": 1200, "hr": null, "pace": null, "cadence": null}], "triggers": []}'::jsonb,
  'c2000000-0000-0000-0000-000000000002', null, now() - interval '6 days', now() - interval '5 days'),
 ('c3000000-0000-0000-0000-000000000004', 1, 'recovery', 'disregarded',
  '{"schema_version": 1, "type": "recovery", "title": "Dropped", "rationale": null, "target_distance_m": null,
    "segments": [{"kind": "steady", "duration_s": 1200, "hr": null, "pace": null, "cadence": null}], "triggers": []}'::jsonb,
  null, null, null, now() - interval '8 days', now() - interval '7 days'),
 ('c3000000-0000-0000-0000-000000000005', 1, 'interval', 'completed',
  '{"schema_version": 1, "type": "interval", "title": "Intervals", "rationale": null, "target_distance_m": null,
    "segments": [{"kind": "work", "duration_s": 120, "hr": null, "pace": null, "cadence": null},
                 {"kind": "recovery", "duration_s": 120, "hr": null, "pace": null, "cadence": null},
                 {"kind": "work", "duration_s": 120, "hr": null, "pace": null, "cadence": null}], "triggers": []}'::jsonb,
  '{"schema_version": 1, "type": "interval", "title": "Intervals", "rationale": null, "target_distance_m": null,
    "segments": [{"kind": "work", "duration_s": 120, "hr": null, "pace": null, "cadence": null},
                 {"kind": "recovery", "duration_s": 120, "hr": null, "pace": null, "cadence": null},
                 {"kind": "work", "duration_s": 120, "hr": null, "pace": null, "cadence": null}], "triggers": []}'::jsonb,
  null, '{"planned_s": 360, "done_s": 360, "completed": true, "in_range": {"hr": null, "pace": null, "cadence": null}}'::jsonb,
  now() - interval '12 hours', now() - interval '11 hours');

insert into runningtracker.coach_profile_items (key, basis, value_text, value_num, unit, confidence, n_runs) values
 ('natural_cadence_spm', 'measured', '170 spm', 170, 'spm', null, 4),
 ('aerobic_endurance', 'inferred', 'Steady base, improving slowly', null, null, 0.5, 4);
