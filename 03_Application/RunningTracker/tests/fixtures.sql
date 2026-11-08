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
