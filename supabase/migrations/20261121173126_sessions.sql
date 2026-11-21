-- Conversation state of the parent's interview: the scenario (answers so far) and the
-- assistant's message history. One row per browser session.
--
-- Access model: RLS is on and there are no policies. The publishable (anon) key can neither
-- read nor write this table. Only the backend does, with the secret key.

create table public.sessions (
  id uuid primary key,
  scenario jsonb not null default '{}'::jsonb,
  history jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.sessions enable row level security;
