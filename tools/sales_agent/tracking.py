# -*- coding: utf-8 -*-
"""tools/sales_agent/tracking.py — CRUD Supabase pour le sales agent.

Wrapper minimal autour de Supabase REST API. On ne ramène pas tout
postgrest-py pour rester léger — httpx + service_role suffit.

Tables manipulées :
- sales_prospects (un prospect = une ligne)
- sales_prospect_status (track sent/replied/converted/ghosted + relances)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_SECRET_KEY")
           or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    return url, key


def _headers(skey: str, prefer_repr: bool = False) -> dict:
    h = {
        "apikey": skey,
        "Authorization": f"Bearer {skey}",
        "Content-Type": "application/json",
    }
    if prefer_repr:
        h["Prefer"] = "return=representation"
    return h


# ─── Prospects CRUD ─────────────────────────────────────────────────────

def insert_prospect(
    *,
    linkedin_url: str,
    name: Optional[str] = None,
    headline: Optional[str] = None,
    bio: Optional[str] = None,
    recent_posts: Optional[list[dict]] = None,
    qualification_score: Optional[int] = None,
    qualification_breakdown: Optional[dict] = None,
    qualification_reasoning: Optional[str] = None,
    target_ticker: Optional[str] = None,
    dm_draft: Optional[str] = None,
    pdf_demo_path: Optional[str] = None,
) -> Optional[str]:
    """Upsert un prospect par linkedin_url. Retourne l'id (uuid) ou None."""
    surl, skey = _supabase_creds()
    if not surl or not skey:
        log.warning("[sales/track] Supabase non configuré")
        return None
    payload = {
        "linkedin_url": linkedin_url,
        "name": name,
        "headline": headline,
        "bio": bio,
        "recent_posts": recent_posts or [],
        "qualification_score": qualification_score,
        "qualification_breakdown": qualification_breakdown or {},
        "qualification_reasoning": qualification_reasoning,
        "target_ticker": target_ticker,
        "dm_draft": dm_draft,
        "pdf_demo_path": pdf_demo_path,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        r = httpx.post(
            f"{surl}/rest/v1/sales_prospects",
            headers={**_headers(skey, prefer_repr=True),
                       "Prefer": "return=representation,resolution=merge-duplicates"},
            params={"on_conflict": "linkedin_url"},
            json=payload,
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[sales/track] insert_prospect HTTP {r.status_code} : {r.text[:200]}")
            return None
        rows = r.json() or []
        return rows[0]["id"] if rows else None
    except Exception as e:
        log.warning(f"[sales/track] insert_prospect exception : {e}")
        return None


def get_prospect(prospect_id: str) -> Optional[dict]:
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return None
    try:
        r = httpx.get(
            f"{surl}/rest/v1/sales_prospects",
            headers=_headers(skey),
            params={"id": f"eq.{prospect_id}", "limit": "1"},
            timeout=6.0,
        )
        rows = r.json() if r.status_code < 300 else []
        return rows[0] if rows else None
    except Exception as e:
        log.warning(f"[sales/track] get_prospect : {e}")
        return None


def list_top_today(limit: int = 10, min_score: int = 40) -> list[dict]:
    """Top prospects qualifiés du jour, jamais contactés (statut absent ou
    queued). Triés par score desc."""
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return []
    try:
        # Query : prospects scorés > min_score, sans statut sent/replied/converted/ghosted
        # Postgrest ne supporte pas LEFT JOIN simple → 2 queries puis filter.
        r = httpx.get(
            f"{surl}/rest/v1/sales_prospects",
            headers=_headers(skey),
            params={
                "qualification_score": f"gte.{min_score}",
                "order": "qualification_score.desc",
                "limit": str(min(50, max(1, limit * 3))),
            },
            timeout=8.0,
        )
        if r.status_code >= 300:
            return []
        prospects = r.json() or []
        if not prospects:
            return []
        # Récupère les statuts pour ces prospect_ids
        ids = ",".join(p["id"] for p in prospects)
        r2 = httpx.get(
            f"{surl}/rest/v1/sales_prospect_status",
            headers=_headers(skey),
            params={"prospect_id": f"in.({ids})", "select": "prospect_id,status"},
            timeout=8.0,
        )
        statuses = {}
        if r2.status_code < 300:
            for row in r2.json() or []:
                statuses[row["prospect_id"]] = row["status"]
        # Filtre : on garde queued OU absent
        active = [p for p in prospects
                   if statuses.get(p["id"], "queued") == "queued"]
        return active[:limit]
    except Exception as e:
        log.warning(f"[sales/track] list_top_today : {e}")
        return []


# ─── Status CRUD ────────────────────────────────────────────────────────

def update_status(
    prospect_id: str,
    status: str,
    *,
    response_text: Optional[str] = None,
    notes: Optional[str] = None,
    conversion_amount: Optional[float] = None,
) -> bool:
    """Update ou insert le statut d'un prospect. Status valides :
    queued | sent | replied | converted | ghosted.
    """
    if status not in ("queued", "sent", "replied", "converted", "ghosted"):
        log.warning(f"[sales/track] status invalide : {status}")
        return False
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return False
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "prospect_id": prospect_id,
        "status": status,
        "updated_at": now_iso,
    }
    if status == "sent":
        payload["sent_at"] = now_iso
    elif status == "replied":
        payload["response_at"] = now_iso
        if response_text:
            payload["response_text"] = response_text[:2000]
    elif status == "converted":
        payload["converted_at"] = now_iso
        if conversion_amount is not None:
            payload["conversion_amount"] = float(conversion_amount)
    if notes:
        payload["notes"] = notes[:1000]
    try:
        # Vérifie si le row existe déjà
        rget = httpx.get(
            f"{surl}/rest/v1/sales_prospect_status",
            headers=_headers(skey),
            params={"prospect_id": f"eq.{prospect_id}", "limit": "1"},
            timeout=6.0,
        )
        existing = rget.json() if rget.status_code < 300 else []
        if existing:
            # PATCH
            r = httpx.patch(
                f"{surl}/rest/v1/sales_prospect_status",
                headers={**_headers(skey), "Prefer": "return=minimal"},
                params={"prospect_id": f"eq.{prospect_id}"},
                json=payload,
                timeout=6.0,
            )
        else:
            # INSERT
            r = httpx.post(
                f"{surl}/rest/v1/sales_prospect_status",
                headers={**_headers(skey), "Prefer": "return=minimal"},
                json=payload,
                timeout=6.0,
            )
        if r.status_code >= 300:
            log.warning(f"[sales/track] update_status HTTP {r.status_code} : {r.text[:200]}")
            return False
        log.info(f"[sales/track] {prospect_id[:8]} → {status}")
        return True
    except Exception as e:
        log.warning(f"[sales/track] update_status exception : {e}")
        return False


# ─── Stats hebdo ───────────────────────────────────────────────────────

def stats_weekly() -> dict:
    """Compte par status sur les 7 derniers jours + cap journalier
    (pour vérif anti-ban)."""
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return {}
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        r = httpx.get(
            f"{surl}/rest/v1/sales_prospect_status",
            headers=_headers(skey),
            params={"updated_at": f"gte.{cutoff}",
                     "select": "status,sent_at,converted_at,conversion_amount"},
            timeout=8.0,
        )
        rows = r.json() if r.status_code < 300 else []
        sent = sum(1 for r in rows if r.get("sent_at"))
        replied = sum(1 for r in rows if r.get("status") == "replied")
        converted = sum(1 for r in rows if r.get("status") == "converted")
        ghosted = sum(1 for r in rows if r.get("status") == "ghosted")
        revenue = sum(float(r.get("conversion_amount") or 0)
                      for r in rows if r.get("status") == "converted")
        # Sent today
        today = datetime.now(timezone.utc).date().isoformat()
        sent_today = sum(1 for r in rows
                          if (r.get("sent_at") or "").startswith(today))
        return {
            "sent_7d": sent,
            "sent_today": sent_today,
            "replied_7d": replied,
            "converted_7d": converted,
            "ghosted_7d": ghosted,
            "revenue_7d": round(revenue, 2),
            "reply_rate": round(replied / sent * 100, 1) if sent else 0,
            "conversion_rate": round(converted / replied * 100, 1) if replied else 0,
            "cap_daily": 15,
            "cap_remaining_today": max(0, 15 - sent_today),
        }
    except Exception as e:
        log.warning(f"[sales/track] stats_weekly : {e}")
        return {}
