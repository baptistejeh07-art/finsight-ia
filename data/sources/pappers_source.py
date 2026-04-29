# =============================================================================
# FinSight IA — Source : Pappers API (sociétés non-cotées FR)
# data/sources/pappers_source.py
#
# Wrapper data/sources compatible avec le contrat fetch(ticker) → FinancialSnapshot
# pour intégration dans agents/agent_data.py fallback chain.
#
# Pappers indexe par SIREN (9 chiffres), pas par ticker boursier. Cette source
# est donc UNIQUEMENT activée si le "ticker" passé est un SIREN valide
# (9 chiffres) ou un format spécial "FR{siren}". Pour les tickers boursiers
# classiques (AAPL, MC.PA, etc.), retourne None — yfinance/FMP restent
# prioritaires.
#
# Couverture : ~3.5M sociétés FR non-cotées (vs ~40 cotées via yfinance CAC 40).
# Sources : INPI, BODACC, INSEE — mises à jour quotidiennes.
#
# Documentation Pappers : https://www.pappers.fr/api/documentation
# =============================================================================

from __future__ import annotations

import logging
import re
from typing import Optional

from data.models import FinancialSnapshot

log = logging.getLogger(__name__)

# Pattern SIREN : 9 chiffres exacts. Optionnel "FR" prefix accepté.
_SIREN_RE = re.compile(r"^(?:FR)?(\d{9})$", re.IGNORECASE)


def _is_siren(value: str) -> Optional[str]:
    """Retourne le SIREN normalisé (9 chiffres) si la string est un SIREN valide.

    Accepte "FR123456789" ou "123456789". Rejette les tickers boursiers.
    """
    if not value:
        return None
    m = _SIREN_RE.match(str(value).strip())
    return m.group(1) if m else None


def fetch(ticker: str) -> Optional[FinancialSnapshot]:
    """Fetch via Pappers si le ticker est un SIREN, sinon retourne None.

    Pour les sociétés cotées (ticker boursier classique), retourne None
    immédiatement → yfinance/FMP prennent la suite via la chain de fallback.

    Note : la conversion full PappersCompany → FinancialSnapshot n'est pas
    encore implémentée. Cette fonction sert de stub d'intégration pour
    Phase 3 roadmap (project_pappers_api.md). Pour l'analyse PME complète,
    utiliser directement l'endpoint backend /pme/{siren}.
    """
    siren = _is_siren(ticker)
    if not siren:
        # Ticker boursier classique → Pappers non applicable
        log.debug(f"[pappers] '{ticker}' n'est pas un SIREN — skip")
        return None

    try:
        from core.pappers.client import PappersClient, PappersAPIError
    except ImportError as e:
        log.warning(f"[pappers] core.pappers.client indisponible : {e}")
        return None

    try:
        client = PappersClient()
        company = client.fetch_company(siren, with_bodacc=False)
        if not company:
            log.warning(f"[pappers] SIREN {siren} : aucune donnée")
            return None
    except PappersAPIError as e:
        log.warning(f"[pappers] SIREN {siren} : API error {e}")
        return None
    except Exception as e:
        log.warning(f"[pappers] SIREN {siren} : exception {e}")
        return None

    # TODO Phase 3 (project_pappers_api.md) : conversion complète PappersCompany
    # → FinancialSnapshot (CompanyInfo + MarketData + 3 ans de FinancialYear).
    # Le parser INPI→Pappers existe (core/inpi/parser.py:parse_inpi_to_pappers)
    # mais la conversion inverse Pappers→FinancialSnapshot n'est pas encore
    # branchée car le pipeline standard yfinance suffit pour cotées.
    #
    # Cf endpoint backend /pme/{siren} qui fait la conversion complète pour
    # l'analyse PME dédiée (différent du pipeline analyse société classique).
    log.info(
        f"[pappers] SIREN {siren} fetched mais conversion FinancialSnapshot "
        f"non-implémentée — utiliser /pme/{siren} pour l'analyse PME complète."
    )
    return None
