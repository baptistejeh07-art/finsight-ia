-- Migration 010 : Stripe subscriptions + plan column.
--
-- Ajoute :
--  - user_preferences.plan : plan actuel ('free', 'decouverte', 'pro', 'enterprise')
--  - user_preferences.stripe_customer_id : Stripe Customer ID (cus_...)
--  - table user_subscriptions : historique des abonnements
--
-- Le plan est la source de vérité pour les quotas. Les webhooks Stripe
-- updatent user_preferences.plan + user_subscriptions au fil de l'eau.

alter table public.user_preferences
  add column if not exists plan text default 'free'
    check (plan in ('free', 'decouverte', 'pro', 'enterprise'));

alter table public.user_preferences
  add column if not exists stripe_customer_id text;

alter table public.user_preferences
  add column if not exists plan_current_period_end timestamptz;

comment on column public.user_preferences.plan
  is 'Plan abonnement actuel : free (par défaut), decouverte 34.99€, pro 44.99€, enterprise 299-499€';
comment on column public.user_preferences.stripe_customer_id
  is 'Stripe Customer ID (cus_xxx) pour billing portal et history';
comment on column public.user_preferences.plan_current_period_end
  is 'Fin de la période de facturation actuelle (pour afficher dans UI + grace period)';

create index if not exists idx_user_preferences_stripe_customer
  on public.user_preferences (stripe_customer_id)
  where stripe_customer_id is not null;


-- Historique complet des abonnements (pour analytics + audit)
create table if not exists public.user_subscriptions (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  user_id uuid not null references auth.users(id) on delete cascade,
  stripe_subscription_id text not null unique,
  stripe_customer_id text,
  stripe_price_id text,

  plan text not null check (plan in ('decouverte', 'pro', 'enterprise')),
  interval text check (interval in ('month', 'year')),   -- mensuel ou annuel
  amount_eur numeric not null default 0,                 -- montant période

  status text not null check (status in (
    'incomplete', 'incomplete_expired',
    'trialing', 'active',
    'past_due', 'canceled', 'unpaid'
  )),

  current_period_start timestamptz,
  current_period_end timestamptz,
  canceled_at timestamptz,
  ended_at timestamptz,

  raw_event jsonb  -- dernier event Stripe (debug)
);

create index if not exists idx_user_subscriptions_user
  on public.user_subscriptions (user_id, created_at desc);

create index if not exists idx_user_subscriptions_status
  on public.user_subscriptions (status);

-- RLS : user voit ses propres subscriptions, admin voit tout
alter table public.user_subscriptions enable row level security;

drop policy if exists "subs_own_read" on public.user_subscriptions;
create policy "subs_own_read" on public.user_subscriptions
  for select to authenticated
  using (
    user_id = auth.uid()
    or exists (select 1 from public.user_preferences where user_id = auth.uid() and is_admin = true)
  );

-- Pas de policy insert/update côté client — seul service_role via webhooks écrit.

comment on table public.user_subscriptions is
  'Historique des abonnements Stripe. Une ligne par événement subscription.*. '
  'Le status courant est aussi reflété dans user_preferences.plan pour enforcement quotas.';
