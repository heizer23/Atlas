-- RunningTracker Sprint04_GhostCoach -- private application schema.
-- sprint_note: seeded from the runtime schema.sql (03_Application/RunningTracker/schema.sql, the clean snapshot after Sprint03) and extended
-- ADDITIVELY. Only the block under "Sprint04 [NEW]" at the end is this sprint's change; everything above it is unchanged and must stay
-- equal to the runtime copy (the Sprint03 '[NEW]' markers of the previous artifact were reduced to plain 'Sprint03:' comments).
-- Runtime canonical path: 03_Application/RunningTracker/schema.sql (copy of this file; executed idempotently at startup).
-- Private tables: not a cross-application contract. Other components must never query schema `runningtracker`.
-- Time columns: run times (started_at, finished_at, run_finished_at, pause stamps, sample_ts) are phone-reported UTC (persisted domain time);
-- created_at / expires_at / last_used_at / used_at / locked_at / failed_at / revoked_at / consented_at / decided_at / called_at /
-- analysed_at are server time (now()).

begin;

create schema if not exists runningtracker;

-- Paired AtlasPhone devices. Token is a random 256-bit value shown once; only its SHA-256 hex digest is stored.
create table if not exists runningtracker.devices (
    id           uuid        primary key default gen_random_uuid(),
    name         text        not null check (char_length(name) between 1 and 60),
    token_hash   text        not null unique,
    created_at   timestamptz not null default now(),
    last_used_at timestamptz,
    revoked_at   timestamptz
);

-- One-time pairing codes (8 chars). Only the SHA-256 hex digest of the code is stored.
create table if not exists runningtracker.pairing_codes (
    id         uuid        primary key default gen_random_uuid(),
    code_hash  text        not null unique,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    used_at    timestamptz,
    locked_at  timestamptz,
    device_id  uuid        references runningtracker.devices(id) on delete set null
);

create index if not exists ix_pairing_codes_expires_at
    on runningtracker.pairing_codes(expires_at);

-- Failed pair attempts (global, single-user system). Drives the lockout rule (see Sprint01_RecordAndSync/10_architecture.json invariants).
create table if not exists runningtracker.pairing_failures (
    id        bigserial   primary key,
    failed_at timestamptz not null default now()
);

create index if not exists ix_pairing_failures_failed_at
    on runningtracker.pairing_failures(failed_at);

-- One row per run. id is client-generated (phone capture id) or server-generated for prepared runs; it is stable.
create table if not exists runningtracker.runs (
    id          uuid        primary key,
    run_type    text        not null default 'continuous'
                            check (run_type in ('continuous', 'interval')),
    status      text        not null
                            check (status in ('prepared', 'uploading', 'complete')),
    short_id    text        unique,
    title       text        check (title is null or char_length(title) <= 120),
    planned_for timestamptz,
    expires_at  timestamptz,
    started_at  timestamptz,
    finished_at timestamptz,
    elapsed_s   double precision check (elapsed_s is null or elapsed_s >= 0),
    moving_s    double precision check (moving_s is null or moving_s >= 0),
    distance_m  double precision check (distance_m is null or distance_m >= 0),
    comment     text        check (comment is null or char_length(comment) <= 2000),
    device_id   uuid        references runningtracker.devices(id),
    route_id    uuid,       -- FK fk_runs_route added below (routes table)
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    check (status <> 'prepared' or (short_id is not null and expires_at is not null)),
    check (status = 'prepared' or started_at is not null),
    check (finished_at is null or started_at is null or finished_at >= started_at)
);

-- Free-text run category ("Easy Continuous", "Tempo Continuous"); combined effort+structure label chosen by the user.
alter table runningtracker.runs add column if not exists category text
    check (category is null or char_length(category) <= 60);
-- Where the recording came from: the phone upload or a one-off file import (Polar FIT). Raw samples are identical in shape.
alter table runningtracker.runs add column if not exists source text not null default 'phone'
    check (source in ('phone', 'fit_import'));

create index if not exists ix_runs_started_at on runningtracker.runs(started_at desc);
create index if not exists ix_runs_status     on runningtracker.runs(status);

