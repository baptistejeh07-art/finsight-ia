"""Endpoints gestion des clés API publiques (auth JWT Supabase).

Les clés servent à l'API v1 (backend/api_v1.py) via header X-API-Key.
"""
from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend._common import require_user, supabase_creds, utcnow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/me/api-keys", tags=["api-keys"])


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    rate_limit_per_min: int = Field(30, ge=1, le=600)
    rate_limit_per_day: int = Field(1000, ge=1, le=1000000)


@router.post("")
async def create_key(payload: ApiKeyCreateRequest,
                      user: Annotated[dict, Depends(require_user)]):
    from backend.api_v1 import generate_api_key
    surl, skey = supabase_creds()
    key_plain, key_hash, prefix = generate_api_key()
    try:
        r = httpx.post(
            f"{surl}/rest/v1/api_keys",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=representation"},
            json={
                "user_id": user["id"], "key_prefix": prefix, "key_hash": key_hash,
                "name": payload.name,
                "rate_limit_per_min": payload.rate_limit_per_min,
                "rate_limit_per_day": payload.rate_limit_per_day,
            },
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Create failed: {r.text[:200]}")
        rows = r.json() or []
        return {"ok": True, "key": key_plain, "key_row": rows[0] if rows else None,
                "warning": "La clé complète ne sera JAMAIS réaffichée. Copie-la maintenant."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create error: {e}")


@router.get("")
async def list_keys(user: Annotated[dict, Depends(require_user)]):
    surl, skey = supabase_creds()
    try:
        r = httpx.get(
            f"{surl}/rest/v1/api_keys",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            params={"user_id": f"eq.{user['id']}",
                    "select": "id,key_prefix,name,rate_limit_per_min,rate_limit_per_day,last_used_at,revoked_at,created_at",
                    "order": "created_at.desc"},
            timeout=5.0,
        )
        return {"keys": r.json() if r.status_code < 300 else []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List: {e}")


@router.post("/{key_id}/revoke")
async def revoke_key(key_id: str,
                      user: Annotated[dict, Depends(require_user)]):
    surl, skey = supabase_creds()
    try:
        r = httpx.patch(
            f"{surl}/rest/v1/api_keys",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            params={"id": f"eq.{key_id}", "user_id": f"eq.{user['id']}"},
            json={"revoked_at": utcnow().isoformat()},
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Revoke failed: {r.text[:200]}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revoke: {e}")
