-- ============================================================================
-- Migration 012 : explanatory mode + onboarded flag
-- - explanatory_mode : quand actif, les LLM explicitent en langage simple chaque
--   ratio / concept financier (cible : débutants & non-initiés).
-- - onboarded : flag permettant de déclencher le tour guidé à la 1ère connexion.
-- ============================================================================

ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS explanatory_mode BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS onboarded BOOLEAN NOT NULL DEFAULT FALSE;
