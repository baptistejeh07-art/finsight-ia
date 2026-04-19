-- ============================================================================
-- Migration 003 : user_preferences
-- Stocke les préférences utilisateur (page /parametres) : thème, police,
-- profil, notifications, confidentialité, etc.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_preferences (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,

  -- === Onglet Général : Profil ===
  full_name TEXT,
  nickname TEXT,
  profession TEXT,
  llm_preferences TEXT,  -- "ex: garder les explications brèves"

  -- === Onglet Général : Apparence ===
  theme TEXT DEFAULT 'auto' CHECK (theme IN ('light', 'auto', 'dark')),
  background_animation TEXT DEFAULT 'auto' CHECK (background_animation IN ('on', 'auto', 'off')),
  font TEXT DEFAULT 'default' CHECK (font IN ('default', 'sans', 'system', 'dyslexia')),
  logo_size TEXT DEFAULT 'lg' CHECK (logo_size IN ('sm', 'md', 'lg', 'xl', '2xl', '3xl')),

  -- === Onglet Général : Notifications (jsonb pour extensibilité) ===
  notifications JSONB DEFAULT '{
    "completion": false,
    "email_reports": false,
    "push_messages": false
  }'::jsonb,

  -- === Onglet Confidentialité ===
  privacy JSONB DEFAULT '{
    "location_metadata": true,
    "improve_models": true,
    "memory_enabled": true
  }'::jsonb,

  -- === Onglet Capacités ===
  capabilities JSONB DEFAULT '{
    "memory_search": true,
    "memory_generate": true,
    "tools_mode": "on_demand"
  }'::jsonb,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- === RLS : chaque user ne voit que sa ligne ===
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own preferences"
  ON public.user_preferences FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own preferences"
  ON public.user_preferences FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own preferences"
  ON public.user_preferences FOR UPDATE
  USING (auth.uid() = user_id);

-- === Trigger updated_at auto ===
CREATE OR REPLACE FUNCTION public.handle_user_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_preferences_updated_at
  BEFORE UPDATE ON public.user_preferences
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_user_preferences_updated_at();

-- === Helper : créer une ligne par défaut à la 1ère connexion ===
-- Si on l'insère via frontend sur premier load, pas besoin de trigger.
-- On laisse l'insertion à la demande (upsert côté client).
