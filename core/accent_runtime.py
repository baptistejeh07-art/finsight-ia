"""
core/accent_runtime.py — Restauration d'accents pour les sorties LLM.

Mistral small (fallback FinSight) retourne souvent du texte sans accents
("sous-evalue" au lieu de "sous-évalué", "generee" au lieu de "générée").

Ce module importe le dict REPLACEMENTS depuis tools/restore_accents.py
(qui fait du bulk refactor sur les writers) et expose une fonction
runtime `restore_accents(text)` à appliquer sur chaque sortie LLM avant
insertion dans les PDF/PPTX.

Usage :
    from core.accent_runtime import restore_accents
    llm_out = _llm.generate(prompt=...)
    llm_out = restore_accents(llm_out)
"""
from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

# ============================================================================
# Import du dict REPLACEMENTS depuis tools/restore_accents.py
# On charge le module dynamiquement pour éviter les dépendances circulaires.
# ============================================================================

@lru_cache(maxsize=1)
def _load_replacements() -> dict[str, str]:
    """Charge le dict REPLACEMENTS depuis tools/restore_accents.py (1 fois)."""
    _root = Path(__file__).resolve().parent.parent
    _tools = _root / "tools"
    if str(_tools) not in sys.path:
        sys.path.insert(0, str(_tools))
    try:
        import restore_accents as _ra_module  # type: ignore
        return dict(_ra_module.REPLACEMENTS)
    except Exception:
        # Fallback si le module n'est pas dispo : dict minimal avec les
        # erreurs LLM les plus fréquentes observées en production.
        return {
            "sous-evalue":  "sous-évalué",
            "sous-evaluee": "sous-évaluée",
            "sur-evalue":   "sur-évalué",
            "sur-evaluee":  "sur-évaluée",
            "evolue":       "évolue",
            "generee":      "générée",
            "generees":     "générées",
            "presente":     "présente",
            "expliquee":    "expliquée",
            "drivee":       "drivée",
            "beneficiaire": "bénéficiaire",
            "mediane":      "médiane",
            "resilience":   "résilience",
            "cyclicite":    "cyclicité",
        }


# ============================================================================
# Regex compilé (1 fois) : alternance de toutes les formes non accentuées
# avec frontières de mot pour éviter les matches partiels.
# ============================================================================

@lru_cache(maxsize=1)
def _compiled_pattern() -> tuple[re.Pattern, dict[str, str]]:
    reps = _load_replacements()
    # Trier du plus long au plus court pour matcher avant les sous-chaînes
    keys = sorted(reps.keys(), key=len, reverse=True)
    # Escape regex special chars
    alt = "|".join(re.escape(k) for k in keys)
    # Pas de word-boundary autour des composés (ex: "sous-evalue") car '-' n'est
    # pas un word char : on utilise (?<![a-zA-ZàâçéèêëîïôùûüÿÀÂÇÉÈÊËÎÏÔÙÛÜŸ])
    # pour lookbehind et lookahead strict.
    pat = re.compile(
        r"(?<![A-Za-zÀ-ÿ])(" + alt + r")(?![A-Za-zÀ-ÿ])",
        flags=re.IGNORECASE,
    )
    return pat, reps


def restore_accents(text: str) -> str:
    """Restaure les accents dans un texte LLM.

    Remplacement mot à mot case-insensitive avec frontières de mot.
    Préserve la casse originale si la forme accentuée existe dans le dict
    sous une seule casse (lowercase par défaut).

    Returns:
        Texte avec accents restaurés. Si text est vide ou None, retourne "".
    """
    if not text:
        return text or ""
    pat, reps = _compiled_pattern()

    def _sub(m: re.Match) -> str:
        word = m.group(1)
        key = word.lower()
        if key in reps:
            rep = reps[key]
            # Préserver casse : si mot original commence par majuscule, capitaliser
            if word and word[0].isupper():
                return rep[0].upper() + rep[1:]
            return rep
        return word

    return pat.sub(_sub, text)
