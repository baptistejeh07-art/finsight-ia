-- ============================================================================
-- Migration 020 : attribution signup
-- Pop-up sur clic CTA "S'abonner" qui demande comment l'utilisateur a entendu
-- parler de FinSight. Permet de mesurer ROI par canal d'acquisition.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.signup_attribution (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  source TEXT NOT NULL,         -- google / linkedin / reddit / friend / press / other / x / tiktok / podcast / search
  source_detail TEXT,           -- Texte libre (ex: "podcast Generation Do It Yourself")
  plan_clicked TEXT,            -- decouverte / essentiel / pro / equipe / enterprise / api
  anon_session_id TEXT,         -- Lié au tracker visites pour relier visiteur → signup
  user_agent TEXT,
  referrer TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signup_attribution_source
  ON public.signup_attribution(source, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signup_attribution_user
  ON public.signup_attribution(user_id) WHERE user_id IS NOT NULL;

ALTER TABLE public.signup_attribution ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Anyone can insert attribution" ON public.signup_attribution;
CREATE POLICY "Anyone can insert attribution" ON public.signup_attribution FOR INSERT WITH CHECK (TRUE);

-- Vue agrégée admin : conversion par source
CREATE OR REPLACE VIEW public.signup_attribution_stats_v AS
SELECT
  source,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS week,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') AS month,
  COUNT(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL) AS converted
FROM public.signup_attribution
GROUP BY source
ORDER BY total DESC;
