-- ============================================================================
-- Migration 021 : watchlists utilisateur
-- Permet à l'utilisateur de créer des listes thématiques de tickers à suivre
-- (ex: "Luxe européen", "Cloud US"). Utilisable pour batch analyses + alertes.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  color TEXT DEFAULT 'navy',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_watchlists_user ON public.watchlists(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.watchlist_tickers (
  id BIGSERIAL PRIMARY KEY,
  watchlist_id UUID NOT NULL REFERENCES public.watchlists(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  company_name TEXT,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  position INTEGER DEFAULT 0,
  UNIQUE(watchlist_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_wl_tickers_wl ON public.watchlist_tickers(watchlist_id, position);

-- RLS : seul l'owner accède
ALTER TABLE public.watchlists ENABLE ROW LEVEL SECURITY;
CREATE POLICY "wl_select_own" ON public.watchlists FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "wl_insert_own" ON public.watchlists FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "wl_update_own" ON public.watchlists FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "wl_delete_own" ON public.watchlists FOR DELETE USING (auth.uid() = user_id);

ALTER TABLE public.watchlist_tickers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "wlt_select_via_wl" ON public.watchlist_tickers FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.watchlists w WHERE w.id = watchlist_id AND w.user_id = auth.uid())
);
CREATE POLICY "wlt_insert_via_wl" ON public.watchlist_tickers FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.watchlists w WHERE w.id = watchlist_id AND w.user_id = auth.uid())
);
CREATE POLICY "wlt_delete_via_wl" ON public.watchlist_tickers FOR DELETE USING (
  EXISTS (SELECT 1 FROM public.watchlists w WHERE w.id = watchlist_id AND w.user_id = auth.uid())
);
