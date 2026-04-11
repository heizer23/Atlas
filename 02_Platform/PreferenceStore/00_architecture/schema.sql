-- PreferenceStore schema
-- Owner: 02_Platform/PreferenceStore
-- Managed by: app/database.py init_schema() (idempotent)

create schema if not exists preferences;

create table if not exists preferences.preferences (
    scope       text        not null,
    key         text        not null,
    value_json  jsonb       not null,
    updated_at  timestamptz not null default now(),
    constraint preferences_pkey primary key (scope, key),
    constraint preferences_scope_nonempty check (length(trim(scope)) > 0),
    constraint preferences_key_nonempty   check (length(trim(key))   > 0)
);

create index if not exists ix_preferences_scope
    on preferences.preferences (scope);
