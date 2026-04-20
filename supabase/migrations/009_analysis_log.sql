-- Migration 009 : dataset analyses anonymisé.
--
-- Objectif : enregistrer chaque analyse faite sur FinSight (société/secteur/
-- indice/PME) avec ses résultats clés, pour :
--   1. Mesurer l'usage plateforme (admin dashboard)
--   2. Construire un dataset "Trends" vendable à des hedge funds
--      (signal alternatif : quelles sociétés/secteurs sont analysés,
--       quelles reco dominent, etc.)
--
-- CRITIQUE : aucune trace de l'utilisateur (anonymisé complètement).
-- Pas de user_id, pas d'email, pas de hash de session.
-- Seul le timestamp + metadata technique de l'analyse.

create table if not exists public.analysis_log (
  id bigserial primary key,
  created_at timestamptz not null default now(),

  -- Type d'analyse
  kind text not null check (kind in ('societe', 'secteur', 'indice', 'pme', 'cmp_societe', 'cmp_secteur', 'cmp_indice')),

  -- Identifiant société/secteur analysé
  ticker text,                   -- AAPL, MC.PA, etc. NULL pour secteur/indice "Technology"
  company_name text,             -- Apple Inc., LVMH, etc.
  sector text,                   -- Technology, Healthcare, etc. (libellé EN yfinance)
  industry text,                 -- sous-secteur détaillé (ex: Consumer Electronics)
  universe text,                 -- S&P 500 / CAC 40 / DAX / FTSE 100 / CUSTOM
  country text,                  -- FR / US / UK / DE / JP / autres (dérivé suffixe ticker)

  -- Caractéristiques société
  market_cap_bucket text         -- nano / micro / small / mid / large / mega
    check (market_cap_bucket in ('nano', 'micro', 'small', 'mid', 'large', 'mega') or market_cap_bucket is null),
  market_cap_usd_bn numeric,     -- en milliards de dollars pour plus de précision

  -- Résultats clés de l'analyse
  score_finsight numeric,        -- 0-100
  recommendation text,           -- BUY / HOLD / SELL
  conviction numeric,            -- 0-1
  target_price_base numeric,     -- prix cible base
  target_upside_pct numeric,     -- (target_base - current_price) / current_price * 100

  -- Métadonnées techniques
  language text default 'fr'     -- langue de l'analyse (fr/en/es/de/it/pt)
    check (language in ('fr', 'en', 'es', 'de', 'it', 'pt') or language is null),
  currency text default 'EUR'    -- devise d'affichage
    check (currency in ('EUR', 'USD', 'GBP', 'CHF', 'JPY', 'CAD') or currency is null),
  duration_ms integer,           -- durée totale pipeline en ms

  -- Drapeaux qualité
  llm_fallback_used boolean default false,  -- true si fallback deterministe utilisé
  data_quality text              -- 'full' | 'partial' | 'stale'
    check (data_quality in ('full', 'partial', 'stale') or data_quality is null)
);

-- Index pour query business
create index if not exists idx_analysis_log_created_at
  on public.analysis_log (created_at desc);

create index if not exists idx_analysis_log_kind
  on public.analysis_log (kind);

create index if not exists idx_analysis_log_sector
  on public.analysis_log (sector)
  where sector is not null;

create index if not exists idx_analysis_log_ticker
  on public.analysis_log (ticker)
  where ticker is not null;

create index if not exists idx_analysis_log_recommendation
  on public.analysis_log (recommendation)
  where recommendation is not null;

-- RLS : personne ne peut lire ou écrire côté client.
-- Seule l'écriture via service role (backend) est autorisée.
alter table public.analysis_log enable row level security;

-- Policy : seuls les admins peuvent lire (pour admin dashboard).
create policy "analysis_log_admin_read" on public.analysis_log
  for select
  to authenticated
  using (
    exists (
      select 1 from public.user_preferences
      where user_id = auth.uid() and is_admin = true
    )
  );

-- Aucune policy d'insert côté client : écriture via service_role key seulement.

comment on table public.analysis_log is
  'Dataset anonymisé de toutes les analyses lancées sur FinSight. '
  'Aucune trace utilisateur. Base du futur dataset "FinSight Trends" vendable.';

comment on column public.analysis_log.country is
  'Pays dérivé du suffixe ticker : .PA=FR .L=UK .DE=DE .AS=NL etc. "US" si pas de suffixe.';
