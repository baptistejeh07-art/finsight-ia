"""Audit post-pipeline : détecte les data critiques manquantes/None dans le state.

Idée Baptiste 2026-04-18 : quand un tiret '—' apparaît dans l'UI, c'est qu'il y
a une data None ou vide. Pour ne pas avoir à scanner le DOM, on audit le state
backend juste avant de retourner au frontend, et on injecte une liste de
warnings consommable par l'UI (encart jaune discret) et logs (observabilité).
"""
from __future__ import annotations
from typing import Any


def _has(obj: Any, key: str) -> bool:
    """True si obj.key (ou obj[key]) existe ET n'est pas None/vide."""
    if obj is None:
        return False
    val = getattr(obj, key, None) if not isinstance(obj, dict) else obj.get(key)
    if val is None:
        return False
    if isinstance(val, (list, dict, str)) and len(val) == 0:
        return False
    if isinstance(val, (int, float)) and val == 0:
        return False  # 0 est suspect pour PE/EV/etc., on le flag
    return True


def audit_state(state: dict) -> list[dict]:
    """Scanne le state d'une analyse société. Retourne liste de warnings.

    Format : [{field, severity, hint}, ...]
    severity ∈ {'info', 'warning', 'error'}
    """
    warnings: list[dict] = []

    raw = state.get("raw_data") or {}
    ratios = state.get("ratios") or {}
    synthesis = state.get("synthesis") or {}

    # --- Synthesis ---
    if not synthesis:
        warnings.append({
            "field": "synthesis",
            "severity": "error",
            "hint": "Aucune synthèse LLM produite (tous providers KO ou JSON invalide).",
        })
    else:
        if not _has(synthesis, "target_base"):
            warnings.append({
                "field": "synthesis.target_base",
                "severity": "warning",
                "hint": "Cours cible (base case) non calculé : fourchette de valorisation incomplète.",
            })
        if not _has(synthesis, "comparable_peers"):
            warnings.append({
                "field": "synthesis.comparable_peers",
                "severity": "warning",
                "hint": "Aucun comparable peer généré : section comparatif vide.",
            })
        # Cas anormal : conviction très faible
        conv = synthesis.get("conviction") if isinstance(synthesis, dict) else getattr(synthesis, "conviction", None)
        try:
            if conv is not None and float(conv) < 0.30:
                warnings.append({
                    "field": "synthesis.conviction",
                    "severity": "info",
                    "hint": f"Conviction très faible ({conv:.0%}) — analyse à interpréter avec prudence.",
                })
        except Exception:
            pass

    # --- Ratios (au moins l'année la plus récente) ---
    years = (ratios.get("years") if isinstance(ratios, dict) else getattr(ratios, "years", None)) or {}
    if not years:
        warnings.append({
            "field": "ratios.years",
            "severity": "error",
            "hint": "Aucun ratio calculé — pipeline quant a échoué.",
        })
    else:
        latest_key = sorted(years.keys())[-1] if years else None
        latest = years.get(latest_key) if latest_key else None
        critical = ["pe_ratio", "ev_ebitda", "ebitda_margin", "roe"]
        if latest:
            missing = [k for k in critical if not _has(latest, k)]
            if len(missing) >= 2:
                warnings.append({
                    "field": "ratios.latest",
                    "severity": "warning",
                    "hint": f"Ratios critiques manquants ({', '.join(missing)}) — KPI grid incomplet.",
                })

    # --- Raw data ---
    company_info = raw.get("company_info") if isinstance(raw, dict) else getattr(raw, "company_info", None)
    if not company_info:
        warnings.append({
            "field": "raw_data.company_info",
            "severity": "error",
            "hint": "Identité société non récupérée : ticker invalide ou yfinance KO.",
        })
    elif not _has(company_info, "sector"):
        warnings.append({
            "field": "raw_data.company_info.sector",
            "severity": "info",
            "hint": "Secteur non identifié : pairs sectoriels et ETF de référence indisponibles.",
        })

    return warnings
