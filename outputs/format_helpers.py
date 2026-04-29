"""Helpers de formatage centralisés FR — source unique de vérité.

Avant : `_fmt_x`, `_fmt_pct`, `_fmt_eur`, `_fmt_mds` dupliqués dans 6-10
fichiers writers. Conséquence : chaque bug FR (décimale US, espace
manquant avant %, etc.) devait être fixé 4-10 fois (cf. session
2026-04-29 où la même régression a été fixée sur sect/indice/société/
cmp_societe/cmp_secteur/cmp_indice — 6 commits pour le même pattern).

Désormais : import depuis ce module. Bug fixé une seule fois propage
partout. Audit code 29/04/2026 P2 #15.

Conventions FR :
- Virgule décimale (12,3 au lieu de 12.3)
- Espace insécable avant `%` (12,3 % au lieu de 12,3%)
- Espace milliers (1 234 au lieu de 1,234)
- "—" (em dash) pour valeurs manquantes (pas "N/A" ou "-")

Usage :
    from outputs.format_helpers import fmt_x, fmt_pct, fmt_eur, fmt_mds, MISSING
"""

from __future__ import annotations

from typing import Any, Optional


# Marker visuel cohérent pour valeurs manquantes / inexploitables
MISSING: str = "—"  # em dash —


def _safe_float(v: Any) -> Optional[float]:
    """Cast safe en float. Retourne None pour None / "" / "N/A" / NaN / non-numérique."""
    if v is None:
        return None
    try:
        f = float(v)
        # NaN check : float("nan") != float("nan")
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


# =============================================================================
# Multiples (x)
# =============================================================================

def fmt_x(v: Any, d: int = 1) -> str:
    """Formatte un multiple : `12,3x`. None / invalide → MISSING.

    >>> fmt_x(12.34)
    '12,3x'
    >>> fmt_x(None)
    '—'
    >>> fmt_x(2.5, d=2)
    '2,50x'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    return f"{f:.{d}f}x".replace(".", ",")


# =============================================================================
# Pourcentages (%)
# =============================================================================

def fmt_pct(v: Any, d: int = 1, sign: bool = False, mult: bool = False) -> str:
    """Formatte un pourcentage : `12,3 %` (avec espace insécable avant %).

    Args:
        v : valeur numérique
        d : nombre de décimales (défaut 1)
        sign : si True, prefixe `+` pour positif (`+12,3 %`)
        mult : si True, multiplie la valeur par 100 (utile pour ratios stockés
               en décimal : 0.12 → "12,0 %")

    >>> fmt_pct(12.34)
    '12,3 %'
    >>> fmt_pct(0.123, mult=True)
    '12,3 %'
    >>> fmt_pct(5.7, sign=True)
    '+5,7 %'
    >>> fmt_pct(None)
    '—'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    if mult:
        f *= 100
    fmt = f"{{:+.{d}f}}" if sign else f"{{:.{d}f}}"
    return fmt.format(f).replace(".", ",") + " %"


# =============================================================================
# Devise / valeurs monétaires
# =============================================================================

def fmt_eur(v: Any, d: int = 0, currency: str = "€") -> str:
    """Formatte un montant : `1 234 €` (espace milliers + devise).

    >>> fmt_eur(1234)
    '1 234 €'
    >>> fmt_eur(1234.56, d=2)
    '1 234,56 €'
    >>> fmt_eur(None)
    '—'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    formatted = f"{f:,.{d}f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}"


def fmt_mds(v: Any, currency: str = "€", threshold: float = 1e9) -> str:
    """Formatte un grand montant : `1,2 Mds €` ou `850 M €`.

    Adaptatif : >= 1 Md → "X,X Mds devise" ; sinon "X M devise".

    >>> fmt_mds(1.5e9)
    '1,5 Mds €'
    >>> fmt_mds(8.5e8)
    '850 M €'
    >>> fmt_mds(None)
    '—'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    if abs(f) >= threshold:
        # Milliards
        return f"{f / 1e9:.1f} Mds {currency}".replace(".", ",")
    # Millions
    return f"{f / 1e6:.0f} M {currency}"


def fmt_mds_compact(v: Any, currency: str = "€") -> str:
    """Variante compacte sans devise : `1,2 Mds`. Utile pour KPI tiles.

    >>> fmt_mds_compact(1.5e9)
    '1,5 Mds'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    if abs(f) >= 100e9:
        return f"{f / 1e9:.0f} Mds"
    if abs(f) >= 1e9:
        return f"{f / 1e9:.1f} Mds".replace(".", ",")
    return f"{f / 1e6:.0f} M"


# =============================================================================
# Nombres bruts
# =============================================================================

def fmt_num(v: Any, d: int = 1) -> str:
    """Formatte un nombre simple : `1,5`. Pour ratios sans unité.

    >>> fmt_num(1.5)
    '1,5'
    >>> fmt_num(1.567, d=2)
    '1,57'
    >>> fmt_num(None)
    '—'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    return f"{f:.{d}f}".replace(".", ",")


def fmt_int(v: Any) -> str:
    """Formatte un entier avec espace milliers : `1 234`.

    >>> fmt_int(1234)
    '1 234'
    >>> fmt_int(None)
    '—'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    return f"{int(f):,}".replace(",", " ")


# =============================================================================
# Score FinSight
# =============================================================================

def fmt_score(v: Any, max_value: int = 100) -> str:
    """Formatte un score : `72/100`. None → MISSING.

    >>> fmt_score(72)
    '72/100'
    >>> fmt_score(None)
    '—'
    """
    f = _safe_float(v)
    if f is None:
        return MISSING
    return f"{int(f)}/{max_value}"


# =============================================================================
# Tests doctest
# =============================================================================

if __name__ == "__main__":
    import doctest
    doctest.testmod(verbose=True)
