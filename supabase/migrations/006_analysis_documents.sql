-- Migration 006 : Documents uploadés par l'utilisateur pour enrichir une analyse.
-- Permet à l'user de joindre PDF/XLSX/contrats à une analyse existante,
-- extraction Gemini Vision (compte de résultat, bilan) ou parsing XLSX déterministe.
--
-- Liens : analyses_history.id (UUID) ← analysis_documents.analysis_id
-- RLS : un user ne voit/modifie que ses propres documents.

create extension if not exists "pgcrypto";

create table if not exists public.analysis_documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  analysis_id text,
  -- analysis_id = job_id du backend (UUID stringifié dans l'URL /resultats/[id])
  -- pas de FK stricte car les analyses ne sont pas toujours persistées en BDD
  -- (notamment pour les invités). Peut être null si upload "libre" sans analyse.
  filename text not null,
  mime_type text,
  size_bytes bigint,
  file_hash text,                       -- SHA256 pour cache + déduplication
  storage_path text not null,           -- path dans bucket 'analysis_documents'
  type_detected text,                   -- 'compte_resultat' | 'bilan' | 'contrat' | 'autre' | 'xlsx'
  status text not null default 'uploaded',
  -- 'uploaded' | 'extracting' | 'extracted' | 'validated' | 'error'
  extracted_data jsonb,                 -- résultat structuré du LLM/parser
  extraction_error text,
  validated boolean default false,      -- true quand user a confirmé les données
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists analysis_documents_user_idx
  on public.analysis_documents(user_id, created_at desc);
create index if not exists analysis_documents_analysis_idx
  on public.analysis_documents(user_id, analysis_id) where analysis_id is not null;
create index if not exists analysis_documents_hash_idx
  on public.analysis_documents(user_id, file_hash) where file_hash is not null;

-- updated_at auto
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists analysis_documents_touch on public.analysis_documents;
create trigger analysis_documents_touch
  before update on public.analysis_documents
  for each row execute function public.touch_updated_at();

-- RLS
alter table public.analysis_documents enable row level security;

drop policy if exists "documents_select_own" on public.analysis_documents;
create policy "documents_select_own"
  on public.analysis_documents for select
  using (auth.uid() = user_id);

drop policy if exists "documents_insert_own" on public.analysis_documents;
create policy "documents_insert_own"
  on public.analysis_documents for insert
  with check (auth.uid() = user_id);

drop policy if exists "documents_update_own" on public.analysis_documents;
create policy "documents_update_own"
  on public.analysis_documents for update
  using (auth.uid() = user_id);

drop policy if exists "documents_delete_own" on public.analysis_documents;
create policy "documents_delete_own"
  on public.analysis_documents for delete
  using (auth.uid() = user_id);

-- Bucket Storage privé pour les fichiers
-- (à exécuter via Dashboard Supabase si ce SQL n'a pas les droits storage admin)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'analysis_documents',
  'analysis_documents',
  false,                 -- privé
  20971520,              -- 20 Mo
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'image/png',
    'image/jpeg',
    'image/webp',
    'text/plain',
    'text/csv'
  ]
)
on conflict (id) do update set
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types,
  public = excluded.public;

-- Storage RLS : user accède qu'aux fichiers du dossier {user_id}/...
drop policy if exists "documents_storage_select_own" on storage.objects;
create policy "documents_storage_select_own"
  on storage.objects for select
  using (
    bucket_id = 'analysis_documents'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

drop policy if exists "documents_storage_insert_own" on storage.objects;
create policy "documents_storage_insert_own"
  on storage.objects for insert
  with check (
    bucket_id = 'analysis_documents'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

drop policy if exists "documents_storage_delete_own" on storage.objects;
create policy "documents_storage_delete_own"
  on storage.objects for delete
  using (
    bucket_id = 'analysis_documents'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
