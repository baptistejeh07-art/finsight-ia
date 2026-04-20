"""Endpoints de partage public d'analyses (URL read-only).

Migration 014 : analysis_shares.
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend._common import require_user, supabase_creds, utcnow

log = logging.getLogger(__name__)
router = APIRouter(tags=["share"])


class ShareCreateRequest(BaseModel):
    history_id: str
    expires_in_days: Optional[int] = None


def _gen_token(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


@router.post("/share/create")
async def share_create(payload: ShareCreateRequest,
                        user: Annotated[dict, Depends(require_user)]):
    surl, skey = supabase_creds()
    try:
        r = httpx.get(
            f"{surl}/rest/v1/analyses_history?id=eq.{payload.history_id}&user_id=eq.{user['id']}&select=id",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            timeout=5.0,
        )
        if r.status_code >= 300 or not (r.json() or []):
            raise HTTPException(status_code=404, detail="Analyse introuvable")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lookup error: {e}")

    token = _gen_token(16)
    expires_at = None
    if payload.expires_in_days and payload.expires_in_days > 0:
        expires_at = (utcnow() + timedelta(days=payload.expires_in_days)).isoformat()

    body = {"token": token, "history_id": payload.history_id, "user_id": user["id"]}
    if expires_at:
        body["expires_at"] = expires_at

    try:
        r = httpx.post(
            f"{surl}/rest/v1/analysis_shares",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=body, timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Insert failed: {r.text[:200]}")
        return {"ok": True, "token": token, "expires_at": expires_at}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert error: {e}")


@router.get("/share/{token}")
async def share_get(token: str):
    surl, skey = supabase_creds()
    h = {"apikey": skey, "Authorization": f"Bearer {skey}"}
    try:
        r = httpx.get(
            f"{surl}/rest/v1/analysis_shares?token=eq.{token}&select=id,history_id,user_id,expires_at,revoked_at,views_count",
            headers=h, timeout=5.0,
        )
        rows = r.json() if r.status_code < 300 else []
        if not rows:
            raise HTTPException(status_code=404, detail="Lien introuvable")
        share = rows[0]
        if share.get("revoked_at"):
            raise HTTPException(status_code=410, detail="Lien révoqué")
        if share.get("expires_at"):
            try:
                exp = datetime.fromisoformat(share["expires_at"].replace("Z", "+00:00"))
                if exp < utcnow().replace(tzinfo=exp.tzinfo):
                    raise HTTPException(status_code=410, detail="Lien expiré")
            except (ValueError, TypeError):
                pass

        r2 = httpx.get(
            f"{surl}/rest/v1/analyses_history?id=eq.{share['history_id']}&select=id,kind,label,display_name,ticker,payload,created_at",
            headers=h, timeout=8.0,
        )
        rows2 = r2.json() if r2.status_code < 300 else []
        if not rows2:
            raise HTTPException(status_code=404, detail="Analyse introuvable")
        analysis = rows2[0]

        try:
            httpx.patch(
                f"{surl}/rest/v1/analysis_shares?id=eq.{share['id']}",
                headers={**h, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json={"views_count": int(share.get("views_count") or 0) + 1},
                timeout=3.0,
            )
        except Exception:
            pass

        return {
            "kind": analysis.get("kind"),
            "label": analysis.get("display_name") or analysis.get("label"),
            "ticker": analysis.get("ticker"),
            "created_at": analysis.get("created_at"),
            "payload": analysis.get("payload"),
            "views_count": int(share.get("views_count") or 0) + 1,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetch error: {e}")


@router.delete("/share/{token}")
async def share_revoke(token: str,
                        user: Annotated[dict, Depends(require_user)]):
    surl, skey = supabase_creds()
    try:
        r = httpx.patch(
            f"{surl}/rest/v1/analysis_shares?token=eq.{token}&user_id=eq.{user['id']}",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={"revoked_at": utcnow().isoformat()},
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Revoke failed: {r.text[:200]}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revoke error: {e}")
