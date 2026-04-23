-- Migration 011 : ajoute le plan "early_backer" (20€/mois à vie, 10 places max).
--
-- Étend les check constraints existants sur user_preferences.plan et
-- user_subscriptions.plan pour autoriser la nouvelle valeur.

-- user_preferences
alter table public.user_preferences
  drop constraint if exists user_preferences_plan_check;

alter table public.user_preferences
  add constraint user_preferences_plan_check
  check (plan in ('free', 'early_backer', 'decouverte', 'pro', 'enterprise'));

comment on column public.user_preferences.plan
  is 'Plan abonnement actuel : free, early_backer (20€/mois à vie, 10 places max), decouverte 34.99€, pro 44.99€, enterprise 299-499€';

-- user_subscriptions
alter table public.user_subscriptions
  drop constraint if exists user_subscriptions_plan_check;

alter table public.user_subscriptions
  add constraint user_subscriptions_plan_check
  check (plan in ('early_backer', 'decouverte', 'pro', 'enterprise'));

-- Vue utile : compteur Early Backers actifs pour afficher "X/10 places"
create or replace view public.early_backer_count as
select count(*) as used,
       10 as total,
       greatest(0, 10 - count(*)) as remaining
from public.user_preferences
where plan = 'early_backer';

grant select on public.early_backer_count to anon, authenticated;
