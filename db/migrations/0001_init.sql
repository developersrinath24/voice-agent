-- Initial schema for conversation storage.
-- Run this in the Supabase SQL editor (or with `supabase db push`).

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- sessions: one row per conversation (web chat or voice call)
-- ---------------------------------------------------------------------------
create table if not exists public.sessions (
    id          uuid primary key default gen_random_uuid(),
    channel     text not null default 'web' check (channel in ('web', 'voice')),
    status      text not null default 'active' check (status in ('active', 'ended')),
    metadata    jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    ended_at    timestamptz
);

create index if not exists sessions_created_at_idx
    on public.sessions (created_at desc);

-- ---------------------------------------------------------------------------
-- messages: every turn in a session, in order
-- ---------------------------------------------------------------------------
create table if not exists public.messages (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid not null references public.sessions (id) on delete cascade,
    role        text not null check (role in ('user', 'assistant', 'system', 'tool')),
    content     text not null,
    model       text,
    latency_ms  integer,
    metadata    jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

create index if not exists messages_session_created_idx
    on public.messages (session_id, created_at);

-- ---------------------------------------------------------------------------
-- keep sessions.updated_at honest
-- ---------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists sessions_touch_updated_at on public.sessions;
create trigger sessions_touch_updated_at
    before update on public.sessions
    for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Row level security
-- Enabled with no policies: the anon/public key can read nothing. The FastAPI
-- backend uses the service_role key, which bypasses RLS. Add explicit policies
-- here if the Next.js app ever talks to Supabase directly.
-- ---------------------------------------------------------------------------
alter table public.sessions enable row level security;
alter table public.messages enable row level security;
