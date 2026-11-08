-- RunningTracker Sprint01_RecordAndSync -- private application schema.
-- Runtime canonical path: 03_Application/RunningTracker/schema.sql (copy of this file; executed idempotently at startup).
-- Private tables: not a cross-application contract. Other components must never query schema `runningtracker`.
-- Time columns: run times (started_at, finished_at, pause stamps, sample_ts) are phone-reported UTC (persisted domain time);
-- created_at / expires_at / last_used_at / used_at / locked_at / failed_at / revoked_at are server time (now()).

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

-- Failed pair attempts (global, single-user system). Drives the lockout rule (see 10_architecture.json invariants).
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
