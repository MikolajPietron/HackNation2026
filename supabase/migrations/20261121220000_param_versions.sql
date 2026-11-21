-- Versions of the legal parameters saved in the admin panel. The base version is the JSON file
-- in the repo (backend/params/); each row here is a full copy of the parameters with the
-- changed numbers, valid from `effective_from`. The engine uses the newest row whose date has
-- come, otherwise the base file.
--
-- Access model: RLS is on and there are no policies. Only the backend reads and writes this
-- table, with the secret key.

create table public.param_versions (
  id uuid primary key,
  version text not null,
  effective_from date not null,
  note text not null,
  params jsonb not null,
  created_at timestamptz not null default now()
);

create index param_versions_effective_from on public.param_versions (effective_from desc, created_at desc);

alter table public.param_versions enable row level security;
