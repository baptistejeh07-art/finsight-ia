-- ============================================================================
-- Migration 011 : historique renommable + favoris
-- Ajoute display_name (label custom user) et is_favorite (étoile) à
-- analyses_history. Permet UX "Renommer" + filtre "Favoris" dans la sidebar.
-- ============================================================================

ALTER TABLE public.analyses_history
  ADD COLUMN IF NOT EXISTS display_name TEXT,
  ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE;

-- Index partiel sur favoris pour filtrage rapide (un user a peu de favoris)
CREATE INDEX IF NOT EXISTS idx_analyses_history_user_fav
  ON public.analyses_history(user_id, created_at DESC)
  WHERE is_favorite = TRUE;

-- Policy update : l'user peut modifier (rename / toggle fav) son propre historique
DROP POLICY IF EXISTS "Users can update their own history" ON public.analyses_history;
CREATE POLICY "Users can update their own history"
  ON public.analyses_history FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
