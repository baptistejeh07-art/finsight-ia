"""Client INPI RNE — Registre National des Entreprises.

Accès gratuit aux données des sociétés françaises (alternative à Pappers payant
= 30€/500 crédits/mois). Identité, dirigeants, activité, comptes annuels si
déposés publiquement.

Workflow authentification :
  1. POST https://registre-national-entreprises.inpi.fr/api/sso/login
     body: {"username": email, "password": pwd}
     → renvoie JSON avec sessionToken (JWT 24h)
  2. Requêtes API : Authorization: Bearer <JWT>
     ex: GET /api/companies?siren[]=552032534
  3. Si 401 → re-login automatique.

Env vars requises :
  INPI_USERNAME = email du compte RNE (ex: baptiste.jeh07@gmail.com)
  INPI_PASSWORD = mot de passe

Cache JWT 23h dans logs/cache/inpi_token.json (évite login à chaque requête).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)

_BASE_URL = "https://registre-national-entreprises.inpi.fr"
_LOGIN_PATH = "/api/sso/login"
_COMPANIES_PATH = "/api/companies"

# Cache JWT sur disque pour survivre aux redémarrages
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_TOKEN_CACHE_FILE = _CACHE_DIR / "inpi_token.json"

# JWT valide 24h côté INPI — on refresh à 23h pour marge de sécurité
_TOKEN_TTL_SECONDS = 23 * 3600


class InpiClient:
    """Client INPI RNE avec gestion auto du JWT.

    Usage :
        client = InpiClient()
        data = client.get_company("552032534")
    """

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None,
                 timeout: float = 15.0):
        self.username = username or os.getenv("INPI_USERNAME") or ""
        self.password = password or os.getenv("INPI_PASSWORD") or ""
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        # Charge cache disque au startup
        self._load_token_cache()

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.password)

    def _load_token_cache(self) -> None:
        if not _TOKEN_CACHE_FILE.exists():
            return
        try:
            data = json.loads(_TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
            expires = float(data.get("expires_at", 0))
            if expires > time.time():
                self._token = data.get("token")
                self._token_expires_at = expires
                log.debug(f"[inpi] JWT chargé depuis cache (expire dans {int((expires - time.time())/3600)}h)")
        except Exception as e:
            log.debug(f"[inpi] cache JWT illisible : {e}")

    def _save_token_cache(self) -> None:
        try:
            _TOKEN_CACHE_FILE.write_text(json.dumps({
                "token": self._token,
                "expires_at": self._token_expires_at,
                "saved_at": datetime.utcnow().isoformat(),
            }), encoding="utf-8")
        except Exception as e:
            log.debug(f"[inpi] save cache failed : {e}")

    def _login(self) -> bool:
        """POST /api/sso/login → récupère le JWT."""
        if not self.is_configured:
            log.warning("[inpi] credentials non configurés (INPI_USERNAME/INPI_PASSWORD)")
            return False
        try:
            r = httpx.post(
                f"{_BASE_URL}{_LOGIN_PATH}",
                json={"username": self.username, "password": self.password},
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            if r.status_code != 200:
                log.error(f"[inpi] login failed {r.status_code}: {r.text[:200]}")
                return False
            data = r.json()
            token = data.get("token") or data.get("sessionToken")
            if not token:
                log.error(f"[inpi] login OK mais pas de token : {list(data.keys())}")
                return False
            self._token = token
            self._token_expires_at = time.time() + _TOKEN_TTL_SECONDS
            self._save_token_cache()
            log.info(f"[inpi] login OK — JWT caché (valide {_TOKEN_TTL_SECONDS//3600}h)")
            return True
        except Exception as e:
            log.error(f"[inpi] login exception : {e}")
            return False

    def _ensure_token(self) -> bool:
        """Assure un JWT valide : login si absent ou expiré."""
        if self._token and time.time() < self._token_expires_at:
            return True
        return self._login()

    def _request(self, method: str, path: str, *, params: Optional[dict] = None,
                  retry_on_401: bool = True) -> Optional[dict]:
        if not self._ensure_token():
            return None
        try:
            r = httpx.request(
                method,
                f"{_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                params=params,
                timeout=self.timeout,
            )
            if r.status_code == 401 and retry_on_401:
                # Token invalide — force re-login
                log.info("[inpi] 401 — re-login")
                self._token = None
                self._token_expires_at = 0
                return self._request(method, path, params=params, retry_on_401=False)
            if r.status_code >= 400:
                log.warning(f"[inpi] HTTP {r.status_code} sur {path} : {r.text[:200]}")
                return None
            return r.json()
        except Exception as e:
            log.warning(f"[inpi] request {path} exception : {e}")
            return None

    def get_company(self, siren: str) -> Optional[dict]:
        """Récupère les données complètes d'une société par SIREN.

        Returns : dict brut INPI (formality, dirigeants, etablissements, etc.)
                  ou None si erreur/non trouvé.
        """
        siren = str(siren).strip().replace(" ", "")
        if not siren.isdigit() or len(siren) != 9:
            log.warning(f"[inpi] SIREN invalide : {siren}")
            return None
        result = self._request("GET", _COMPANIES_PATH, params={"siren[]": siren, "pageSize": 1})
        if isinstance(result, list) and result:
            return result[0]
        return None


def fetch_pme_inpi(siren: str) -> Optional[dict]:
    """Point d'entrée rapide. Retourne données brutes INPI pour un SIREN."""
    client = InpiClient()
    if not client.is_configured:
        log.debug("[inpi] non configuré — skip")
        return None
    return client.get_company(siren)
