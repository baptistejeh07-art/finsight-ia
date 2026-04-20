"""FinSight Public API v1 — endpoints sous /api/v1/* avec auth par clé API.

Différent de l'auth Supabase JWT (qui sert l'UI web). Ici les clients
programmatiques (backends tiers, bots, hedge funds) utilisent une clé
`fsk_xxx` envoyée en header `X-API-Key`.

Rate limits :
  - per_minute : 30 req/min par défaut (config par clé)
  - per_day    : 1000 req/jour par défaut

Endpoints :
  - POST /api/v1/analyze/societe
  - POST /api/v1/analyze/secteur
  - POST /api/v1/analyze/indice
  - GET  /api/v1/me (info clé + usage)
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["public-api"])


# ---------------------------------------------------------------------------
# Clé API : génération, hash, validation
# ---------------------------------------------------------------------------

_KEY_PREFIX = "fsk_"


def generate_api_key() -> tuple[str, str, str]:
    """Génère une nouvelle clé. Retourne (key_plain, key_hash, prefix).

    key_plain : à retourner à l'user UNE SEULE FOIS (jamais stockée claire)
    key_hash : SHA256, stocké en DB
    prefix : 12 premiers chars (affichés dans UI admin)
    """
    token = secrets.token_urlsafe(32)
    key_plain = f"{_KEY_PREFIX}{token}"
    key_hash = hashlib.sha256(key_plain.encode()).hexdigest()
    prefix = key_plain[:12]
    return key_plain, key_hash, prefix


def hash_key(key_plain: str) -> str:
    return hashlib.sha256(key_plain.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Rate limiter in-memory (simple, par process Railway)
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Sliding window in-memory. Pour prod multi-process, remplacer par Redis."""

    def __init__(self) -> None:
        self._minute: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._day: dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))

    def check(self, key_id: str, per_min: int, per_day: int) -> tuple[bool, str]:
        now = time.time()
        mq = self._minute[key_id]
        dq = self._day[key_id]
        # Purge > 60s
        while mq and mq[0] < now - 60:
            mq.popleft()
        while dq and dq[0] < now - 86400:
            dq.popleft()
        if len(mq) >= per_min:
            return False, f"Rate limit minute: {per_min}/min dépassé"
        if len(dq) >= per_day:
            return False, f"Rate limit quotidien: {per_day}/jour dépassé"
        mq.append(now)
        dq.append(now)
        return True, ""


_LIMITER = _RateLimiter()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_SECRET_KEY")
           or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    return url, key


def require_api_key(
    request: Request,
    x_api_key: Annotated[Optional[str], Header()] = None,
) -> dict:
    """Valide la clé API. Retourne le record api_keys."""
    if not x_api_key or not x_api_key.startswith(_KEY_PREFIX):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")

    surl, skey = _supabase_creds()
    if not surl or not skey:
        raise HTTPException(status_code=500, detail="API unavailable")

    key_hash = hash_key(x_api_key)
    try:
        r = httpx.get(
            f"{surl}/rest/v1/api_keys",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            params={"key_hash": f"eq.{key_hash}", "revoked_at": "is.null",
                    "select": "id,user_id,name,rate_limit_per_min,rate_limit_per_day"},
            timeout=5.0,
        )
        rows = r.json() if r.status_code < 300 else []
        if not rows:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        api_key_row = rows[0]
    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"[api-auth] lookup fail: {e}")
        raise HTTPException(status_code=500, detail="Auth error")

    # Rate limit
    ok, reason = _LIMITER.check(
        api_key_row["id"],
        api_key_row.get("rate_limit_per_min", 30),
        api_key_row.get("rate_limit_per_day", 1000),
    )
    if not ok:
        raise HTTPException(status_code=429, detail=reason)

    # Update last_used + log usage (best-effort async)
    request.state.api_key_row = api_key_row
    request.state.api_start = time.time()
    return api_key_row


def _log_usage(request: Request, status_code: int) -> None:
    """Log usage dans api_usage (best-effort)."""
    surl, skey = _supabase_creds()
    if not surl or not skey:
        return
    row = getattr(request.state, "api_key_row", None)
    start = getattr(request.state, "api_start", time.time())
    if not row:
        return
    try:
        httpx.post(
            f"{surl}/rest/v1/api_usage",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={
                "key_id": row["id"],
                "user_id": row.get("user_id"),
                "endpoint": str(request.url.path),
                "method": request.method,
                "status_code": status_code,
                "duration_ms": int((time.time() - start) * 1000),
                "ip": request.client.host if request.client else None,
            },
            timeout=3.0,
        )
        httpx.patch(
            f"{surl}/rest/v1/api_keys",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            params={"id": f"eq.{row['id']}"},
            json={"last_used_at": datetime.now(timezone.utc).isoformat()},
            timeout=3.0,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ApiSocieteRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    language: Optional[str] = "fr"
    currency: Optional[str] = "EUR"


class ApiSecteurRequest(BaseModel):
    secteur: str
    univers: str = "S&P 500"
    language: Optional[str] = "fr"
    currency: Optional[str] = "EUR"


class ApiIndiceRequest(BaseModel):
    indice: str
    language: Optional[str] = "fr"
    currency: Optional[str] = "EUR"


# ---------------------------------------------------------------------------
# Endpoints publics
# ---------------------------------------------------------------------------

@router.get("/me")
async def api_me(request: Request, key_row: dict = Depends(require_api_key)):
    """Info sur la clé utilisée + quota restant."""
    _log_usage(request, 200)
    return {
        "key_id": key_row["id"],
        "name": key_row.get("name"),
        "rate_limit_per_min": key_row.get("rate_limit_per_min"),
        "rate_limit_per_day": key_row.get("rate_limit_per_day"),
    }


@router.post("/analyze/societe")
async def api_analyze_societe(req: ApiSocieteRequest, request: Request,
                                key_row: dict = Depends(require_api_key)):
    """Analyse société synchrone (1-3 min). Retourne data + URLs fichiers."""
    from backend.main import _do_societe, _sync_response
    try:
        resp = _sync_response("api/v1/analyze/societe", _do_societe,
                               req.ticker, req.language or "fr", req.currency or "EUR")
        _log_usage(request, 200)
        return resp
    except Exception as e:
        _log_usage(request, 500)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/analyze/secteur")
async def api_analyze_secteur(req: ApiSecteurRequest, request: Request,
                               key_row: dict = Depends(require_api_key)):
    from backend.main import _do_secteur, _sync_response
    try:
        resp = _sync_response("api/v1/analyze/secteur", _do_secteur,
                               req.secteur, req.univers,
                               req.language or "fr", req.currency or "EUR")
        _log_usage(request, 200)
        return resp
    except Exception as e:
        _log_usage(request, 500)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/analyze/indice")
async def api_analyze_indice(req: ApiIndiceRequest, request: Request,
                               key_row: dict = Depends(require_api_key)):
    from backend.main import _do_indice, _sync_response
    try:
        resp = _sync_response("api/v1/analyze/indice", _do_indice,
                               req.indice, req.language or "fr", req.currency or "EUR")
        _log_usage(request, 200)
        return resp
    except Exception as e:
        _log_usage(request, 500)
        raise HTTPException(status_code=500, detail=str(e)[:200])
