begin;

create schema if not exists claudeconsole;

create table if not exists claudeconsole.sessions (
    id                 uuid primary key default gen_random_uuid(),
    claude_session_id  text,
    permission_mode    text not null check (permission_mode in ('plan', 'acceptEdits', 'bypassPermissions')),
    status             text not null default 'active' check (status in ('active', 'ended')),
    created_at         timestamptz not null default now(),
    ended_at           timestamptz
);

create table if not exists claudeconsole.messages (
    id           uuid primary key default gen_random_uuid(),
    session_id   uuid not null references claudeconsole.sessions(id) on delete cascade,
    role         text not null check (role in ('user', 'assistant', 'tool')),
    content      text,
    raw_event    jsonb,
    created_at   timestamptz not null default now()
);

create index if not exists ix_messages_session_created on claudeconsole.messages(session_id, created_at);

commit;
