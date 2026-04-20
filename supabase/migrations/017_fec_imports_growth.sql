-- ============================================================================
-- Migration 017 : FEC imports + growth loop LinkedIn shares
-- ============================================================================

-- === FEC imports (comptabilité FR) ===========================================
CREATE TABLE IF NOT EXISTS public.fec_imports (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  siren        TEXT,
  filename     TEXT NOT NULL,
  size_bytes   INT,
  num_lines    INT,
  exercice     TEXT,                -- ex: "2024" ou "2024-2025"
  storage_path TEXT,                -- Supabase Storage path (private bucket)
  parsed_summary JSONB,             -- {revenue, ebitda, net_income, total_assets, ...}
  status       TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'parsing', 'parsed', 'error')),
  error        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fec_user ON public.fec_imports(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fec_siren ON public.fec_imports(siren) WHERE siren IS NOT NULL;

ALTER TABLE public.fec_imports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "owners manage their FEC" ON public.fec_imports;
CREATE POLICY "owners manage their FEC" ON public.fec_imports FOR ALL
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- === Growth loop LinkedIn shares ============================================
CREATE TABLE IF NOT EXISTS public.user_shares_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  share_token  TEXT,                            -- ref vers analysis_shares.token si applicable
  platform     TEXT NOT NULL CHECK (platform IN ('linkedin', 'twitter', 'reddit', 'facebook', 'email', 'copy')),
  linkedin_post_url TEXT,                       -- URL du post LinkedIn user (pour vérification manuelle)
  verified     BOOLEAN NOT NULL DEFAULT FALSE,  -- admin valide après check
  credits_awarded INT NOT NULL DEFAULT 0,       -- +3 analyses par batch de 10 shares
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  verified_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_shares_log_user ON public.user_shares_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shares_log_verified ON public.user_shares_log(user_id, verified, credits_awarded);

ALTER TABLE public.user_shares_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "owners view their shares log" ON public.user_shares_log;
CREATE POLICY "owners view their shares log" ON public.user_shares_log FOR SELECT
  USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "owners insert their shares log" ON public.user_shares_log;
CREATE POLICY "owners insert their shares log" ON public.user_shares_log FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Crédits analyses bonus dans user_preferences
ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS bonus_analyses_credits INT NOT NULL DEFAULT 0;
