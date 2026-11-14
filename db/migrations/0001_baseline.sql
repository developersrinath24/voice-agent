-- Baseline schema, written to match the live Supabase project.
-- As of 14 Nov 2026 this schema already exists, so every statement below is a
-- no-op there. The file exists so the schema is reproducible, reviewable and
-- versioned in git (`supabase db pull` can regenerate it once the CLI is set up).
--
-- Anything the live database might be missing (checks, indexes, RLS) is worth
-- confirming in the dashboard; the definitions here are the intended state.

-- ---------------------------------------------------------------------------
-- sessions: one row per conversation
-- ---------------------------------------------------------------------------
create table if not exists public.sessions (
    id          uuid primary key default gen_random_uuid(),
    status      text not null default 'active' check (status in ('active', 'ended')),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
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
    created_at  timestamptz not null default now()
);

create index if not exists messages_session_created_idx
    on public.messages (session_id, created_at);

-- ---------------------------------------------------------------------------
-- appointments: booking requests captured during a conversation
-- Not used by the code yet; the booking tool in the LLM phase writes to it.
-- session_id is NOT NULL, while patient_name and requested_date are nullable —
-- a request can be captured in stages and completed later in the same session.
-- ---------------------------------------------------------------------------
create table if not exists public.appointments (
    id              uuid primary key default gen_random_uuid(),
    session_id      uuid not null references public.sessions (id) on delete cascade,
    patient_name    text,
    requested_date  date,
    status          text not null default 'requested',
    created_at      timestamptz not null default now()
);

create index if not exists appointments_requested_date_idx
    on public.appointments (requested_date);

-- ---------------------------------------------------------------------------
-- Row level security
-- Enabled with no policies: the anon/public key can read nothing. The FastAPI
-- backend uses the service/secret key, which bypasses RLS. Add explicit
-- policies here if the Next.js app ever talks to Supabase directly.
-- ---------------------------------------------------------------------------
alter table public.sessions enable row level security;
alter table public.messages enable row level security;
alter table public.appointments enable row level security;
