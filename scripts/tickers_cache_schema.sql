-- =============================================================================
-- FinSight IA — Table tickers_cache
-- Coller dans Supabase > SQL Editor > Run
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.tickers_cache (
    ticker            TEXT        PRIMARY KEY,
    company_name      TEXT,
    sector            TEXT,
    exchange          TEXT,
    currency          TEXT,
    income_statement  JSONB       DEFAULT '{}'::jsonb,
    balance_sheet     JSONB       DEFAULT '{}'::jsonb,
    cash_flow         JSONB       DEFAULT '{}'::jsonb,
    last_updated      TIMESTAMPTZ,
    next_earnings     DATE
);

-- Index pour les requetes de refresh
CREATE INDEX IF NOT EXISTS idx_tc_next_earnings
    ON public.tickers_cache (next_earnings);

CREATE INDEX IF NOT EXISTS idx_tc_last_updated
    ON public.tickers_cache (last_updated);

-- RLS : seul le service role peut ecrire
ALTER TABLE public.tickers_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_full_access" ON public.tickers_cache
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Lecture publique (optionnel — commenter si pas souhaite)
CREATE POLICY "anon_read" ON public.tickers_cache
    FOR SELECT
    USING (true);
