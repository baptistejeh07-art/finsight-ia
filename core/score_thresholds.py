"""Seuils de scoring FinSight — source unique de vérité.

Avant : seuils 65 (Surpondérer) et 45 (Neutre) hardcodés dans 18+ endroits du
codebase (audit code 29/04/2026 P1 #7). Changer un seuil = 18 edits + risque
oubli + incohérence visuels/critères.

Désormais : import depuis ce module. Toute modification d'un seuil = 1 edit.

Usage :
    from core.score_thresholds import SCORE_BUY, SCORE_NEUTRAL, signal_label

    if score >= SCORE_BUY:
        ...
    label = signal_label(score)  # "Surpondérer" / "Neutre" / "Sous-pondérer"
"""

from __future__ import annotations


# =============================================================================
# Seuils canoniques
# =============================================================================
# Score FinSight 0-100 (composite Value/Growth/Quality/Momentum, 25 pts chacun).
# Seuils calibrés sur backtest sp100 10y (cf. reference_score_backtest_results.md).

SCORE_BUY: int = 65
"""Seuil minimum pour signal Surpondérer."""

SCORE_NEUTRAL: int = 45
"""Seuil minimum pour signal Neutre. En-dessous → Sous-pondérer."""


# Seuils alternatifs utilisés dans certains contextes plus stricts (top-picks,
# screening tactique). Ne pas confondre avec SCORE_BUY/SCORE_NEUTRAL standard.
SCORE_BUY_STRICT: int = 60
"""Seuil tactique (utilisé par signal global d'indice/secteur)."""

SCORE_NEUTRAL_STRICT: int = 40
"""Seuil tactique."""


# =============================================================================
# Helpers
# =============================================================================

def signal_label(score: float | int | None) -> str:
    """Retourne le label FR du signal pour un score 0-100.

    None → 'N/D' (différent de 'Sous-pondérer' qui exige une donnée valide).
    """
    if score is None:
        return "N/D"
    if score >= SCORE_BUY:
        return "Surpondérer"
    if score >= SCORE_NEUTRAL:
        return "Neutre"
    return "Sous-pondérer"


def signal_label_strict(score: float | int | None) -> str:
    """Variante tactique : seuils 60/40 au lieu de 65/45."""
    if score is None:
        return "N/D"
    if score >= SCORE_BUY_STRICT:
        return "Surpondérer"
    if score >= SCORE_NEUTRAL_STRICT:
        return "Neutre"
    return "Sous-pondérer"


def is_buy(score: float | int | None) -> bool:
    """True si score franchit le seuil Surpondérer."""
    return score is not None and score >= SCORE_BUY


def is_neutral(score: float | int | None) -> bool:
    """True si score est dans la zone Neutre [45, 65[."""
    return score is not None and SCORE_NEUTRAL <= score < SCORE_BUY


def is_underweight(score: float | int | None) -> bool:
    """True si score est sous le seuil Neutre."""
    return score is not None and score < SCORE_NEUTRAL
