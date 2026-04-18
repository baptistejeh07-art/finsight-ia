"""Handler webhook Stripe — préparé mais inactif tant que pricing OFF.

Pour activer :
  1. Créer un compte Stripe (mode test d'abord)
  2. Ajouter STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET dans .env
  3. Configurer le endpoint webhook : https://finsight-ia-production.up.railway.app/stripe/webhook
  4. Souscrire aux events : customer.subscription.created/updated/deleted, invoice.paid/payment_failed
  5. Décommenter le router include dans backend/main.py

Schémas SQL : voir supabase/migrations/002_phase2_users_quotas_subscriptions.sql
"""
from __future__ import annotations
import os
import logging
from typing import Optional

log = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


def is_enabled() -> bool:
    """True si Stripe est configuré (clé + webhook secret)."""
    return bool(STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET)


def verify_webhook(payload: bytes, signature: str) -> Optional[dict]:
    """Vérifie la signature Stripe et retourne l'event dict si valide."""
    if not is_enabled():
        log.warning("[stripe] webhook reçu mais Stripe non configuré — skip")
        return None
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
        return event
    except Exception as e:
        log.error(f"[stripe] webhook signature invalide : {e}")
        return None


def handle_event(event: dict) -> bool:
    """Dispatch handler par type d'event. Best-effort, log + retourne True/False."""
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    log.info(f"[stripe] webhook event : {event_type}")

    try:
        if event_type == "customer.subscription.created":
            return _on_subscription_created(data)
        if event_type == "customer.subscription.updated":
            return _on_subscription_updated(data)
        if event_type == "customer.subscription.deleted":
            return _on_subscription_deleted(data)
        if event_type == "invoice.paid":
            return _on_invoice_paid(data)
        if event_type == "invoice.payment_failed":
            return _on_payment_failed(data)
        log.debug(f"[stripe] event ignored : {event_type}")
        return True
    except Exception as e:
        log.error(f"[stripe] handler {event_type} failed : {e}")
        return False


# ─── Handlers individuels (à compléter quand pricing actif) ──────────────────

def _on_subscription_created(sub: dict) -> bool:
    """Crée la row subscriptions + bump le profile.plan."""
    # TODO Phase 2 : insert subscriptions + update profiles.plan
    log.info(f"[stripe] subscription created : {sub.get('id')}")
    return True


def _on_subscription_updated(sub: dict) -> bool:
    """Update status + dates."""
    log.info(f"[stripe] subscription updated : {sub.get('id')} → {sub.get('status')}")
    return True


def _on_subscription_deleted(sub: dict) -> bool:
    """Marque comme canceled + downgrade plan vers decouverte."""
    log.info(f"[stripe] subscription deleted : {sub.get('id')}")
    return True


def _on_invoice_paid(inv: dict) -> bool:
    """Reset les quotas pour la nouvelle période."""
    log.info(f"[stripe] invoice paid : {inv.get('id')}")
    return True


def _on_payment_failed(inv: dict) -> bool:
    """Notification user + grace period."""
    log.warning(f"[stripe] payment failed : {inv.get('id')}")
    return True
