-- ============================================================================
-- Migration 015 : analysis_alerts
-- Système de rappels post-analyse. L'user configure un trigger (prix cible
-- atteint, earnings date, dividende, news…) et reçoit une notification
-- (email + push browser) quand la condition est satisfaite.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.analysis_alerts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  history_id    UUID REFERENCES public.analyses_history(id) ON DELETE SET NULL,
  ticker        TEXT,                                   -- ticker yfinance si applicable
  trigger_type  TEXT NOT NULL CHECK (trigger_type IN (
                  'price_target', 'earnings_date', 'dividend_exdate',
                  'news', 'custom_date', 'quarterly_results'
                )),
  trigger_value JSONB NOT NULL DEFAULT '{}'::jsonb,    -- {target: 180.0, direction: 'above'} ou {date: '2026-05-01'}
  channels      TEXT[] NOT NULL DEFAULT ARRAY['email'], -- ['email', 'push']
  label         TEXT,                                   -- titre lisible ("AAPL atteint 200$")
  enabled       BOOLEAN NOT NULL DEFAULT TRUE,
  last_checked  TIMESTAMPTZ,
  fired_at      TIMESTAMPTZ,                            -- NULL = pas encore déclenché
  fired_payload JSONB,                                  -- snapshot du trigger au moment du fire
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_user ON public.analysis_alerts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON public.analysis_alerts(enabled, fired_at)
  WHERE enabled = TRUE AND fired_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON public.analysis_alerts(ticker)
  WHERE ticker IS NOT NULL AND enabled = TRUE AND fired_at IS NULL;

-- RLS
ALTER TABLE public.analysis_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "owners can view their alerts" ON public.analysis_alerts;
CREATE POLICY "owners can view their alerts"
  ON public.analysis_alerts FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "owners can insert their alerts" ON public.analysis_alerts;
CREATE POLICY "owners can insert their alerts"
  ON public.analysis_alerts FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "owners can update their alerts" ON public.analysis_alerts;
CREATE POLICY "owners can update their alerts"
  ON public.analysis_alerts FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "owners can delete their alerts" ON public.analysis_alerts;
CREATE POLICY "owners can delete their alerts"
  ON public.analysis_alerts FOR DELETE USING (auth.uid() = user_id);

-- Table pour stocker les subscriptions Web Push (endpoint + p256dh + auth)
CREATE TABLE IF NOT EXISTS public.push_subscriptions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  endpoint    TEXT NOT NULL,
  p256dh      TEXT NOT NULL,
  auth_key    TEXT NOT NULL,
  user_agent  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, endpoint)
);

CREATE INDEX IF NOT EXISTS idx_push_user ON public.push_subscriptions(user_id);

ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "owners can manage their push subs" ON public.push_subscriptions;
CREATE POLICY "owners can manage their push subs"
  ON public.push_subscriptions FOR ALL
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Trigger updated_at
CREATE OR REPLACE FUNCTION public.handle_alerts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_alerts_updated_at ON public.analysis_alerts;
CREATE TRIGGER trg_alerts_updated_at
  BEFORE UPDATE ON public.analysis_alerts
  FOR EACH ROW EXECUTE FUNCTION public.handle_alerts_updated_at();
