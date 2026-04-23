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
    """Résumé structuré injecté au prompt LLM (<500 tokens).

    Attributs corrects :
      - YearAccounts → pas de .sig/.ratios, juste les lignes PCG (CA, capitaux_propres…)
      - PmeAnalysis → sig_by_year[year] (SIG) + ratios_by_year[year] (Ratios)
      - SIG : chiffre_affaires, valeur_ajoutee, ebe, resultat_net
      - Ratios : marge_ebitda, marge_nette, roe, roce, autonomie_financiere,
                 dso_jours, dpo_jours, bfr, bfr_jours_ca, tresorerie_nette
    """
    yrs_sorted = sorted(yearly_accounts, key=lambda a: a.annee) if yearly_accounts else []
    latest_year = yrs_sorted[-1].annee if yrs_sorted else None

    sig_by_year = getattr(analysis, "sig_by_year", {}) or {}
    ratios_by_year = getattr(analysis, "ratios_by_year", {}) or {}
    sig = sig_by_year.get(latest_year) if latest_year is not None else None
    ratios = ratios_by_year.get(latest_year) if latest_year is not None else None

    lignes = [
        f"Société : {denomination}",
        f"NAF : {code_naf or 'n/a'} — {libelle_naf or 'n/a'}",
    ]
    if latest_year is not None:
        lignes.append(f"Dernier exercice disponible : {latest_year}")
    if sig is not None:
        lignes.append(
            f"CA : {_fmt_eur_m(getattr(sig, 'chiffre_affaires', None))} · "
            f"VA : {_fmt_eur_m(getattr(sig, 'valeur_ajoutee', None))} · "
            f"EBE : {_fmt_eur_m(getattr(sig, 'ebe', None))} · "
            f"Résultat net : {_fmt_eur_m(getattr(sig, 'resultat_net', None))}"
        )
    if ratios is not None:
        lignes.append(
            f"Marge EBITDA : {_fmt_pct(getattr(ratios, 'marge_ebitda', None))} · "
            f"Marge nette : {_fmt_pct(getattr(ratios, 'marge_nette', None))} · "
            f"ROE : {_fmt_pct(getattr(ratios, 'roe', None))} · "
            f"ROCE : {_fmt_pct(getattr(ratios, 'roce', None))}"
        )
        _auto = getattr(ratios, "autonomie_financiere", None)
        _dne = getattr(ratios, "dette_nette_ebitda", None)
        _cov = getattr(ratios, "couverture_interets", None)
        if _auto is not None or _dne is not None:
            lignes.append(
                f"Autonomie financière : {_fmt_pct(_auto)} · "
                f"Dette nette/EBITDA : {(_dne if _dne is None else f'{_dne:.2f}x')} · "
                f"Couverture intérêts : {(_cov if _cov is None else f'{_cov:.2f}x')}"
            )
        _dso = getattr(ratios, "dso_jours", None)
        _dpo = getattr(ratios, "dpo_jours", None)
        _bfr = getattr(ratios, "bfr_jours_ca", None)
        if _dso is not None or _dpo is not None or _bfr is not None:
            lignes.append(
                f"DSO : {(_dso if _dso is None else f'{_dso:.0f} j')} · "
                f"DPO : {(_dpo if _dpo is None else f'{_dpo:.0f} j')} · "
                f"BFR : {(_bfr if _bfr is None else f'{_bfr:.0f} j de CA')}"
            )

    scoring = getattr(analysis, "scoring", None)
    if scoring is not None:
        _altman = getattr(scoring, "altman_z", None)
        _fscore = getattr(scoring, "finsight_score", None)
        if _altman is not None or _fscore is not None:
            lignes.append(
                f"Altman Z-score : {(_altman if _altman is None else f'{_altman:.2f}')} · "
                f"Score FinSight PME : {(_fscore if _fscore is None else f'{_fscore}/100')}"
            )

    if benchmark is not None:
        rank = getattr(benchmark, "rank_global", None) or getattr(benchmark, "rank", None)
        if rank:
            lignes.append(f"Positionnement sectoriel : {rank}")

    # Croissance CAGR via les CA des SIG (pas yearly_accounts qui n'ont pas .sig)
    if len(yrs_sorted) >= 2 and sig_by_year:
        y0 = yrs_sorted[0].annee
        y1 = yrs_sorted[-1].annee
        sig0 = sig_by_year.get(y0)
        sig1 = sig_by_year.get(y1)
        ca0 = getattr(sig0, "chiffre_affaires", None) if sig0 else None
        ca1 = getattr(sig1, "chiffre_affaires", None) if sig1 else None
        if ca0 and ca1 and ca0 > 0 and y1 > y0:
            cagr = (ca1 / ca0) ** (1 / (y1 - y0)) - 1
            lignes.append(f"Croissance CA CAGR {y0}-{y1} : {_fmt_pct(cagr)}")

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
        "Tu es un analyste financier senior spécialisé dans les PME françaises, "
        "style sell-side institutionnel (Lazard, Rothschild, EY Transaction Advisory). "
        "Écris en français rigoureux avec accents complets (é è ê à ù ç î ô), "
        "apostrophes droites ASCII (pas de ' ou '), "
        "guillemets français « ». Pas de jargon anglo-saxon superflu.\n\n"
        "CONTEXTE — chiffres clés de l'entreprise :\n"
        f"{context}\n\n"
        "TACHE : Rédige 8 commentaires (4-6 phrases chacun) au format JSON STRICT. "
        "Chaque commentaire doit citer au moins un chiffre précis du contexte, "
        "proposer une interprétation analytique (pas une description) et pointer "
        "un signal à surveiller ou une implication décisionnelle. Pas de lieux "
        "communs (« il est important de », « on peut noter que »).\n\n"
        "Sections attendues :\n"
        "1. sig : Soldes Intermédiaires de Gestion — structure de création de valeur, taux de conversion.\n"
        "2. rentabilite : marges EBITDA/nette, ROE, ROCE — comparaison implicite médiane sectorielle.\n"
        "3. solidite : autonomie financière, dette nette/EBITDA, couverture intérêts — signal bancable/fragile.\n"
        "4. efficacite : DSO, DPO, BFR en jours de CA — tension sur la trésorerie.\n"
        "5. croissance : trajectoire CA pluriannuelle, CAGR — tendance qualitative.\n"
        "6. scoring : Altman Z et Score FinSight PME — zone de risque (rouge <1.8 / orange 1.8-3 / verte >3).\n"
        "7. bankabilite : capacité à lever de la dette — vision banquier/investisseur.\n"
        "8. synthese : verdict global 5-6 phrases — forces, faiblesses, recommandation structurée.\n\n"
        "FORMAT DE SORTIE (RIEN D'AUTRE, PAS DE ```json, PAS DE COMMENTAIRE) :\n"
        "{\"sig\": \"...\", \"rentabilite\": \"...\", \"solidite\": \"...\", "
        "\"efficacite\": \"...\", \"croissance\": \"...\", \"scoring\": \"...\", "
        "\"bankabilite\": \"...\", \"synthese\": \"...\"}\n\n"
        "RÈGLES JSON STRICTES :\n"
        "- Échappe tous les guillemets doubles internes avec \\\".\n"
        "- Aucune virgule finale (pas de trailing comma).\n"
        "- Pas de retour à la ligne brut dans les valeurs (remplacer par espace).\n"
        "- UTF-8, pas de caractère de contrôle.\n\n"
        "Format de réponse EXIGÉ (et rien d'autre) :\n"
        "{\"sig\": \"...\", \"rentabilite\": \"...\", \"solidite\": \"...\", "
        "\"efficacite\": \"...\", \"croissance\": \"...\", \"scoring\": \"...\", "
        "\"bankabilite\": \"...\", \"synthese\": \"...\"}"
    )

    try:
        # strip_markdown=False : ne pas retirer les *, ** etc car ils peuvent
        # faire partie du texte des commentaires et casser le JSON.
        raw = llm_call(prompt, phase="long", max_tokens=2400, strip_markdown=False) or ""
    except Exception as e:
        log.warning(f"[pme_commentaires] LLM call failed: {e}")
        return {}

    log.info(f"[pme_commentaires] raw LLM len={len(raw)} head={raw[:80]!r}")

    # Extraction JSON robuste — un bloc {...} quelque part dans la réponse.
    # Le LLM peut préfixer par ```json\n ou du texte explicatif.
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        log.warning(f"[pme_commentaires] pas de JSON trouvé dans la sortie LLM (len={len(raw)})")
        return {}

    js = match.group(0)

    # Normalisation systématique AVANT le premier parse : apostrophes courbes
    # dans les clés JSON (« rentabilité », « solidité », « synthèse ») —
    # retirer les accents des clés uniquement.
    def _deaccent_keys(s: str) -> str:
        # Transform les clés accentuées en ASCII :
        # "rentabilité": -> "rentabilite":
        # "solidité": -> "solidite":
        # "synthèse": -> "synthese":
        mapping = {
            "rentabilité": "rentabilite",
            "solidité": "solidite",
            "efficacité": "efficacite",
            "synthèse": "synthese",
            "bankabilité": "bankabilite",
        }
        for k_fr, k_asc in mapping.items():
            s = s.replace(f'"{k_fr}"', f'"{k_asc}"')
        return s

    js_norm = _deaccent_keys(js)
    parsed = None
    try:
        parsed = json.loads(js_norm)
    except Exception as e_first:
        # Tentative 2 : fix apostrophes typo + trailing comma
        cleaned = re.sub(r",(\s*[}\]])", r"\1", js_norm)
        try:
            parsed = json.loads(cleaned)
        except Exception as e2:
            log.warning(
                f"[pme_commentaires] parsing JSON échoué : {e_first} (et aussi "
                f"après nettoyage : {e2})"
            )
            return {}

    # Ne garder que les sections LLM réellement remplies — pas de substitution.
    out: dict[str, str] = {}
    for sec in SECTIONS:
        v = parsed.get(sec)
        if isinstance(v, str) and v.strip() and len(v) > 30:
            out[sec] = v.strip()
    return out
