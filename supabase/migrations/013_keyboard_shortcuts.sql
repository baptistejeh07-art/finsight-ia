-- ============================================================================
-- Migration 013 : raccourcis clavier customisables
-- - shortcuts : jsonb { action: combo } pour tous les users
-- - dev_shortcuts : jsonb { action: combo } pour admins uniquement (no-op si non admin)
-- ============================================================================

ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS shortcuts JSONB DEFAULT '{
    "newAnalysis": "ctrl+k",
    "openHistory": "ctrl+h",
    "toggleFavoritesFilter": "ctrl+b",
    "openSettings": "ctrl+,",
    "toggleTheme": "ctrl+shift+t",
    "openHomepage": "ctrl+shift+h"
  }'::jsonb,
  ADD COLUMN IF NOT EXISTS dev_shortcuts JSONB DEFAULT '{
    "openAdminDashboard": "ctrl+shift+d",
    "clearLocalCache": "ctrl+shift+l",
    "reloadHardNoCache": "ctrl+shift+r",
    "toggleDevMode": "ctrl+shift+m",
    "openTrendsPage": "ctrl+shift+y"
  }'::jsonb;
