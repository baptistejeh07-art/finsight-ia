"""Envoi des notifications d'alertes : email (Resend) + Web Push (VAPID)."""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)


# ─── Email via Resend ───────────────────────────────────────────────────────

def send_email(to: str, subject: str, body: str, ticker: Optional[str] = None) -> bool:
    """Envoie un email via Resend API. No-op si RESEND_API_KEY absente."""
    key = os.getenv("RESEND_API_KEY", "").strip()
    if not key:
        log.info(f"[alerts] email skipped (RESEND_API_KEY missing): {to} · {subject}")
        return False

    from_addr = os.getenv("RESEND_FROM", "FinSight IA <alerts@finsight-ia.com>")
    html = _render_email_html(subject, body, ticker)
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"from": from_addr, "to": [to], "subject": subject, "html": html, "text": body},
            timeout=10.0,
        )
        if r.status_code >= 300:
            log.warning(f"[alerts] Resend HTTP {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log.warning(f"[alerts] Resend exception: {e}")
        return False


def _render_email_html(subject: str, body: str, ticker: Optional[str]) -> str:
    base = os.getenv("NEXT_PUBLIC_APP_URL", "https://finsight-ia.com")
    cta_url = f"{base}/app" if not ticker else f"{base}/app"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafaf5;padding:32px;color:#1a1a1a;">
<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;border:1px solid #e5e5e0;">
  <div style="font-size:12px;letter-spacing:2px;color:#666;text-transform:uppercase;margin-bottom:12px;font-weight:600;">
    FinSight IA · Rappel
  </div>
  <h1 style="font-size:22px;margin:0 0 16px;color:#0c0c0c;font-weight:600;">{subject}</h1>
  <p style="font-size:15px;line-height:1.6;color:#333;margin:0 0 24px;">{body}</p>
  <a href="{cta_url}" style="display:inline-block;background:#0c0c0c;color:#fff;text-decoration:none;padding:10px 18px;border-radius:6px;font-size:14px;font-weight:600;">
    Ouvrir FinSight
  </a>
  <div style="margin-top:32px;padding-top:24px;border-top:1px solid #eee;font-size:12px;color:#888;line-height:1.5;">
    Vous recevez cet email car vous avez créé un rappel sur FinSight IA.
    <a href="{base}/parametres/rappels" style="color:#666;">Gérer mes rappels</a>.
  </div>
</div>
</body></html>"""


# ─── Web Push via VAPID ─────────────────────────────────────────────────────

def send_push(subscription: dict, title: str, body: str, url_path: str = "/app") -> bool:
    """Envoie une notification Web Push. No-op si VAPID keys absentes."""
    private = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    public = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    subject = os.getenv("VAPID_SUBJECT", "mailto:contact@finsight-ia.com")
    if not private or not public:
        log.info("[alerts] push skipped (VAPID keys missing)")
        return False

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        log.warning("[alerts] pywebpush non installé")
        return False

    sub_dict = {
        "endpoint": subscription.get("endpoint"),
        "keys": {
            "p256dh": subscription.get("p256dh"),
            "auth": subscription.get("auth_key") or subscription.get("auth"),
        },
    }
    payload = json.dumps({"title": title, "body": body, "url": url_path, "icon": "/icon.png"})
    try:
        webpush(
            subscription_info=sub_dict,
            data=payload,
            vapid_private_key=private,
            vapid_claims={"sub": subject},
        )
        return True
    except WebPushException as e:
        log.warning(f"[alerts] webpush failed (status {e.response.status_code if e.response else '?'}): {e}")
        return False
    except Exception as e:
        log.warning(f"[alerts] webpush exception: {e}")
        return False
