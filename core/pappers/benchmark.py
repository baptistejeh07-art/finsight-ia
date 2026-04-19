"""
Benchmark peers pour une PME analysée.

Stratégie :
1. Récupère N (5-10) peers SIREN via PeersClient (gratuit, NAF+taille).
2. Pour chaque peer, **tente** de récupérer ses comptes via Pappers (3 crédits/peer).
   Si budget serré : on se rabat sur les médianes sectorielles pré-stockées
   dans le profil (SectorProfile thresholds = proxys des médianes).
3. Calcule les quartiles (25%, 50%, 75%) des ratios clés.
4. Positionne la société cible dans sa quartile.

Fonction publique : `build_benchmark(target_ratios, peers_ratios, profile)`
où `peers_ratios` est une liste de `Ratios` (peut être vide → fallback thresholds).
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Iterable

from core.pappers.analytics import Ratios
from core.pappers.sector_profiles import SectorProfile, Threshold

log = logging.getLogger(__name__)


# ==============================================================================
# Structure de résultat
# ==============================================================================

@dataclass
class Quartile:
    """Position d'une valeur par rapport à un échantillon."""
    value: float | None
    q25: float | None
    q50: float | None           # médiane
    q75: float | None
    rank: str = "unknown"       # "top_25" / "above_median" / "below_median" / "bottom_25" / "unknown"


@dataclass
class BenchmarkResult:
    """Résultat complet du benchmark."""
    n_peers: int = 0
    source: str = "thresholds"   # "peers_real" | "thresholds" (médianes sectorielles du profil)
    ratios: dict[str, Quartile] = field(default_factory=dict)
    forces: list[str] = field(default_factory=list)        # ratios où la société est dans le top
    faiblesses: list[str] = field(default_factory=list)    # ratios où elle est dans le bottom


# ==============================================================================
# Helpers
# ==============================================================================

def _quartile_from_values(vals: list[float]) -> tuple[float, float, float]:
    """Q25/Q50/Q75 d'une série. Renvoie NaN-tuple si moins de 2 valeurs."""
    vals_sorted = sorted(v for v in vals if v is not None)
    n = len(vals_sorted)
    if n < 2:
        return (float("nan"), float("nan"), float("nan"))
    q25 = statistics.quantiles(vals_sorted, n=4)[0] if n >= 4 else vals_sorted[0]
    q50 = statistics.median(vals_sorted)
    q75 = statistics.quantiles(vals_sorted, n=4)[2] if n >= 4 else vals_sorted[-1]
    return q25, q50, q75


def _quartile_from_threshold(t: Threshold | None) -> tuple[float, float, float] | None:
    """Approxime Q25/Q50/Q75 à partir d'un Threshold sectoriel."""
    if t is None:
        return None
    return (t.normal_low, (t.normal_low + t.normal_high) / 2, t.normal_high)


def _rank_position(value: float | None, q25: float, q50: float, q75: float,
                   higher_is_better: bool) -> str:
    if value is None:
        return "unknown"
    if higher_is_better:
        if value >= q75:
            return "top_25"
        if value >= q50:
            return "above_median"
        if value >= q25:
            return "below_median"
        return "bottom_25"
    # lower_is_better
    if value <= q25:
        return "top_25"
    if value <= q50:
        return "above_median"
    if value <= q75:
        return "below_median"
    return "bottom_25"


# Mapping Ratio → (attribut profile, higher_is_better, label FR)
_RATIO_DEFINITIONS: list[tuple[str, str, bool, str]] = [
    ("marge_ebitda",       "marge_ebitda",       True,  "Marge EBITDA"),
    ("marge_nette",        "marge_nette",        True,  "Marge nette"),
    ("roce",               "roce",               True,  "ROCE"),
    ("roe",                "roe",                True,  "ROE"),
    ("dette_nette_ebitda", "dette_nette_ebitda", False, "Dette nette / EBITDA"),
    ("couverture_interets", "couverture_interets", True, "Couverture intérêts"),
    ("autonomie_financiere", "autonomie_financiere", True, "Autonomie financière"),
    ("bfr_jours_ca",       "bfr_jours_ca",       False, "BFR (jours de CA)"),
    ("dso_jours",          "dso_jours",          False, "DSO"),
    ("rotation_stocks",    "rotation_stocks",    True,  "Rotation stocks"),
    ("ca_par_employe",     "ca_par_employe",     True,  "CA / employé"),
    ("charges_perso_ca",   "charges_perso_ca",   False, "Charges perso / CA"),
]


# ==============================================================================
# Fonction principale
# ==============================================================================

def build_benchmark(
    target_ratios: Ratios,
    peers_ratios: Iterable[Ratios],
    profile: SectorProfile,
) -> BenchmarkResult:
    """Construit le benchmark de la cible vs peers (ou médianes sectorielles)."""
    peers_list = list(peers_ratios)
    result = BenchmarkResult(n_peers=len(peers_list))

    has_real_peers = len(peers_list) >= 2

    if has_real_peers:
        result.source = "peers_real"
    else:
        result.source = "thresholds"

    for field_name, profile_attr, higher, label in _RATIO_DEFINITIONS:
        target_val = getattr(target_ratios, field_name)

        if has_real_peers:
            peer_vals = [getattr(p, field_name) for p in peers_list]
            peer_vals = [v for v in peer_vals if v is not None]
            if len(peer_vals) >= 2:
                q25, q50, q75 = _quartile_from_values(peer_vals)
            else:
                # Fallback thresholds même si peers présents mais valeur manquante
                thr = getattr(profile, profile_attr, None)
                approx = _quartile_from_threshold(thr)
                if approx is None:
                    continue
                q25, q50, q75 = approx
        else:
            thr = getattr(profile, profile_attr, None)
            approx = _quartile_from_threshold(thr)
            if approx is None:
                continue
            q25, q50, q75 = approx

        rank = _rank_position(target_val, q25, q50, q75, higher)
        quartile = Quartile(value=target_val, q25=q25, q50=q50, q75=q75, rank=rank)
        result.ratios[field_name] = quartile

        if rank == "top_25":
            result.forces.append(label)
        elif rank == "bottom_25":
            result.faiblesses.append(label)

    return result