-- Raw samples exactly as recorded on the phone (nullable fields stay null). Never updated; duplicates are ignored.
-- Sprint03: the stream set grows by 'step' (see ck_run_samples_stream below). This inline constraint is the
-- original Sprint01 one and is replaced idempotently further down; it is left unchanged here so that a fresh database and an
-- existing database converge on the same final constraint.
create table if not exists runningtracker.run_samples (
    run_id    uuid        not null references runningtracker.runs(id) on delete cascade,
    stream    text        not null check (stream in ('location', 'heart_rate')),
    seq       bigint      not null check (seq >= 1),
    sample_ts timestamptz not null,
    payload   jsonb       not null,
    primary key (run_id, stream, seq)
);

create index if not exists ix_run_samples_run_seq on runningtracker.run_samples(run_id, seq);

-- Manual pauses. Replaced as a set on every finish call (idempotent).
create table if not exists runningtracker.run_pauses (
    id                uuid             primary key default gen_random_uuid(),
    run_id            uuid             not null references runningtracker.runs(id) on delete cascade,
    started_at        timestamptz      not null,
    ended_at          timestamptz      not null,
    started_elapsed_s double precision not null check (started_elapsed_s >= 0),
    ended_elapsed_s   double precision not null,
    check (ended_at >= started_at),
    check (ended_elapsed_s >= started_elapsed_s),
    unique (run_id, started_at)
);

-- Derived metrics; recomputable from run_samples + run_pauses (algorithm A1, versioned by algo_version).
create table if not exists runningtracker.run_metrics (
    run_id             uuid        primary key references runningtracker.runs(id) on delete cascade,
    algo_version       integer     not null,
    computed_at        timestamptz not null default now(),
    server_distance_m  double precision not null check (server_distance_m >= 0),
    avg_hr             double precision,
    max_hr             integer,
    splits             jsonb       not null default '[]'::jsonb,
    pace_series        jsonb       not null default '[]'::jsonb,
    hr_series          jsonb       not null default '[]'::jsonb
);

commit;

-- Reusable course. Geometry is an immutable canonical reference: [[lat, lon, cumulative_m], ...] along the
-- simplified path (geometry_version names the derivation). Ghost comparison later projects onto this path.
create table if not exists runningtracker.routes (
    id                   uuid             primary key default gen_random_uuid(),
    name                 text             not null check (char_length(btrim(name)) between 1 and 120),
    description          text             check (description is null or char_length(description) <= 2000),
    geometry             jsonb            not null,
    reference_distance_m double precision not null check (reference_distance_m > 0),
    is_loop              boolean          not null,
    point_count          integer          not null check (point_count >= 2),
    geometry_version     integer          not null,
    source_run_id        uuid             references runningtracker.runs(id) on delete set null,
    created_at           timestamptz      not null default now(),
    updated_at           timestamptz      not null default now()
);
create unique index if not exists ux_routes_name on runningtracker.routes (lower(btrim(name)));

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'fk_runs_route') then
        alter table runningtracker.runs
            add constraint fk_runs_route foreign key (route_id) references runningtracker.routes(id) on delete restrict;
    end if;
end $$;
create index if not exists ix_runs_route_id on runningtracker.runs(route_id);

-- Derived (recomputable) route progress of a run: the ghost profile. One row per run that is linked to a route.
-- profile = [[moving_t_s, progress_m, hr_bpm|null], ...]. qualified=false rows keep the reason (e.g. route_not_completed).
create table if not exists runningtracker.run_route_progress (
    run_id               uuid        primary key references runningtracker.runs(id) on delete cascade,
    route_id             uuid        not null references runningtracker.routes(id) on delete cascade,
    geometry_version     integer     not null,
    algo_version         integer     not null,
    qualified            boolean     not null,
    reason               text,
    end_progress_m       double precision not null,
    coverage             double precision not null,
    matched_fixes        integer     not null,
    off_course_fixes     integer     not null,
    profile              jsonb       not null,
    computed_at          timestamptz not null default now()
);
create index if not exists ix_run_route_progress_route on runningtracker.run_route_progress(route_id) where qualified;

-- Ghost chosen when a run is prepared (resolved to a concrete run at preparation time; null = no ghost).
alter table runningtracker.runs add column if not exists ghost_run_id uuid
    references runningtracker.runs(id) on delete set null;

