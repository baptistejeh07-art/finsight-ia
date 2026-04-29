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


_JWT_WARNED = False
_JWKS_CLIENT = None


def _get_jwks_client():
    """Lazy init JWKS client (cache 1h auto). Supabase migre vers ES256
    (ECC P-256) JWT Signing Keys avec endpoint JWKS public. On utilise la
    clé publique du `kid` dans le header JWT pour vérifier.
    """
    global _JWKS_CLIENT
    if _JWKS_CLIENT is not None:
        return _JWKS_CLIENT
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not supabase_url:
        return None
    try:
        from jwt import PyJWKClient
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        _JWKS_CLIENT = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        return _JWKS_CLIENT
    except Exception as e:
        log.warning(f"[auth] JWKS init failed: {e}")
        return None


def get_current_user(authorization: Annotated[Optional[str], Header()] = None) -> Optional[dict]:
    """Valide le JWT Supabase via JWKS (ES256/ECC P-256).

    Audit secu 27/04/2026 — fix P0 #B1 : vérif signature obligatoire pour
    empêcher les forge JWT. Supabase utilise depuis 2024 des JWT Signing
    Keys ES256 (ECC P-256) avec endpoint JWKS public. La clé publique est
    récupérée et cachée 1h. Pour les anciennes installations sur secret
    HS256, set FINSIGHT_JWT_LEGACY_SECRET en env Railway.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        import jwt
        # 1. Tenter vérif ES256 via JWKS (Supabase moderne)
        jwks_client = _get_jwks_client()
        if jwks_client is not None:
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token, signing_key.key,
                    algorithms=["ES256", "RS256"],
                    audience="authenticated",
                )
                return {
                    "id": payload.get("sub"),
                    "email": payload.get("email"),
                    "role": payload.get("role", "authenticated"),
                    "exp": payload.get("exp"),
                }
            except Exception as e_jwks:
                # Token signé avec ancien HS256 → fallback secret
                log.debug(f"[auth] JWKS verify failed, try legacy: {e_jwks}")

        # 2. Fallback HS256 (legacy projects pre-2024)
        legacy_secret = (os.getenv("FINSIGHT_JWT_LEGACY_SECRET")
                         or os.getenv("SUPABASE_JWT_SECRET")
                         or os.getenv("JWT_SECRET"))
        if legacy_secret:
            payload = jwt.decode(
                token, legacy_secret, algorithms=["HS256"],
                audience="authenticated",
            )
            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role", "authenticated"),
                "exp": payload.get("exp"),
            }

        # 3. Mode dégradé final : impossible de vérifier le JWT.
        # Audit code 29/04/2026 P0 #1 : avant retournait un payload non vérifié
        # ("verify_signature": False) ce qui ouvrait une faille auth si
        # SUPABASE_URL absent ET FINSIGHT_JWT_LEGACY_SECRET vide.
        # Désormais : log.error + return None → utilisateur non authentifié.
        # Action requise : env Railway DOIT avoir SUPABASE_URL ou
        # FINSIGHT_JWT_LEGACY_SECRET défini.
        global _JWT_WARNED
        if not _JWT_WARNED:
            log.error(
                "[auth] Aucun moyen de vérifier le JWT (JWKS init failed + "
                "no FINSIGHT_JWT_LEGACY_SECRET). Tous les tokens seront rejetés. "
                "ACTION REQUISE : définir SUPABASE_URL ou FINSIGHT_JWT_LEGACY_SECRET en env Railway."
            )
            _JWT_WARNED = True
        return None
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
