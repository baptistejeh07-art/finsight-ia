-- Migration 007 : devise + langue préférées de l'utilisateur.
-- - currency : devise affichée dans toute l'UI + outputs (EUR, USD, GBP, CHF, JPY, CAD)
-- - language : langue d'interface + commentaires LLM + outputs
--   FR/EN/ES/DE/IT/PT (FR = défaut, marché cible domestic)

alter table public.user_preferences
  add column if not exists currency text default 'EUR'
    check (currency in ('EUR','USD','GBP','CHF','JPY','CAD'));

alter table public.user_preferences
  add column if not exists language text default 'fr'
    check (language in ('fr','en','es','de','it','pt'));

-- Backfill : les rows existantes ont déjà EUR/fr via DEFAULT
-- (pas besoin d'update explicite)

comment on column public.user_preferences.currency
  is 'Devise utilisée dans l affichage UI + outputs (formatage uniquement, pas de conversion forcée)';
comment on column public.user_preferences.language
  is 'Langue interface + commentaires LLM + outputs (FR par défaut, EN/ES/DE/IT/PT supportés)';
