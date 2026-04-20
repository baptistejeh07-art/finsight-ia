"""Handler webhook Stripe — persiste subscriptions vers Supabase.

Activation :
  1. Créer compte Stripe, mode test
  2. Env vars : STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET
  3. Endpoint : https://finsight-ia-production.up.railway.app/stripe/webhook
  4. Events : customer.subscription.created/updated/deleted,
              invoice.paid, invoice.payment_failed
"""
from __future__ import annotations
import logging
import os
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Mapping price_id Stripe → plan FinSight
# Défini au runtime via STRIPE_PRICE_MAP env var (JSON) OU hardcodé après
# stripe_setup.py. Ex: '{"price_xxx":"decouverte","price_yyy":"pro"}'
import json as _json

_PRICE_MAP: dict[str, str] = {}
try:
    _PRICE_MAP = _json.loads(os.getenv("STRIPE_PRICE_MAP", "{}"))
except Exception:
    _PRICE_MAP = {}


def is_enabled() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET)


def verify_webhook(payload: bytes, signature: str) -> Optional[dict]:
    if not is_enabled():
        log.warning("[stripe] webhook reçu mais Stripe non configuré — skip")
        return None
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        return stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        log.error(f"[stripe] webhook signature invalide : {e}")
        return None


def handle_event(event: dict) -> bool:
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    log.info(f"[stripe] event : {event_type}")
    try:
        if event_type == "customer.subscription.created":
            return _upsert_subscription(data)
        if event_type == "customer.subscription.updated":
            return _upsert_subscription(data)
        if event_type == "customer.subscription.deleted":
            return _on_subscription_deleted(data)
        if event_type == "invoice.paid":
            return _on_invoice_paid(data)
        if event_type == "invoice.payment_failed":
            return _on_payment_failed(data)
    except Exception as e:
        log.error(f"[stripe] handler {event_type} exception : {e}")
    return False


def _plan_from_price_id(price_id: Optional[str]) -> str:
    """Mapping price → plan. Env STRIPE_PRICE_MAP JSON sinon 'decouverte'."""
    if not price_id:
        return "decouverte"
    return _PRICE_MAP.get(price_id, "decouverte")


def _ts(unix: Any) -> Optional[str]:
    if not unix:
        return None
    try:
        return datetime.utcfromtimestamp(int(unix)).isoformat() + "+00:00"
    except Exception:
        return None


def _supabase_upsert_subscription(row: dict) -> bool:
    """Upsert dans user_subscriptions via PostgREST (on stripe_subscription_id)."""
    import httpx
    surl = os.getenv("SUPABASE_URL", "").rstrip("/")
    skey = (os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not surl or not skey:
        log.warning("[stripe] Supabase non configuré — skip persistance")
        return False
    try:
        r = httpx.post(
            f"{surl}/rest/v1/user_subscriptions",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=row, timeout=5.0,
        )
        if r.status_code >= 300:
            log.warning(f"[stripe] upsert sub HTTP {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log.error(f"[stripe] upsert sub exception : {e}")
        return False


def _supabase_update_user_plan(user_id: str, plan: str,
                                 stripe_customer_id: Optional[str] = None,
                                 period_end: Optional[str] = None) -> bool:
    import httpx
    surl = os.getenv("SUPABASE_URL", "").rstrip("/")
    skey = (os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not surl or not skey or not user_id:
        return False
    update = {"plan": plan}
    if stripe_customer_id:
        update["stripe_customer_id"] = stripe_customer_id
    if period_end:
        update["plan_current_period_end"] = period_end
    try:
        r = httpx.patch(
            f"{surl}/rest/v1/user_preferences?user_id=eq.{user_id}",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=update, timeout=5.0,
        )
        if r.status_code >= 300:
            log.warning(f"[stripe] update plan HTTP {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log.error(f"[stripe] update plan exception : {e}")
        return False


def _find_user_id_by_customer(stripe_customer_id: str) -> Optional[str]:
    import httpx
    surl = os.getenv("SUPABASE_URL", "").rstrip("/")
    skey = (os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    try:
        r = httpx.get(
            f"{surl}/rest/v1/user_preferences?stripe_customer_id=eq.{stripe_customer_id}&select=user_id",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            timeout=3.0,
        )
        rows = r.json() if r.status_code == 200 else []
        return rows[0]["user_id"] if rows else None
    except Exception:
        return None


def _upsert_subscription(sub: dict) -> bool:
    """Upsert user_subscriptions + update user_preferences.plan."""
    sid = sub.get("id")
    cid = sub.get("customer")
    status = sub.get("status", "active")
    items = (sub.get("items") or {}).get("data") or []
    price = items[0].get("price") if items else {}
    price_id = price.get("id")
    amount_cents = price.get("unit_amount") or 0
    interval = (price.get("recurring") or {}).get("interval")
    plan = _plan_from_price_id(price_id)

    user_id = (sub.get("metadata") or {}).get("user_id")
    if not user_id and cid:
        user_id = _find_user_id_by_customer(cid)
    if not user_id:
        log.warning(f"[stripe] subscription {sid}: user_id introuvable (customer={cid})")
        return False

    period_end = _ts(sub.get("current_period_end"))
    row = {
        "user_id": user_id,
        "stripe_subscription_id": sid,
        "stripe_customer_id": cid,
        "stripe_price_id": price_id,
        "plan": plan,
        "interval": interval,
        "amount_eur": round(amount_cents / 100, 2),
        "status": status,
        "current_period_start": _ts(sub.get("current_period_start")),
        "current_period_end": period_end,
        "canceled_at": _ts(sub.get("canceled_at")),
        "ended_at": _ts(sub.get("ended_at")),
        "raw_event": sub,
    }
    ok1 = _supabase_upsert_subscription(row)

    # Update plan user_preferences uniquement si status actif ou trialing
    if status in {"active", "trialing", "past_due"}:
        _supabase_update_user_plan(user_id, plan,
                                    stripe_customer_id=cid,
                                    period_end=period_end)
    elif status in {"canceled", "unpaid", "incomplete_expired"}:
        _supabase_update_user_plan(user_id, "free",
                                    stripe_customer_id=cid)

    return ok1


def _on_subscription_deleted(sub: dict) -> bool:
    """Downgrade vers free."""
    sid = sub.get("id")
    cid = sub.get("customer")
    user_id = (sub.get("metadata") or {}).get("user_id")
    if not user_id and cid:
        user_id = _find_user_id_by_customer(cid)
    if user_id:
        _supabase_update_user_plan(user_id, "free", stripe_customer_id=cid)
    _upsert_subscription({**sub, "status": "canceled"})
    log.info(f"[stripe] subscription {sid} supprimée → plan free")
    return True


def _on_invoice_paid(inv: dict) -> bool:
    """Invoice payée — rien à faire (subscription.updated déjà traitée)."""
    log.info(f"[stripe] invoice paid {inv.get('id')}: {inv.get('amount_paid', 0)/100}€")
    return True


def _on_payment_failed(inv: dict) -> bool:
    """Paiement échoué — le status passera en past_due via subscription.updated."""
    log.warning(f"[stripe] payment failed {inv.get('id')} customer={inv.get('customer')}")
    return True