-- Sprint02: end of the RUNNING phase (phone-reported UTC, persisted domain time). Everything between run_finished_at and
-- finished_at is the recovery phase (HR only). NULL = legacy run or a run without recovery phase: the whole run is running.
-- elapsed_s / moving_s / distance_m above keep their meaning and now describe the running phase only.
alter table runningtracker.runs add column if not exists run_finished_at timestamptz;

-- Sprint02: ordering rule started_at <= run_finished_at <= finished_at (finished_at may still be null on a row that never finished).
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'ck_runs_run_finished_at') then
        alter table runningtracker.runs
            add constraint ck_runs_run_finished_at
            check (run_finished_at is null
                   or (started_at is not null and run_finished_at >= started_at
                       and (finished_at is null or run_finished_at <= finished_at)));
    end if;
end $$;

-- Sprint02: derived recovery metrics, recomputable from run_samples + runs.run_finished_at + runs.finished_at.
-- SQL NULL (not JSON null) = no recovery phase. Object shape (declared once in Sprint02_RunFinishAndRecovery/10_architecture.json exposed_surfaces, RecoveryRow/series):
-- {"hr_end": n|null, "hr_60": n|null, "hr_120": n|null, "hrr60": n|null, "hrr120": n|null, "curve": [[t_s_since_run_finished_at, bpm], ...]}
alter table runningtracker.run_metrics add column if not exists recovery jsonb;

-- Sprint03: the raw step stream. One sample per detected step (payload.timestamp = sensor event time, phone UTC); raw rows are never
-- modified. The previous inline constraint (run_samples_stream_check, 2 streams) is dropped and replaced by the named 3-stream one.
-- Idempotent: the drop is a no-op once the inline constraint is gone, the add is guarded by pg_constraint. Adding the constraint scans
-- run_samples once (existing rows are all location/heart_rate, so it always validates).
do $$
begin
    alter table runningtracker.run_samples drop constraint if exists run_samples_stream_check;
    if not exists (select 1 from pg_constraint where conname = 'ck_run_samples_stream') then
        alter table runningtracker.run_samples
            add constraint ck_run_samples_stream check (stream in ('location', 'heart_rate', 'step'));
    end if;
end $$;

-- Sprint03: derived cadence of the RUNNING phase, recomputable from the 'step' rows + run_pauses + runs.started_at/run_finished_at/finished_at
-- (algorithm CAD1, versioned by cadence.algo and by run_metrics.algo_version). SQL NULL (not JSON null) = no step samples in the running
-- phase (legacy run, permission denied, no sensor). Object shape (declared once in Sprint03_CadenceAndLiveRacing/10_architecture.json invariant CAD2):
-- {"avg_spm": n|null, "series": [{"t": seconds_since_started_at, "spm": n, "conf": 0..1}, ...], "algo": integer}
-- Gaps are absent points, never zero.
alter table runningtracker.run_metrics add column if not exists cadence jsonb;

-- Sprint03: the ghost's cadence along the route, derived next to the profile when the run is matched onto its route.
-- [[progress_m_bucket_start, spm], ...] ascending, 20 m buckets, empty buckets absent. SQL NULL = the run has no usable cadence
-- (never derived from speed). Served as `cadence_by_progress` by GET /native/runs/{id}/ghost-profile.
alter table runningtracker.run_route_progress add column if not exists cadence_by_progress jsonb;

-- =====================================================================================================================
-- Sprint04 [NEW] Ghost Coach. All tables below are new, private and additive (create if not exists); nothing above is changed.
-- Single-user system: no owner column anywhere. Server clock (now()) is used ONLY for the audit/consent/decision columns named in the
-- header; every run-derived value keeps the phone-UTC domain time of the run it comes from (invariant T4 in 10_architecture.json).
-- =====================================================================================================================

begin;

-- Exactly one row (id = 1). The external-AI opt-in lives here and nowhere else (invariant CO1). ai_enabled is false until the user
-- consents; disabling clears the consent columns, so enabled <=> a consent of some version is recorded.
create table if not exists runningtracker.coach_settings (
    id              smallint    primary key check (id = 1),
    ai_enabled      boolean     not null default false,
    consent_version integer,
    consented_at    timestamptz,
    goal_text       text        check (goal_text is null or char_length(goal_text) <= 500),
    updated_at      timestamptz not null default now(),
    check ((ai_enabled and consent_version is not null and consented_at is not null)
           or (not ai_enabled and consent_version is null and consented_at is null))
);
insert into runningtracker.coach_settings (id) values (1) on conflict (id) do nothing;

