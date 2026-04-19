"""
Client Pappers API v2 — identité, dirigeants, comptes annuels d'une société FR.

Coût par appel (2026-04, plan 30€/500 crédits/mois) :
- GET /entreprise (identité + dirigeants)            → 1 crédit
- GET /entreprise?comptes_complets=true              → 3 crédits
- GET /entreprise?format_publications_bodacc=true    → 1-2 crédits

Stratégie d'économie : toujours faire un SEUL appel "gros" avec tous les flags
utiles plutôt que 3 petits. Cache local sur disque (1 an — les comptes annuels
ne changent qu'une fois par an).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

log = logging.getLogger(__name__)

_BASE_URL = "https://api.pappers.fr/v2"
_DEFAULT_TIMEOUT = 20
_CACHE_DIR = Path(os.getenv("PAPPERS_CACHE_DIR", "logs/cache/pappers"))
_CACHE_TTL_DAYS = int(os.getenv("PAPPERS_CACHE_TTL_DAYS", "365"))


@dataclass
class PappersCompany:
    """Représentation normalisée d'une entreprise Pappers (ce qu'on utilise
    réellement dans le pipeline — le payload brut est stocké à part)."""

    siren: str
    denomination: str
    forme_juridique: str | None = None
    code_naf: str | None = None
    libelle_naf: str | None = None
    date_creation: str | None = None
    capital: float | None = None
    ville_siege: str | None = None
    departement: str | None = None
    effectif: str | None = None  # tranche INSEE ex: "100 à 199 salariés"
    effectif_min: int | None = None
    effectif_max: int | None = None
    chiffre_affaires_dernier: float | None = None
    exercice_dernier: str | None = None
    dirigeants: list[dict[str, Any]] = field(default_factory=list)
    comptes: list[dict[str, Any]] = field(default_factory=list)  # N dernières années
    publications_bodacc: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)  # payload complet


class PappersAPIError(Exception):
    """Erreur API Pappers (quota, clé invalide, SIREN introuvable…)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class PappersClient:
    """Client Pappers. Utilise la clé API depuis `PAPPERS_API_KEY` env var.

    Mode `use_mock=True` renvoie des fixtures locales (utile pour dev/CI sans
    consommer de crédits).
    """

    def __init__(
        self,
        api_key: str | None = None,
        use_mock: bool = False,
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("PAPPERS_API_KEY", "").strip()
        self.use_mock = use_mock or os.getenv("PAPPERS_USE_MOCK", "").lower() in {"1", "true"}
        self.timeout = timeout
        if not self.use_mock and not self.api_key:
            log.warning(
                "[PappersClient] PAPPERS_API_KEY absente et use_mock=False. "
                "Les appels réseau échoueront."
            )

    # ==========================================================================
    # Public API
    # ==========================================================================

    def fetch_company(
        self,
        siren: str,
        with_comptes: bool = True,
        with_bodacc: bool = False,
    ) -> PappersCompany:
        """Récupère l'identité + dirigeants + (optionnel) comptes + BODACC.

        `with_bodacc=False` par défaut car BODACC open data est gratuit — pas
        besoin d'appeler via Pappers payant. On conservera Pappers uniquement
        pour la partie que seul Pappers fournit proprement.
        """
        siren = _normalize_siren(siren)
        cache_key = self._cache_key("entreprise", siren, with_comptes, with_bodacc)

        cached = self._cache_read(cache_key)
        if cached is not None:
            log.info("[Pappers] cache HIT siren=%s", siren)
            return self._parse_company(cached)

        if self.use_mock:
            payload = self._mock_fixture(siren)
        else:
            payload = self._http_get(
                "/entreprise",
                params={
                    "siren": siren,
                    "format_publications_bodacc": "true" if with_bodacc else "false",
                },
            )

        self._cache_write(cache_key, payload)
        return self._parse_company(payload)

    def search_peers(
        self,
        code_naf: str,
        departement: str | None = None,
        effectif_min: int | None = None,
        effectif_max: int | None = None,
        max_results: int = 10,
    ) -> list[str]:
        """Renvoie une liste de SIREN candidats peers (pour benchmark).

        Note : cet endpoint Pappers consomme 1 crédit. Pour économiser, on
        préférera utiliser l'API INPI gratuite (`inpi_client.search_peers`)
        qui fait le même job sans crédit. Cette méthode est un fallback.
        """
        if self.use_mock:
            return [f"999{i:06d}" for i in range(max_results)]

        params: dict[str, Any] = {
            "code_naf": code_naf,
            "par_page": max_results,
            "tri": "chiffre_affaires_desc",
        }
        if departement:
            params["departement"] = departement
        if effectif_min is not None:
            params["effectif_min"] = effectif_min
        if effectif_max is not None:
            params["effectif_max"] = effectif_max

        payload = self._http_get("/recherche", params=params)
        results = payload.get("resultats", [])
        return [r.get("siren") for r in results if r.get("siren")]

    # ==========================================================================
    # HTTP
    # ==========================================================================

    def _http_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("`requests` non installé — pip install requests")

        url = f"{_BASE_URL}{path}"
        params = dict(params or {})
        params["api_token"] = self.api_key

        try:
            r = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise PappersAPIError(f"Erreur réseau Pappers : {e}") from e

        if r.status_code == 200:
            return r.json()

        # Essaie de parser le message d'erreur
        try:
            err = r.json()
            msg = err.get("error") or err.get("message") or r.text[:200]
        except Exception:
            msg = r.text[:200]

        raise PappersAPIError(
            f"Pappers {r.status_code} : {msg}",
            status_code=r.status_code,
        )

    # ==========================================================================
    # Normalisation payload → PappersCompany
    # ==========================================================================

    def _parse_company(self, payload: dict[str, Any]) -> PappersCompany:
        siege = payload.get("siege") or {}
        dep = siege.get("code_postal", "")[:2] if siege.get("code_postal") else None
        eff = payload.get("effectif") or ""
        eff_min, eff_max = _parse_effectif_tranche(eff)

        # Comptes : on essaie plusieurs clés selon la version API
        comptes = (
            payload.get("comptes")
            or payload.get("comptes_sociaux")
            or []
        )

        return PappersCompany(
            siren=payload.get("siren", ""),
            denomination=payload.get("denomination") or payload.get("nom_entreprise") or "",
            forme_juridique=payload.get("forme_juridique"),
            code_naf=payload.get("code_naf"),
            libelle_naf=payload.get("libelle_code_naf") or payload.get("domaine_activite"),
            date_creation=payload.get("date_creation"),
            capital=_float_or_none(payload.get("capital")),
            ville_siege=siege.get("ville"),
            departement=dep,
            effectif=eff or None,
            effectif_min=eff_min,
            effectif_max=eff_max,
            chiffre_affaires_dernier=_float_or_none(payload.get("chiffre_affaires")),
            exercice_dernier=payload.get("date_cloture_exercice"),
            dirigeants=payload.get("representants") or [],
            comptes=comptes,
            publications_bodacc=payload.get("publications_bodacc_sans_evenement", []) +
                                payload.get("publications_bodacc", []),
            raw=payload,
        )

    # ==========================================================================
    # Cache disque (économie crédits Pappers)
    # ==========================================================================

    def _cache_key(self, *parts: Any) -> str:
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return _CACHE_DIR / f"{key}.json"

    def _cache_read(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            st = path.stat()
            age = datetime.fromtimestamp(st.st_mtime)
            if datetime.now() - age > timedelta(days=_CACHE_TTL_DAYS):
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("[Pappers cache] read failed %s : %s", path, e)
            return None

    def _cache_write(self, key: str, payload: dict[str, Any]) -> None:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._cache_path(key).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("[Pappers cache] write failed %s : %s", key, e)

    # ==========================================================================
    # Mock fixtures (dev sans crédits)
    # ==========================================================================

    def _mock_fixture(self, siren: str) -> dict[str, Any]:
        """Fixture minimale pour dev/tests — structure représentative d'une PME
        française typique (services B2B ~20 employés)."""
        return {
            "siren": siren,
            "denomination": f"PME Test {siren}",
            "forme_juridique": "SAS",
            "code_naf": "70.22Z",
            "libelle_code_naf": "Conseil pour les affaires et autres conseils de gestion",
            "date_creation": "2015-06-12",
            "capital": 50_000,
            "siege": {
                "ville": "Paris",
                "code_postal": "75008",
            },
            "effectif": "20 à 49 salariés",
            "chiffre_affaires": 3_200_000,
            "date_cloture_exercice": "2024-12-31",
            "representants": [
                {
                    "nom": "DUPONT", "prenom": "Jean",
                    "qualite": "Président", "date_prise_de_poste": "2015-06-12",
                },
            ],
            "comptes": [
                {"date_cloture_exercice": f"202{i}-12-31",
                 "chiffre_affaires": 3_000_000 * (1.05 ** (i - 1)),
                 "resultat_net": 250_000 * (1.08 ** (i - 1))}
                for i in range(1, 6)
            ],
            "publications_bodacc": [],
        }


# ==============================================================================
# Utils
# ==============================================================================

def _normalize_siren(siren: str) -> str:
    s = "".join(c for c in str(siren) if c.isdigit())
    if len(s) == 14:  # SIRET → on tronque en SIREN
        s = s[:9]
    if len(s) != 9:
        raise ValueError(f"SIREN invalide (attendu 9 chiffres) : {siren}")
    return s


def _float_or_none(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_effectif_tranche(tranche: str) -> tuple[int | None, int | None]:
    """Parse la tranche d'effectif INSEE (formats Pappers variables) :

      "20 à 49 salariés"                        → (20, 49)
      "Entre 1 000 et 1 999 salariés"           → (1000, 1999)
      "Entre 5 000 et 9 999 salariés"           → (5000, 9999)
      "10 000 salariés et plus"                 → (10000, None)
      "0 salarié (non employeur)"               → (0, 0)
      "1 ou 2 salariés"                         → (1, 2)
    """
    if not tranche:
        return None, None
    import re
    # Retire les espaces dans les nombres ("1 000" → "1000") avant extraction
    normalized = re.sub(r"(\d)\s+(\d)", r"\1\2", tranche)
    nums = re.findall(r"\d+", normalized)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    if len(nums) == 1:
        n = int(nums[0])
        # Cas "0 salarié" (non employeur)
        if n == 0:
            return 0, 0
        # Cas "10 000 salariés et plus"
        if "plus" in tranche.lower() or "ou plus" in tranche.lower():
            return n, None
        return n, n
    return None, None
