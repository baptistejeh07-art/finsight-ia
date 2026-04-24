-- Migration 025 : table jobs_state pour persistance des analyses.
-- Règle le bug "Analyse introuvable. Lien expiré ou redémarrage serveur"
-- qui cassait tous les liens /resultats/[id] partagés à des prospects dès
-- qu'un redeploy Railway redémarrait le backend (_JOBS en mémoire purgé).
--
-- Le backend (backend/db.py::upsert_job_state) écrit ici à chaque changement
-- d'état (running → done → finished). Le frontend passe par /jobs/{id}
-- qui tente la mémoire puis tombe sur cette table en fallback.

CREATE TABLE IF NOT EXISTS jobs_state (
    job_id      uuid PRIMARY KEY,
    kind        text NOT NULL,
    status      text NOT NULL,
    progress    int  DEFAULT 0,
    user_id     text,
    label       text,
    created_at  timestamptz DEFAULT now(),
    started_at  timestamptz,
    finished_at timestamptz,
    result      jsonb,
    error       text
);

-- Index sur user_id pour retrouver rapidement les analyses d'un utilisateur
-- (listing /mes-analyses). Sans index, scan de la table entière.
CREATE INDEX IF NOT EXISTS idx_jobs_state_user_id
    ON jobs_state (user_id)
    WHERE user_id IS NOT NULL;

-- Index sur finished_at pour purger les jobs anciens (TTL 30 jours).
CREATE INDEX IF NOT EXISTS idx_jobs_state_finished_at
    ON jobs_state (finished_at)
    WHERE finished_at IS NOT NULL;

-- RLS désactivé : la table est uniquement écrite par le backend Railway
-- avec la service_role key. Le frontend n'y accède jamais directement, il
-- passe par l'API /jobs/{id} qui vérifie les droits (owner ou partagé).
ALTER TABLE jobs_state DISABLE ROW LEVEL SECURITY;

-- Politique de rétention : les jobs terminés depuis +30 jours peuvent être
-- purgés par un cron Supabase. À activer quand le volume le justifiera.
-- DELETE FROM jobs_state WHERE finished_at < now() - interval '30 days';

COMMENT ON TABLE jobs_state IS
    'Persistance des états de jobs (analyses) pour survivre aux redeploys Railway.';
