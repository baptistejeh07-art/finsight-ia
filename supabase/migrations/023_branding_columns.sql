-- ============================================================================
-- Migration 023 : white-label léger sur user_preferences
-- Permet aux plans Pro+ de personnaliser logo + couleurs des livrables PDF/PPTX.
-- ============================================================================

ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS brand_logo_url TEXT,
  ADD COLUMN IF NOT EXISTS brand_primary_color TEXT DEFAULT '#1B2A4A',
  ADD COLUMN IF NOT EXISTS brand_secondary_color TEXT DEFAULT '#6B7280',
  ADD COLUMN IF NOT EXISTS brand_company_name TEXT;
