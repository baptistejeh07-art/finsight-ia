-- ============================================================================
-- Migration 018 : tracking anonyme visites site vitrine
-- Permet à Baptiste (admin) de voir les visiteurs NON connectés sur le site
-- marketing (/, /methodologie, /roadmap, etc.).
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.vitrine_visits (
  id BIGSERIAL PRIMARY KEY,
  -- Chemin visité (ex: '/', '/methodologie', '/roadmap')
  path TEXT NOT NULL,
  -- Referrer (ex: 'https://www.google.com/', 'https://linkedin.com/...')
  referrer TEXT,
  -- User-agent pour analytics device
  user_agent TEXT,
  -- ID session anonyme (cookie localStorage côté frontend, 1 par navigateur)
  -- Permet de dédupliquer "un visiteur a cliqué sur 5 pages" comme UN visiteur
  anon_session_id TEXT,
  -- Pays estimé via Accept-Language ou header Cloudflare
  country TEXT,
  -- User connecté : user_id. Sinon NULL (visiteur anonyme).
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes pour agrégation rapide dans le dashboard admin
CREATE INDEX IF NOT EXISTS idx_vitrine_visits_created_at
  ON public.vitrine_visits(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vitrine_visits_session
  ON public.vitrine_visits(anon_session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vitrine_visits_path
  ON public.vitrine_visits(path, created_at DESC);

-- RLS : personne ne peut lire (admin seulement via service_role dans le backend).
-- Anyone peut insert (visiteur anonyme → sinon on ne pourrait rien tracker).
ALTER TABLE public.vitrine_visits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can insert a vitrine visit"
  ON public.vitrine_visits FOR INSERT
  WITH CHECK (TRUE);

-- Pas de policy SELECT → seul le backend service_role peut lire.

-- Vue agrégée pour le dashboard admin
CREATE OR REPLACE VIEW public.vitrine_stats_v AS
SELECT
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 day')          AS visits_day,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days')         AS visits_week,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days')        AS visits_month,
  COUNT(DISTINCT anon_session_id) FILTER (WHERE created_at > NOW() - INTERVAL '1 day')   AS unique_day,
  COUNT(DISTINCT anon_session_id) FILTER (WHERE created_at > NOW() - INTERVAL '7 days')  AS unique_week,
  COUNT(DISTINCT anon_session_id) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') AS unique_month
FROM public.vitrine_visits
WHERE user_id IS NULL;