-- One analysis per run (a forced re-analysis updates the same row). sent_payload is the exact JSON document that was sent to the
-- provider as the user message (audit of what left the system, invariant EGR1); it contains no raw GPS, ids, titles or comments.
create table if not exists runningtracker.coach_analyses (
    id                   uuid        primary key default gen_random_uuid(),
    run_id               uuid        not null unique references runningtracker.runs(id) on delete cascade,
    assessment           text        not null check (char_length(assessment) between 1 and 1500),
    previous_effect      text        check (previous_effect is null or char_length(previous_effect) <= 600),
    profile_updates      jsonb       not null default '[]'::jsonb,
    plan_rejected_reason text        check (plan_rejected_reason is null or char_length(plan_rejected_reason) <= 200),
    payload_version      integer     not null,
    prompt_version       text        not null check (char_length(prompt_version) <= 20),
    model                text        not null check (char_length(model) between 1 and 80),
    sent_payload         jsonb       not null,
    analysed_at          timestamptz not null default now()
);

-- Every outbound provider attempt (success or failure) for the daily cap and failure audit. No request or response content.
create table if not exists runningtracker.coach_ai_calls (
    id        bigserial   primary key,
    run_id    uuid        references runningtracker.runs(id) on delete set null,
    called_at timestamptz not null default now(),
    outcome   text        not null check (outcome in ('ok', 'provider_error', 'invalid_response'))
);
create index if not exists ix_coach_ai_calls_called_at on runningtracker.coach_ai_calls(called_at desc);

-- Recommended / accepted training plans and their outcome history (invariants PLAN1, OUT1).
--   plan        = the validated AI recommendation, never edited.
--   active_plan = the version the user accepted (plan + user overrides); NULL until accepted. The phone receives active_plan.
--   run_id      = the run that executed the plan (set at finish from FinishRequest.coach_plan_id); at most one run per plan.
--   outcome     = derived, recomputable from run_metrics + run_pauses (OUT1); NULL until the linked run is complete.
-- Shape of plan / active_plan: CoachPlanV1 (declared once in 10_scaffolding.json backend/coach_plan.py).
create table if not exists runningtracker.coach_plans (
    id                  uuid        primary key default gen_random_uuid(),
    analysis_id         uuid        references runningtracker.coach_analyses(id) on delete set null,
    plan_schema_version integer     not null,
    plan_type           text        not null
                                    check (plan_type in ('easy_continuous', 'hr_controlled', 'recovery', 'endurance', 'interval')),
    status              text        not null
                                    check (status in ('recommended', 'accepted', 'disregarded', 'superseded', 'completed')),
    plan                jsonb       not null,
    active_plan         jsonb,
    run_id              uuid        unique references runningtracker.runs(id) on delete set null,
    outcome             jsonb,
    created_at          timestamptz not null default now(),
    decided_at          timestamptz,
    check (status not in ('accepted', 'completed') or active_plan is not null),
    check (run_id is null or status in ('accepted', 'completed'))
);
create index if not exists ix_coach_plans_status_created on runningtracker.coach_plans(status, created_at desc);

-- Athlete profile: one row per key. basis 'measured' = deterministic server computation (confidence NULL); basis 'inferred' = AI statement
-- that passed validation (confidence required, capped by the number of runs, invariant PROF1). The key sets are declared once in
-- 10_scaffolding.json (backend/config.py COACH_MEASURED_KEYS / COACH_INFERRED_KEYS) and enforced in code, not here.
create table if not exists runningtracker.coach_profile_items (
    key        text             primary key check (char_length(key) between 1 and 40),
    basis      text             not null check (basis in ('measured', 'inferred')),
    value_text text             not null check (char_length(value_text) between 1 and 200),
    value_num  double precision,
    unit       text             check (unit is null or char_length(unit) <= 12),
    confidence double precision check (confidence is null or (confidence >= 0 and confidence <= 1)),
    n_runs     integer          not null check (n_runs >= 0),
    updated_at timestamptz      not null default now(),
    check ((basis = 'measured' and confidence is null) or (basis = 'inferred' and confidence is not null))
);

commit;
