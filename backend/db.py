"""Persistence Supabase Postgres via REST API (PostgREST).

On n'utilise PAS le SDK supabase-py (incompat Python 3.14 + dépendances lourdes).
On parle directement à PostgREST avec httpx + clé service_role.

Table SQL à créer dans Supabase (one-shot) :

    CREATE TABLE IF NOT EXISTS analyses_history (
        id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id      uuid NOT NULL,
        kind         text NOT NULL,
        label        text,
        ticker       text,
        status       text NOT NULL DEFAULT 'done',
        created_at   timestamptz NOT NULL DEFAULT now(),
        finished_at  timestamptz,
        files        jsonb,
        meta         jsonb
    );
    CREATE INDEX IF NOT EXISTS idx_analyses_history_user_created
        ON analyses_history (user_id, created_at DESC);

RLS désactivée car on attaque via service_role (server-side).
"""

from __future__ import annotations
import os
import logging
from datetime import datetime
from typing import Optional, Any
import httpx

log = logging.getLogger(__name__)

_SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or ""
)


def _enabled() -> bool:
    return bool(_SUPABASE_URL and _SERVICE_KEY)


def _headers() -> dict:
    return {
        "apikey": _SERVICE_KEY,
        "Authorization": f"Bearer {_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def insert_analysis(
    *,
    user_id: str,
    kind: str,
    label: Optional[str] = None,
    ticker: Optional[str] = None,
    status: str = "done",
    files: Optional[dict] = None,
    meta: Optional[dict] = None,
    finished_at: Optional[datetime] = None,
) -> bool:
    """Persiste une analyse terminée dans la table analyses_history.

    Silencieux si Supabase non configuré (renvoie False). Logué si erreur HTTP.
    """
    if not _enabled():
        log.debug("[db] insert_analysis skipped : Supabase non configuré")
        return False

    payload = {
        "user_id": user_id,
        "kind": kind,
        "label": label,
        "ticker": ticker,
        "status": status,
        "files": files,
        "meta": meta,
    }
    if finished_at is not None:
        payload["finished_at"] = finished_at.isoformat()
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        r = httpx.post(
            f"{_SUPABASE_URL}/rest/v1/analyses_history",
            headers=_headers(),
            json=payload,
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] insert_analysis HTTP {r.status_code} : {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log.warning(f"[db] insert_analysis exception : {e}")
        return False


def list_analyses(user_id: str, limit: int = 50) -> list[dict]:
    """Retourne les N dernières analyses du user (plus récentes d'abord).

    Retourne [] si Supabase non configuré ou si la table n'existe pas.
    """
    if not _enabled():
        return []

    try:
        r = httpx.get(
            f"{_SUPABASE_URL}/rest/v1/analyses_history",
            headers={**_headers(), "Prefer": "count=none"},
            params={
                "user_id": f"eq.{user_id}",
                "select": "id,kind,label,ticker,status,created_at,finished_at,files",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] list_analyses HTTP {r.status_code} : {r.text[:200]}")
            return []
        return r.json() or []
    except Exception as e:
        log.warning(f"[db] list_analyses exception : {e}")
        return []
