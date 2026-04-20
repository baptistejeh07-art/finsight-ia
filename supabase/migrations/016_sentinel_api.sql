-- ============================================================================
-- Migration 016 : Sentinelle + API publique
-- ============================================================================

-- === Sentinelle : pipeline errors + data missing tracking ===================
CREATE TABLE IF NOT EXISTS public.pipeline_errors (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  severity     TEXT NOT NULL CHECK (severity IN ('info', 'warn', 'error', 'critical')),
  error_type   TEXT NOT NULL,                -- ex: 'missing_data', 'llm_fail', 'writer_crash'
  node         TEXT,                          -- fetch / quant / synthesis / output / writer
  ticker       TEXT,
  kind         TEXT,                          -- societe / secteur / indice / pme / comparatif
  field_path   TEXT,                          -- ex: 'synthesis.conviction' ou 'raw_data.years.2024.capex'
  message      TEXT NOT NULL,
  stack        TEXT,
  context      JSONB NOT NULL DEFAULT '{}'::jsonb,
  user_id      UUID,
  job_id       TEXT,
  wakeup_fired BOOLEAN NOT NULL DEFAULT FALSE,
  wakeup_reason TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_errors_created ON public.pipeline_errors(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_errors_severity ON public.pipeline_errors(severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_errors_type ON public.pipeline_errors(error_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_errors_ticker ON public.pipeline_errors(ticker) WHERE ticker IS NOT NULL;

ALTER TABLE public.pipeline_errors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "admin read errors" ON public.pipeline_errors;
CREATE POLICY "admin read errors" ON public.pipeline_errors FOR SELECT
  USING (EXISTS (SELECT 1 FROM public.user_preferences p WHERE p.user_id = auth.uid() AND p.is_admin = TRUE));

-- === API publique : clés + usage ===========================================
CREATE TABLE IF NOT EXISTS public.api_keys (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  key_prefix   TEXT NOT NULL,                 -- 8 premiers chars visibles UI (fsk_ab12cd34...)
  key_hash     TEXT NOT NULL UNIQUE,          -- SHA256 de la clé complète
  name         TEXT NOT NULL,                 -- label user ('Prod backend', 'Test dev')
  rate_limit_per_min INT NOT NULL DEFAULT 30, -- req/min
  rate_limit_per_day INT NOT NULL DEFAULT 1000,
  last_used_at TIMESTAMPTZ,
  revoked_at   TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON public.api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON public.api_keys(user_id, created_at DESC);

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "owners can manage api_keys" ON public.api_keys;
CREATE POLICY "owners can manage api_keys" ON public.api_keys FOR ALL
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.api_usage (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key_id      UUID REFERENCES public.api_keys(id) ON DELETE CASCADE,
  user_id     UUID,
  endpoint    TEXT NOT NULL,
  method      TEXT NOT NULL DEFAULT 'POST',
  status_code INT,
  duration_ms INT,
  ip          TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_key ON public.api_usage(key_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_usage_user ON public.api_usage(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_usage_created ON public.api_usage(created_at DESC);

ALTER TABLE public.api_usage ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "owners can view their usage" ON public.api_usage;
CREATE POLICY "owners can view their usage" ON public.api_usage FOR SELECT
  USING (auth.uid() = user_id);
