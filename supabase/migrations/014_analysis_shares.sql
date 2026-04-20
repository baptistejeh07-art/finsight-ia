-- ============================================================================
-- Migration 014 : analysis_shares
-- Permet à un user de partager son analyse via une URL publique read-only.
-- Token random base62 ; expiration optionnelle ; tracking views_count.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.analysis_shares (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token       TEXT UNIQUE NOT NULL,
  history_id  UUID NOT NULL REFERENCES public.analyses_history(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  views_count INT NOT NULL DEFAULT 0,
  expires_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_analysis_shares_token ON public.analysis_shares(token);
CREATE INDEX IF NOT EXISTS idx_analysis_shares_user ON public.analysis_shares(user_id, created_at DESC);

-- RLS : owner peut tout, lecture publique uniquement via service_role (backend gère)
ALTER TABLE public.analysis_shares ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "owners can view their shares" ON public.analysis_shares;
CREATE POLICY "owners can view their shares"
  ON public.analysis_shares FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "owners can insert their shares" ON public.analysis_shares;
CREATE POLICY "owners can insert their shares"
  ON public.analysis_shares FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "owners can revoke their shares" ON public.analysis_shares;
CREATE POLICY "owners can revoke their shares"
  ON public.analysis_shares FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "owners can delete their shares" ON public.analysis_shares;
CREATE POLICY "owners can delete their shares"
  ON public.analysis_shares FOR DELETE
  USING (auth.uid() = user_id);
