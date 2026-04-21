-- ============================================================================
-- Migration 024 : commentaires collaboratifs sur analyses
-- Permet à un utilisateur de commenter une analyse (ou un bloc précis) et
-- d'ouvrir un fil de discussion. Visibilité : tout le monde qui a accès au
-- job (par invitation/share) peut lire ; insert si authed = own user_id.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.analysis_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id TEXT NOT NULL,                      -- analyse cible
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  user_email TEXT,                           -- snapshot pour affichage si user supprimé
  block_id TEXT,                             -- ex: "synthese", "valo", "ratios" — null = commentaire global
  body TEXT NOT NULL CHECK (length(body) > 0 AND length(body) <= 2000),
  parent_id UUID REFERENCES public.analysis_comments(id) ON DELETE CASCADE,
  resolved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_job ON public.analysis_comments(job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comments_user ON public.analysis_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_block ON public.analysis_comments(job_id, block_id, created_at);

ALTER TABLE public.analysis_comments ENABLE ROW LEVEL SECURITY;

-- SELECT : open (TRUE) car la visibilité est contrôlée par l'accès à l'analyse
-- elle-même (analyses_history RLS). Pour V2 : restreindre aux owners + invités.
CREATE POLICY "comments_select_via_share" ON public.analysis_comments FOR SELECT USING (TRUE);

CREATE POLICY "comments_insert_authed" ON public.analysis_comments FOR INSERT
  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "comments_update_own" ON public.analysis_comments FOR UPDATE
  USING (auth.uid() = user_id);
CREATE POLICY "comments_delete_own" ON public.analysis_comments FOR DELETE
  USING (auth.uid() = user_id);
