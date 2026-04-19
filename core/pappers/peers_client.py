"""
Client `recherche-entreprises.api.gouv.fr` — annuaire officiel INSEE/État
français des SIREN. **Gratuit, sans clé, sans rate-limit strict** (5 req/s).

Usage : identifier des peers d'une société cible (même secteur NAF, taille
similaire, zone géo proche) pour le benchmark. Ne renvoie **PAS les comptes
détaillés** — ceux-ci viennent soit de Pappers (société cible), soit du
dataset statique `sector_medians` (médianes sectorielles INSEE ESANE).

Endpoint : https://recherche-entreprises.api.gouv.fr/
Doc : https://recherche-entreprises.api.gouv.fr/docs/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

log = logging.getLogger(__name__)

_BASE_URL = "https://recherche-entreprises.api.gouv.fr"
_DEFAULT_TIMEOUT = 15


# Tranches d'effectif INSEE — code officiel
# https://www.insee.fr/fr/information/2114066
TRANCHE_EFFECTIF = {
    "00": (0, 0),
    "01": (1, 2),
    "02": (3, 5),
    "03": (6, 9),
    "11": (10, 19),
    "12": (20, 49),
    "21": (50, 99),
    "22": (100, 199),
    "31": (200, 249),
    "32": (250, 499),
    "41": (500, 999),
    "42": (1000, 1999),
    "51": (2000, 4999),
    "52": (5000, 9999),
    "53": (10000, None),
}


@dataclass
class PeerCandidate:
    """Résultat minimal d'une recherche peer (identité, pas de comptes)."""

    siren: str
    denomination: str
    code_naf: str | None = None
    tranche_effectif: str | None = None
    effectif_min: int | None = None
    effectif_max: int | None = None
    code_postal: str | None = None
    departement: str | None = None
    ville: str | None = None
    date_creation: str | None = None
    est_actif: bool = True


class PeersAPIError(Exception):
    """Erreur API recherche-entreprises."""


