"""
Client BODACC open data (gratuit, sans clé).

Source : https://bodacc-datadila.opendatasoft.com/api/records/1.0/search/
Dataset : `annonces-commerciales`.

Renvoie les publications BODACC d'un SIREN : procédures collectives, dépôts
de comptes, modifications dirigeants, radiations, etc.

Intégration au scoring santé :
- Procédure collective récente (< 3 ans) → -30 points
- Procédure collective plus ancienne → -10 points
- Radiation → -50 points (société cessée)
- Dépôts de comptes réguliers → +5 points (transparence)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

try:
    import requests
except ImportError:
    requests = None

log = logging.getLogger(__name__)

_BASE = "https://bodacc-datadila.opendatasoft.com/api/records/1.0/search/"
_DATASET = "annonces-commerciales"


# Catégories d'avis à détecter
_PROC_COLLECTIVES = {
    "Procédure de sauvegarde",
    "Redressement judiciaire",
    "Liquidation judiciaire",
    "Dépôt d'état de cessation de paiement",
    "Jugement de clôture",
    "Plan de continuation",
    "Plan de cession",
}


@dataclass
class BodaccAnnonce:
    date_parution: str           # YYYY-MM-DD
    famille: str                 # ex: "Procédure collective", "Dépôts des comptes"
    type_avis: str | None = None
    contenu: str | None = None   # texte partiel


@dataclass
class BodaccSummary:
    siren: str
    total_annonces: int = 0
    procedures_collectives: list[BodaccAnnonce] = field(default_factory=list)
    derniere_procedure: str | None = None       # date YYYY-MM-DD, ou None
    dernier_depot_comptes: str | None = None
    radie: bool = False
    modifications_recentes: int = 0              # dans les 2 ans
    bodacc_score_penalty: float = 0.0            # pénalité (0 = OK, -50 = très mauvais)


# ==============================================================================
# Client
# ==============================================================================

class BodaccClient:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch(self, siren: str, max_records: int = 50) -> BodaccSummary:
        siren = str(siren).strip()
        summary = BodaccSummary(siren=siren)
        if requests is None:
            log.warning("[bodacc] requests non installé")
            return summary

        params = {
            "dataset": _DATASET,
            "q": f"registre:{siren}",
            "rows": max_records,
            "sort": "-dateparution",
        }
        try:
            r = requests.get(_BASE, params=params, timeout=self.timeout)
            if r.status_code != 200:
                log.warning("[bodacc] HTTP %s pour siren %s", r.status_code, siren)
                return summary
            data = r.json()
        except Exception as e:
            log.warning("[bodacc] error: %s", e)
            return summary

        records = data.get("records", [])
        summary.total_annonces = data.get("nhits", 0)

        today = date.today()
        for rec in records:
            f = rec.get("fields", {})
            dp = f.get("dateparution") or ""
            famille = f.get("familleavis_lib") or f.get("familleavis") or ""
            type_avis = f.get("typeavis_lib") or f.get("typeavis")
            contenu = f.get("listepersonnes") or f.get("jugement") or ""

            annonce = BodaccAnnonce(
                date_parution=dp,
                famille=famille,
                type_avis=type_avis,
                contenu=contenu[:300] if isinstance(contenu, str) else "",
            )

            famille_lower = famille.lower()

            # Procédures collectives
            is_proc = any(
                p.lower() in famille_lower or p.lower() in (type_avis or "").lower()
                for p in _PROC_COLLECTIVES
            ) or "procédure" in famille_lower or "proc�dure" in famille_lower.encode('utf-8').decode('latin-1', errors='ignore')
            if is_proc:
                summary.procedures_collectives.append(annonce)
                if summary.derniere_procedure is None or dp > summary.derniere_procedure:
                    summary.derniere_procedure = dp

            # Dépôts de comptes
            if "dépôt" in famille_lower or "depot" in famille_lower:
                if summary.dernier_depot_comptes is None or dp > summary.dernier_depot_comptes:
                    summary.dernier_depot_comptes = dp

            # Radiation
            if "radiation" in famille_lower:
                summary.radie = True

            # Modifications récentes
            if "modification" in famille_lower:
                try:
                    rec_date = datetime.strptime(dp, "%Y-%m-%d").date()
                    age = (today - rec_date).days / 365
                    if age < 2:
                        summary.modifications_recentes += 1
                except ValueError:
                    pass

        # Calcul pénalité BODACC pour le scoring santé
        penalty = 0.0
        if summary.radie:
            penalty -= 50.0
        if summary.derniere_procedure:
            try:
                proc_date = datetime.strptime(summary.derniere_procedure, "%Y-%m-%d").date()
                age_years = (today - proc_date).days / 365
                if age_years < 3:
                    penalty -= 30.0
                elif age_years < 7:
                    penalty -= 10.0
            except ValueError:
                penalty -= 20.0
        if summary.modifications_recentes > 5:
            penalty -= 5.0
        summary.bodacc_score_penalty = penalty

        return summary


def compute_bodacc_score(summary: BodaccSummary) -> float:
    """Score BODACC 0-100 à intégrer au score santé.

    Base : 100 (tout va bien), on applique les pénalités.
    """
    return max(0.0, 100.0 + summary.bodacc_score_penalty)
