-- Migration : table analyses_history
-- À exécuter dans Supabase SQL Editor (one-shot)
-- https://supabase.com/dashboard/project/<PROJECT>/sql/new

CREATE TABLE IF NOT EXISTS analyses_history (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL,
    kind         text NOT NULL,         -- 'societe' | 'secteur' | 'indice' | 'cmp_*'
    label        text,                  -- libellé affiché : ticker, nom secteur, indice
    ticker       text,                  -- ticker primaire si applicable
    status       text NOT NULL DEFAULT 'done',
    created_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    files        jsonb,                 -- {pdf, pptx, xlsx} : chemins ou URLs
    meta         jsonb                  -- libre (durée, devise, scope, etc.)
);

CREATE INDEX IF NOT EXISTS idx_analyses_history_user_created
    ON analyses_history (user_id, created_at DESC);

-- RLS désactivée car le backend attaque via service_role (server-side).
-- Si vous voulez activer RLS pour un client direct, ajouter :
--   ALTER TABLE analyses_history ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY analyses_history_owner_select ON analyses_history
--       FOR SELECT USING (auth.uid() = user_id);
