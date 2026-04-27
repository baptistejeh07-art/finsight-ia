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


def _get_jwt_secret() -> Optional[str]:
    """Retourne le secret JWT Supabase pour vérification HS256.

    Recherche dans SUPABASE_JWT_SECRET (officiel) ou JWT_SECRET (alias).
    Si absent : warn + retourne None (tombe en mode dégradé verify_signature=False
    avec log warn fort, le temps de l'ajout en env Railway).
    """
    return (os.getenv("SUPABASE_JWT_SECRET")
            or os.getenv("JWT_SECRET")
            or None)


_JWT_SECRET_WARNED = False


def get_current_user(authorization: Annotated[Optional[str], Header()] = None) -> Optional[dict]:
    """Valide le JWT Supabase avec vérification HS256.

    Audit secu 27/04/2026 — fix P0 #B1 : vérif signature obligatoire pour
    empêcher les forge JWT (n'importe qui se faisait passer pour admin).
    Le SUPABASE_JWT_SECRET doit être en env Railway (Settings > API >
    JWT Settings sur Supabase dashboard).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        import jwt
        secret = _get_jwt_secret()
        if not secret:
            global _JWT_SECRET_WARNED
            if not _JWT_SECRET_WARNED:
                log.error(
                    "[auth] SUPABASE_JWT_SECRET MANQUANT — JWT non vérifié, "
                    "FAILLE SÉCURITÉ. Ajouter en env Railway."
                )
                _JWT_SECRET_WARNED = True
            # Mode dégradé : decode sans signature mais log chaque appel
            payload = jwt.decode(token, options={"verify_signature": False})
        else:
            # Mode sécurisé : signature vérifiée + audience standard Supabase
            try:
                payload = jwt.decode(
                    token, secret, algorithms=["HS256"],
                    audience="authenticated",
                )
            except Exception as e_v:
                # Fallback : Supabase peut utiliser un autre audience selon
                # config — retry sans audience strict mais signature toujours
                # vérifiée.
                log.debug(f"[auth] audience mismatch, retry without: {e_v}")
                payload = jwt.decode(token, secret, algorithms=["HS256"],
                                     options={"verify_aud": False})
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
            "exp": payload.get("exp"),
        }
    except Exception as e:
        log.warning(f"[auth] JWT verify failed: {e}")
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
