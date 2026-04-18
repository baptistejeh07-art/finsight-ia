-- =============================================================================
-- FinSight IA — Phase 2 schemas (INACTIFS pour V1)
-- À exécuter UNIQUEMENT quand Baptiste active le pricing.
-- =============================================================================
--
-- Ces tables préparent :
--   1. Profils utilisateurs (extension auth.users de Supabase)
--   2. Quotas par mois (tracking d'usage par plan)
--   3. Souscriptions Stripe (abonnement actif + historique)
--
-- RLS : à activer plus tard avec policies (chaque user voit ses propres rows).
-- Pour V1, on désactive RLS car on attaque via service_role (server-side).
-- =============================================================================

-- ─── 1. PROFILES ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profiles (
    id          uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       text UNIQUE NOT NULL,
    full_name   text,
    plan        text NOT NULL DEFAULT 'decouverte'
        CHECK (plan IN ('decouverte', 'essentiel', 'pro', 'equipe', 'enterprise')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_profiles_plan ON profiles(plan);

-- Trigger : auto-créer une row profiles à chaque signup auth.users
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name')
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ─── 2. QUOTAS (compteurs mensuels par user et par type d'analyse) ──────────
CREATE TABLE IF NOT EXISTS quotas (
    user_id           uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    period_month      date NOT NULL,  -- 1er du mois (2026-04-01)
    count_societe     int NOT NULL DEFAULT 0,
    count_secteur     int NOT NULL DEFAULT 0,
    count_indice      int NOT NULL DEFAULT 0,
    count_comparatif  int NOT NULL DEFAULT 0,
    count_portrait    int NOT NULL DEFAULT 0,
    count_api         int NOT NULL DEFAULT 0,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, period_month)
);

CREATE INDEX IF NOT EXISTS idx_quotas_period ON quotas(period_month DESC);

-- Helper : incrémenter un compteur (upsert + +1 atomique)
CREATE OR REPLACE FUNCTION increment_quota(
    p_user_id uuid,
    p_kind text  -- 'societe' | 'secteur' | 'indice' | 'comparatif' | 'portrait' | 'api'
)
RETURNS int
LANGUAGE plpgsql
AS $$
DECLARE
    new_count int;
    col text := 'count_' || p_kind;
BEGIN
    EXECUTE format($f$
        INSERT INTO quotas (user_id, period_month, %1$I)
        VALUES ($1, date_trunc('month', current_date)::date, 1)
        ON CONFLICT (user_id, period_month)
        DO UPDATE SET %1$I = quotas.%1$I + 1, updated_at = now()
        RETURNING %1$I
    $f$, col)
    INTO new_count
    USING p_user_id;
    RETURN new_count;
END;
$$;


-- ─── 3. SUBSCRIPTIONS (historique Stripe) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    stripe_subscription_id text UNIQUE,
    stripe_customer_id   text,
    plan                 text NOT NULL,
    status               text NOT NULL  -- 'active' | 'canceled' | 'past_due' | 'incomplete'
        CHECK (status IN ('active', 'canceled', 'past_due', 'incomplete', 'trialing', 'unpaid')),
    current_period_start timestamptz,
    current_period_end   timestamptz,
    cancel_at_period_end boolean NOT NULL DEFAULT false,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status ON subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);

-- Vue : profile + subscription active (pour lookup rapide du plan en cours)
CREATE OR REPLACE VIEW profiles_with_active_sub AS
SELECT
    p.*,
    s.stripe_subscription_id,
    s.status AS subscription_status,
    s.current_period_end,
    s.cancel_at_period_end
FROM profiles p
LEFT JOIN subscriptions s ON s.user_id = p.id AND s.status = 'active';


-- ─── 4. PLAN LIMITS (référentiel statique des quotas par plan) ──────────────
CREATE TABLE IF NOT EXISTS plan_limits (
    plan           text PRIMARY KEY,
    societe_max    int NOT NULL,
    secteur_max    int NOT NULL,
    indice_max     int NOT NULL,
    comparatif_max int NOT NULL,
    portrait_max   int NOT NULL,
    api_max        int NOT NULL,
    price_eur      decimal(10,2) NOT NULL,
    description    text
);

INSERT INTO plan_limits (plan, societe_max, secteur_max, indice_max, comparatif_max, portrait_max, api_max, price_eur, description)
VALUES
    ('decouverte',  3,    1,    1,   1,   0,    0,    0.00,   'Plan gratuit pour découvrir FinSight'),
    ('essentiel',   20,   10,   5,   10,  0,    0,    34.99,  'Productivité quotidienne pour analystes'),
    ('pro',         20,   10,   5,   10,  8,    100,  44.99,  'Pro avec portraits + API'),
    ('equipe',      999,  999,  999, 999, 999,  10000, 199.00, 'Équipe (par siège, à partir de)'),
    ('enterprise',  999999, 999999, 999999, 999999, 999999, 999999, 299.00, 'Enterprise illimité')
ON CONFLICT (plan) DO UPDATE SET
    societe_max = EXCLUDED.societe_max,
    secteur_max = EXCLUDED.secteur_max,
    indice_max = EXCLUDED.indice_max,
    comparatif_max = EXCLUDED.comparatif_max,
    portrait_max = EXCLUDED.portrait_max,
    api_max = EXCLUDED.api_max,
    price_eur = EXCLUDED.price_eur,
    description = EXCLUDED.description;


-- ─── 5. STRIPE WEBHOOKS LOG (audit) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stripe_webhooks_log (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id     text UNIQUE NOT NULL,
    event_type   text NOT NULL,
    payload      jsonb NOT NULL,
    processed_at timestamptz,
    error        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stripe_webhooks_event_type ON stripe_webhooks_log(event_type);

-- =============================================================================
-- FIN MIGRATION 002 (Phase 2)
-- =============================================================================
