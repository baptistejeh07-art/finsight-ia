"""Génère les commentaires narratifs PME via LLM.

Une passe : envoie l'analyse + benchmark + chiffres clés, récupère un JSON
avec 8 commentaires (sig, rentabilite, solidite, efficacite, croissance,
scoring, bankabilite, synthese).

Règle stricte : PAS DE FALLBACK DÉTERMINISTE. Si le LLM échoue ou retourne
du JSON invalide, renvoyer {} pour ne rien afficher plutôt qu'un texte
générique qui ferait passer pour de l'analyse ce qui n'en est pas.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

SECTIONS = (
    "sig",
    "rentabilite",
    "solidite",
    "efficacite",
    "croissance",
    "scoring",
    "bankabilite",
    "synthese",
)


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f} %".replace(".", ",")


def _fmt_eur_m(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f} M€".replace(".", ",")
    if abs(v) >= 1_000:
        return f"{v / 1_000:.0f} k€"
    return f"{v:.0f} €"


def _build_context_bullet(
    denomination: str,
    code_naf: str | None,
    libelle_naf: str | None,
    analysis: Any,
    benchmark: Any,
    yearly_accounts: list,
) -> str:
    """Résumé structuré injecté au prompt LLM (<500 tokens)."""
    latest = sorted(yearly_accounts, key=lambda a: a.annee)[-1] if yearly_accounts else None
    sig = latest.sig if latest else None
    ratios = latest.ratios if latest else None

    lignes = [
        f"Société : {denomination}",
        f"NAF : {code_naf} — {libelle_naf or 'n/a'}",
    ]
    if latest:
        lignes.append(f"Dernier exercice : {latest.annee}")
    if sig:
        lignes.append(
            f"CA : {_fmt_eur_m(sig.chiffre_affaires)} · "
            f"VA : {_fmt_eur_m(sig.valeur_ajoutee)} · "
            f"EBE : {_fmt_eur_m(sig.ebe)} · "
            f"Résultat net : {_fmt_eur_m(sig.resultat_net)}"
        )
    if ratios:
        lignes.append(
            f"Marge EBE/CA : {_fmt_pct(ratios.marge_ebe)} · "
            f"ROE : {_fmt_pct(ratios.roe)} · "
            f"ROCE : {_fmt_pct(ratios.roce)} · "
            f"Gearing : {_fmt_pct(ratios.gearing)}"
        )
        if hasattr(ratios, "dso"):
            lignes.append(
                f"DSO : {ratios.dso:.0f} j · "
                f"DPO : {ratios.dpo:.0f} j · "
                f"BFR/CA : {_fmt_pct(ratios.bfr_ca)}"
                if ratios.dso is not None else "DSO/DPO/BFR : n/a"
            )
    if analysis is not None:
        scoring = getattr(analysis, "scoring", None)
        if scoring is not None:
            lignes.append(
                f"Altman Z : {getattr(scoring, 'altman_z', None)} — "
                f"Score FinSight PME : {getattr(scoring, 'finsight_score', None)}/100"
            )
    if benchmark is not None:
        rank = getattr(benchmark, "rank_global", None) or getattr(benchmark, "rank", None)
        if rank:
            lignes.append(f"Benchmark sectoriel : {rank}")
    if len(yearly_accounts) >= 2:
        yrs = sorted(yearly_accounts, key=lambda a: a.annee)
        ca0 = getattr(yrs[0].sig, "chiffre_affaires", None) if yrs[0].sig else None
        ca1 = getattr(yrs[-1].sig, "chiffre_affaires", None) if yrs[-1].sig else None
        if ca0 and ca1 and ca0 > 0:
            growth = (ca1 / ca0) ** (1 / max(1, len(yrs) - 1)) - 1
            lignes.append(
                f"Croissance CA CAGR {yrs[0].annee}-{yrs[-1].annee} : {_fmt_pct(growth)}"
            )
    return "\n".join(lignes)


def generate_pme_commentaires(
    denomination: str,
    code_naf: str | None,
    libelle_naf: str | None,
    analysis: Any,
    benchmark: Any,
    yearly_accounts: list,
    language: str = "fr",
) -> dict[str, str]:
    """Appelle le LLM pour produire les 8 commentaires en une passe.

    Retourne un dict {section: texte}. Retourne {} si LLM KO ou sortie invalide —
    les sections manquantes seront omises du rapport (pas de fake text).
    """
    try:
        from core.llm_provider import llm_call
    except Exception:
        log.warning("[pme_commentaires] llm_provider import impossible — pas de commentaires")
        return {}

    context = _build_context_bullet(
        denomination, code_naf, libelle_naf, analysis, benchmark, yearly_accounts
    )

    prompt = (
        "Tu es un analyste financier senior spécialisé dans les PME françaises. "
        "Écris en français avec accents complets (é è ê à ù ç î ô), apostrophes droites, "
        "guillemets français (« »). Pas de jargon anglo-saxon superflu.\n\n"
        "CONTEXTE — chiffres clés de l'entreprise :\n"
        f"{context}\n\n"
        "Rédige 8 commentaires courts (3-5 phrases chacun) EN JSON STRICT, clé = section, valeur = texte :\n\n"
        "1. \"sig\" : commentaire sur les Soldes Intermédiaires de Gestion (CA, VA, EBE, RN). Pointe la structure de création de valeur.\n"
        "2. \"rentabilite\" : commentaire sur marges (EBE, nette), ROE, ROCE. Compare à la médiane sectorielle si dispo.\n"
        "3. \"solidite\" : gearing, autonomie financière, trésorerie. Identifie les signaux de fragilité ou de solidité.\n"
        "4. \"efficacite\" : DSO/DPO/DIO/BFR. Commente le cycle d'exploitation.\n"
        "5. \"croissance\" : trajectoire pluriannuelle CA + résultat. Tendance qualitative.\n"
        "6. \"scoring\" : Altman Z, Score FinSight PME. Lis la zone de risque (rouge/orange/verte).\n"
        "7. \"bankabilite\" : capacité à lever de la dette. Ratios bancaires clés.\n"
        "8. \"synthese\" : verdict global en 4-5 phrases — forces, faiblesses, recommandations.\n\n"
        "Format de réponse EXIGÉ (et rien d'autre) :\n"
        "{\"sig\": \"...\", \"rentabilite\": \"...\", \"solidite\": \"...\", "
        "\"efficacite\": \"...\", \"croissance\": \"...\", \"scoring\": \"...\", "
        "\"bankabilite\": \"...\", \"synthese\": \"...\"}"
    )

    try:
        raw = llm_call(prompt, phase="long", max_tokens=1800) or ""
    except Exception as e:
        log.warning(f"[pme_commentaires] LLM call failed: {e}")
        return {}

    # Extraction JSON robuste — un bloc {...} quelque part dans la réponse
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        log.warning("[pme_commentaires] pas de JSON trouvé dans la sortie LLM")
        return {}
    try:
        parsed = json.loads(match.group(0))
    except Exception as e:
        log.warning(f"[pme_commentaires] parsing JSON échoué : {e}")
        return {}

    # Ne garder que les sections LLM réellement remplies — pas de substitution.
    out: dict[str, str] = {}
    for sec in SECTIONS:
        v = parsed.get(sec)
        if isinstance(v, str) and v.strip() and len(v) > 30:
            out[sec] = v.strip()
    return out
