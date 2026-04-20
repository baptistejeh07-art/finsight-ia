-- Migration 008 : flag admin + ban soft-delete.
-- - is_admin : pour Baptiste (et futurs admins) — bypass quotas + accès /admin
-- - banned_at : timestamp de bannissement (soft-delete : le compte existe
--   encore mais ne peut plus lancer d'analyse). banned_reason optionnel pour
--   tracer la raison (spam, abus, etc.).

alter table public.user_preferences
  add column if not exists is_admin boolean default false not null;

alter table public.user_preferences
  add column if not exists banned_at timestamptz;

alter table public.user_preferences
  add column if not exists banned_reason text;

comment on column public.user_preferences.is_admin
  is 'True = accès panneau /admin + bypass quotas + toutes features sans abonnement';
comment on column public.user_preferences.banned_at
  is 'Soft-delete : si non-null, l utilisateur ne peut plus lancer d analyse';
comment on column public.user_preferences.banned_reason
  is 'Raison du bannissement (interne, pour audit)';

-- Index partiel pour retrouver rapidement les bans actifs
create index if not exists idx_user_preferences_banned
  on public.user_preferences (banned_at)
  where banned_at is not null;

-- Flag Baptiste comme admin (une seule fois, idempotent)
-- L'email user@auth.users table → jointure pour trouver son user_id
do $$
declare
  v_uid uuid;
begin
  select id into v_uid from auth.users where email = 'baptiste.jeh07@gmail.com' limit 1;
  if v_uid is not null then
    -- Upsert : créer la row si absente, sinon set is_admin=true
    insert into public.user_preferences (user_id, is_admin)
    values (v_uid, true)
    on conflict (user_id) do update set is_admin = true;
  end if;
end $$;
