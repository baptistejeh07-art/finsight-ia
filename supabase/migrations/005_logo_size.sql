-- ============================================================================
-- Migration 005 : logo_size sur user_preferences
-- Ajout d'une colonne de préférence taille du logo vitrine (slider /parametres)
-- ============================================================================

ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS logo_size TEXT DEFAULT 'lg';

-- Contrainte CHECK (en DROP+ADD pour être idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.constraint_column_usage
    WHERE table_name = 'user_preferences' AND constraint_name = 'user_preferences_logo_size_check'
  ) THEN
    ALTER TABLE public.user_preferences
      ADD CONSTRAINT user_preferences_logo_size_check
      CHECK (logo_size IN ('sm', 'md', 'lg', 'xl', '2xl', '3xl'));
  END IF;
END $$;
