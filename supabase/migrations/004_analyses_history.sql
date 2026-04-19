-- ============================================================================
-- Migration 004 : analyses_history
-- Stocke les analyses que l'utilisateur a choisi de "Garder en mémoire".
-- Snapshot complet du payload (data + files) → rechargeable sans refaire
-- tourner le pipeline.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.analyses_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Identifiant du job original (pour URL /resultats/[id])
  job_id TEXT NOT NULL,
  -- Type d'analyse
  kind TEXT NOT NULL CHECK (kind IN ('societe', 'secteur', 'indice', 'comparatif', 'portrait')),
  -- Libellé affichable (ex: "AAPL", "Utilities / S&P 500", "DAX 40")
  label TEXT NOT NULL,
  -- Ticker principal (pour société/comparatif) ou null
  ticker TEXT,

  -- Snapshot du payload complet (result.data + result.files + elapsed_ms…)
  -- Note : peut être volumineux (~500 Ko par société). Supabase JSONB le gère.
  payload JSONB NOT NULL,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index : accès rapide par utilisateur trié par date décroissante
CREATE INDEX IF NOT EXISTS idx_analyses_history_user_created
  ON public.analyses_history(user_id, created_at DESC);

-- Index : évite les doublons (même job_id par user)
CREATE UNIQUE INDEX IF NOT EXISTS idx_analyses_history_user_job
  ON public.analyses_history(user_id, job_id);

-- === RLS ===
ALTER TABLE public.analyses_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own history"
  ON public.analyses_history FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own history"
  ON public.analyses_history FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own history"
  ON public.analyses_history FOR DELETE
  USING (auth.uid() = user_id);
