"""Common helpers pour les routers backend.

Auth dependencies (require_user, require_admin, require_not_banned) +
helpers Supabase partagés. Permet aux routers d'être isolés sans importer
backend.main (qui est le gros fichier legacy).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def supabase_creds() -> tuple[str, str]:
    """Retourne (url, service_key). Raise HTTPException 500 si absent."""
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_SECRET_KEY")
           or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase non configuré")
    return url, key


def get_current_user(authorization: Annotated[Optional[str], Header()] = None) -> Optional[dict]:
    """Valide le JWT Supabase (decode sans vérif signature — cf. main.py)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
            "exp": payload.get("exp"),
        }
    except Exception as e:
        log.warning(f"[auth] JWT decode failed: {e}")
        return None


def require_user(user: Annotated[Optional[dict], Depends(get_current_user)]) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Authentification requise")
    return user


def require_admin(user: Annotated[dict, Depends(require_user)]) -> dict:
    import httpx
    url, key = supabase_creds()
    try:
        r = httpx.get(
            f"{url}/rest/v1/user_preferences?user_id=eq.{user['id']}&select=is_admin",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=3.0,
        )
        rows = r.json() if r.status_code < 300 else []
        if rows and rows[0].get("is_admin"):
            return user
    except Exception as e:
        log.warning(f"[auth] admin check failed: {e}")
    raise HTTPException(status_code=403, detail="Accès admin uniquement")
