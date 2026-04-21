-- ============================================================================
-- Migration 019 : traçage précis des analyses (observabilité niveau 3)
-- Stocke chaque step d'une analyse (agent LangGraph, appel LLM, fetch data,
-- writer, cache hit) avec durée, tokens, coût estimé, erreurs.
-- Permet profiling sans approximation + SSE temps réel.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.analysis_traces (
  id BIGSERIAL PRIMARY KEY,

  -- Job parent (même job_id que dans jobstore Railway)
  job_id TEXT NOT NULL,
  -- Kind (societe/secteur/indice/pme/cmp_*) pour filtrage admin
  kind TEXT,
  -- Label utile (ex: "AAPL", "Healthcare / S&P 500")
  label TEXT,

  -- Niveau de step : root (job entier), node (node LangGraph), llm, fetch,
  -- writer, cache. Permet de rollup le temps par type.
  level TEXT NOT NULL CHECK (level IN ('root', 'node', 'llm', 'fetch', 'writer', 'cache', 'other')),
  -- Nom lisible (ex: "synthesis_node", "groq.llama-3.3", "yfinance.info AAPL",
  -- "pdf_writer.sector_description")
  step_name TEXT NOT NULL,
  -- Parent step pour hiérarchie (NULL si step racine)
  parent_id BIGINT REFERENCES public.analysis_traces(id) ON DELETE SET NULL,

  -- Provider (groq/mistral/cerebras/anthropic/gemini/yfinance/redis/supabase/internal)
  provider TEXT,
  -- Modèle précis (llama-3.3-70b-versatile, claude-haiku-4-5, etc.)
  model TEXT,

  -- Timestamps précis
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  duration_ms INTEGER,

  -- Inputs / outputs (peut être lourd, JSONB pour requêter dans Supabase)
  input_preview TEXT,      -- Preview truncated (500 chars)
  output_preview TEXT,     -- idem
  input_size INTEGER,      -- taille totale input en chars
  output_size INTEGER,     -- idem output

  -- Métriques LLM
  tokens_in INTEGER,
  tokens_out INTEGER,
  cost_usd NUMERIC(10, 6),

  -- Cache / fallback
  cache_hit BOOLEAN DEFAULT FALSE,
  fallback_level INTEGER DEFAULT 0,   -- 0 = primary, 1 = 1er fallback, etc.

  -- Erreur (si step failed)
  error_type TEXT,
  error_message TEXT,
  error_stack TEXT,

  -- Status final
  status TEXT DEFAULT 'ok' CHECK (status IN ('ok', 'error', 'timeout', 'skipped', 'cache_hit')),

  -- Métadonnées libres (ex: sector, temperature, max_tokens, ticker)
  metadata JSONB DEFAULT '{}'::jsonb
);

-- Index pour requêtes admin rapides
CREATE INDEX IF NOT EXISTS idx_analysis_traces_job
  ON public.analysis_traces(job_id, started_at);
CREATE INDEX IF NOT EXISTS idx_analysis_traces_level_started
  ON public.analysis_traces(level, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_traces_parent
  ON public.analysis_traces(parent_id)
  WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analysis_traces_status
  ON public.analysis_traces(status, started_at DESC)
  WHERE status != 'ok';
-- Pour dashboard "coûts agrégés"
CREATE INDEX IF NOT EXISTS idx_analysis_traces_cost
  ON public.analysis_traces(started_at DESC)
  WHERE cost_usd IS NOT NULL;

-- RLS : service_role only (admin backend). Pas d'accès utilisateur direct.
ALTER TABLE public.analysis_traces ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can insert traces"
  ON public.analysis_traces FOR INSERT
  WITH CHECK (TRUE);

CREATE POLICY "Service role can select traces"
  ON public.analysis_traces FOR SELECT
  USING (TRUE);

-- ============================================================================
-- Vue agrégée : résumé par job (pour page admin /traces)
-- ============================================================================
CREATE OR REPLACE VIEW public.analysis_traces_summary_v AS
SELECT
  t.job_id,
  MAX(t.kind) AS kind,
  MAX(t.label) AS label,
  MIN(t.started_at) AS started_at,
  MAX(t.finished_at) AS finished_at,
  EXTRACT(EPOCH FROM (MAX(t.finished_at) - MIN(t.started_at))) * 1000 AS total_ms,
  COUNT(*) AS n_steps,
  COUNT(*) FILTER (WHERE t.status = 'error') AS n_errors,
  COUNT(*) FILTER (WHERE t.level = 'llm') AS n_llm_calls,
  COUNT(*) FILTER (WHERE t.cache_hit = TRUE) AS n_cache_hits,
  SUM(t.duration_ms) FILTER (WHERE t.level = 'llm') AS llm_ms,
  SUM(t.duration_ms) FILTER (WHERE t.level = 'fetch') AS fetch_ms,
  SUM(t.duration_ms) FILTER (WHERE t.level = 'writer') AS writer_ms,
  SUM(t.tokens_in) AS total_tokens_in,
  SUM(t.tokens_out) AS total_tokens_out,
  ROUND(SUM(t.cost_usd)::numeric, 4) AS total_cost_usd
FROM public.analysis_traces t
GROUP BY t.job_id;
