-- ============================================================================
-- Migration 022 : batch jobs (analyse de N tickers en parallèle)
-- "Analyse tout le CAC 40 en 1 clic" → 40 sous-jobs société + page de
-- progression agrégée + ZIP final des livrables.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.batch_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  label TEXT,                    -- ex: "Watchlist Luxe européen", "CAC 40"
  total INTEGER NOT NULL,
  done INTEGER DEFAULT 0,
  failed INTEGER DEFAULT 0,
  job_ids JSONB DEFAULT '[]'::jsonb,  -- liste des sous-job_ids créés dans jobstore
  status TEXT DEFAULT 'running' CHECK (status IN ('running','done','partial','error')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_user ON public.batch_jobs(user_id, created_at DESC);

ALTER TABLE public.batch_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bj_select_own" ON public.batch_jobs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "bj_insert_own" ON public.batch_jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "bj_update_own" ON public.batch_jobs FOR UPDATE USING (auth.uid() = user_id);