class PeersClient:
    """Client de recherche de SIREN peers.

    Exemples :
        client.search_by_naf("69.20Z", max_results=10)
        client.search_peers_like(company, max_results=10)
    """

    def __init__(self, timeout: int = _DEFAULT_TIMEOUT):
        self.timeout = timeout

    # ==========================================================================
    # Public API
    # ==========================================================================

    def search_by_naf(
        self,
        code_naf: str,
        departement: str | None = None,
        tranche_effectif: str | None = None,
        max_results: int = 25,
    ) -> list[PeerCandidate]:
        """Recherche des SIREN dans un secteur d'activité donné.

        `tranche_effectif` : code INSEE à 2 chiffres (voir TRANCHE_EFFECTIF).
        `departement` : 2-3 chiffres (ex: "75", "33", "971").
        """
        params: dict[str, Any] = {
            "activite_principale": code_naf,
            "per_page": min(max_results, 25),
            "etat_administratif": "A",  # actifs uniquement
        }
        if departement:
            params["departement"] = departement
        if tranche_effectif:
            params["tranche_effectif_salarie"] = tranche_effectif

        payload = self._http_get("/search", params=params)
        results = payload.get("results", [])
        return [self._parse_peer(r) for r in results]

    def search_peers_like(
        self,
        code_naf: str,
        effectif_min: int | None = None,
        effectif_max: int | None = None,
        departement: str | None = None,
        max_results: int = 10,
        exclude_siren: str | None = None,
    ) -> list[PeerCandidate]:
        """Recherche des peers d'une société cible (même NAF + taille proche).

        L'API `recherche-entreprises.api.gouv.fr` traite `departement` et
        `tranche_effectif_salarie` comme boosts de scoring plutôt que filtres
        durs. On fetch donc un gros batch (100) puis on **filtre côté client**
        par tranche + département pour ne garder que les vrais peers.
        """
        tranche_target = _find_tranche(effectif_min, effectif_max) if effectif_min is not None else None

        # Fetch large batch (le NAF reste un vrai filtre, lui)
        naf_attempts = [code_naf]
        if "." in code_naf and len(code_naf) >= 6:  # ex: 69.20Z → 69.20
            naf_attempts.append(code_naf.rsplit(".", 1)[0][:5] if len(code_naf) > 5 else code_naf)

        all_candidates: list[PeerCandidate] = []
        for naf in naf_attempts:
            if len(all_candidates) >= 100:
                break
            try:
                batch = self._fetch_bulk(naf, per_page=25, max_pages=4)
                all_candidates.extend(batch)
            except PeersAPIError as e:
                log.warning("[peers] fetch NAF=%s failed: %s", naf, e)

        # Dédupe
        seen: dict[str, PeerCandidate] = {}
        for p in all_candidates:
            if p.siren and p.siren != exclude_siren and p.est_actif:
                seen.setdefault(p.siren, p)
        candidates = list(seen.values())

        # Filtrage progressif (client-side) : on essaie du + strict au + large
        def _match_tranche(p: PeerCandidate) -> bool:
            return tranche_target is None or p.tranche_effectif == tranche_target

        def _match_dept(p: PeerCandidate) -> bool:
            return departement is None or p.departement == departement

        # Niveau 1 : même tranche + même département
        level1 = [p for p in candidates if _match_tranche(p) and _match_dept(p)]
        # Niveau 2 : même tranche (ignorer dept)
        level2 = [p for p in candidates if _match_tranche(p)]
        # Niveau 3 : tranche adjacente (±1)
        def _tranche_close(p: PeerCandidate) -> bool:
            if tranche_target is None:
                return True
            try:
                t = int(p.tranche_effectif or "99")
                target = int(tranche_target)
                return abs(t - target) <= 1
            except (ValueError, TypeError):
                return False
        level3 = [p for p in candidates if _tranche_close(p)]

        # Consolide sans doublon
        result: list[PeerCandidate] = []
        seen_sirens: set[str] = set()
        for level in (level1, level2, level3, candidates):
            for p in level:
                if p.siren not in seen_sirens:
                    seen_sirens.add(p.siren)
                    result.append(p)
                    if len(result) >= max_results:
                        return result

        return result[:max_results]

    def _fetch_bulk(
        self,
        code_naf: str,
        per_page: int = 25,
        max_pages: int = 4,
    ) -> list[PeerCandidate]:
        """Pagination pour récupérer un gros lot de candidats peers."""
        all_results: list[PeerCandidate] = []
        for page in range(1, max_pages + 1):
            try:
                payload = self._http_get(
                    "/search",
                    params={
                        "activite_principale": code_naf,
                        "per_page": per_page,
                        "page": page,
                        "etat_administratif": "A",
                    },
                )
            except PeersAPIError:
                break
            items = payload.get("results", [])
            if not items:
                break
            all_results.extend(self._parse_peer(r) for r in items)
            total = payload.get("total_results", 0)
            if len(all_results) >= total:
                break
        return all_results

    # ==========================================================================
    # HTTP
    # ==========================================================================

    def _http_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("`requests` non installé")
        url = f"{_BASE_URL}{path}"
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise PeersAPIError(f"Erreur réseau : {e}") from e
        if r.status_code != 200:
            raise PeersAPIError(f"HTTP {r.status_code} : {r.text[:200]}")
        return r.json()

    # ==========================================================================
    # Parsing
    # ==========================================================================

    def _parse_peer(self, payload: dict[str, Any]) -> PeerCandidate:
        siege = payload.get("siege") or {}
        tranche = (
            siege.get("tranche_effectif_salarie")
            or payload.get("tranche_effectif_salarie")
        )
        eff_min, eff_max = TRANCHE_EFFECTIF.get(str(tranche or ""), (None, None))

        etat = siege.get("etat_administratif") or payload.get("etat_administratif") or "A"

        return PeerCandidate(
            siren=payload.get("siren", ""),
            denomination=payload.get("nom_complet") or payload.get("nom_raison_sociale") or "",
            code_naf=siege.get("activite_principale") or payload.get("activite_principale"),
            tranche_effectif=str(tranche) if tranche else None,
            effectif_min=eff_min,
            effectif_max=eff_max,
            code_postal=siege.get("code_postal"),
            departement=siege.get("departement"),
            ville=siege.get("libelle_commune"),
            date_creation=siege.get("date_creation") or payload.get("date_creation"),
            est_actif=(etat == "A"),
        )


# ==============================================================================
# Utils
# ==============================================================================

def _find_tranche(eff_min: int | None, eff_max: int | None) -> str | None:
    """Trouve le code INSEE de tranche correspondant à la fourchette min/max."""
    if eff_min is None:
        return None
    # Match exact sur min
    for code, (lo, hi) in TRANCHE_EFFECTIF.items():
        if lo == eff_min:
            return code
    # Fallback : trouver la tranche qui contient eff_min
    for code, (lo, hi) in TRANCHE_EFFECTIF.items():
        if hi is None:
            if eff_min >= lo:
                return code
        elif lo <= eff_min <= hi:
            return code
    return None
