"""Growth loop : tracking des partages LinkedIn + attribution crédits."""
from __future__ import annotations

import logging
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend._common import require_user, supabase_creds, utcnow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/shares-log", tags=["growth-loop"])


class ShareLogRequest(BaseModel):
    share_token: Optional[str] = None
    platform: str = Field(..., pattern="^(linkedin|twitter|reddit|facebook|email|copy)$")
    linkedin_post_url: Optional[str] = None


@router.post("")
async def log_share(payload: ShareLogRequest,
                     user: Annotated[dict, Depends(require_user)]):
    """Log un partage effectué par le user (LinkedIn, Reddit, etc.)."""
    surl, skey = supabase_creds()
    body = {
        "user_id": user["id"],
        "share_token": payload.share_token,
        "platform": payload.platform,
        "linkedin_post_url": payload.linkedin_post_url,
    }
    body = {k: v for k, v in body.items() if v is not None}
    try:
        r = httpx.post(
            f"{surl}/rest/v1/user_shares_log",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=body, timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Log failed: {r.text[:200]}")

        # Check : si 10 shares verified supplémentaires → attribuer +3 crédits
        await _award_credits_if_eligible(user["id"])
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log error: {e}")


@router.get("")
async def list_shares(user: Annotated[dict, Depends(require_user)]):
    """Liste des shares + progress bar credit."""
    surl, skey = supabase_creds()
    try:
        r = httpx.get(
            f"{surl}/rest/v1/user_shares_log",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            params={"user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": "100"},
            timeout=5.0,
        )
        shares = r.json() if r.status_code < 300 else []
        verified = [s for s in shares if s.get("verified")]
        credits_earned = sum(s.get("credits_awarded", 0) for s in shares)
        # Progress : 10 shares verified = 1 batch de 3 crédits
        next_batch_verified = len(verified) - (credits_earned // 3) * 10
        return {
            "shares": shares,
            "total_shares": len(shares),
            "verified_count": len(verified),
            "credits_earned": credits_earned,
            "progress_current_batch": next_batch_verified,
            "progress_target": 10,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List: {e}")


async def _award_credits_if_eligible(user_id: str) -> None:
    """Si user a atteint un nouveau palier de 10 shares verified, +3 crédits."""
    surl, skey = supabase_creds()
    try:
        r = httpx.get(
            f"{surl}/rest/v1/user_shares_log",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            params={"user_id": f"eq.{user_id}", "verified": "eq.true",
                    "select": "id,credits_awarded"},
            timeout=5.0,
        )
        shares = r.json() if r.status_code < 300 else []
        total_verified = len(shares)
        credits_already = sum(s.get("credits_awarded", 0) for s in shares)
        credits_due = (total_verified // 10) * 3
        delta = credits_due - credits_already
        if delta <= 0:
            return
        # Ajoute delta à user_preferences.bonus_analyses_credits (RPC ou direct update)
        httpx.patch(
            f"{surl}/rpc/increment_bonus_credits",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json"},
            json={"uid": user_id, "delta": delta},
            timeout=5.0,
        )
    except Exception as e:
        log.warning(f"[shares-log] award credits fail: {e}")
