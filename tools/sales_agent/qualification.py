# -*- coding: utf-8 -*-
"""tools/sales_agent/qualification.py — Score 0-100 d'un prospect LinkedIn.

Le score est calculé via Claude Haiku sur 5 axes pondérés. Permet de
trier les 30-50 profils découverts chaque jour pour ne garder que les
top 10 réellement pertinents pour FinSight (particuliers actifs FR).

Approche pragmatique : on n'invente pas un système de ML — un LLM
prompté avec un rubric clair fait le job en 1-2 secondes par prospect
pour <0.001$ avec Haiku.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


_AXES = {
    "intent": (
        "Le prospect cherche-t-il activement des outils d'analyse "
        "financière ? (pose des questions, partage des frustrations sur "
        "Yahoo Finance / Boursorama, demande des avis sur des stocks)"
    ),
    "persona": (
        "Le prospect est-il un particulier actif (PAS un pro RH, PAS un "
        "salarié sans rapport avec la finance, PAS un commercial banque) ? "
        "On veut : ingé/cadre sup avec PEA/CTO actif, ou indépendant qui "
        "investit en propre."
    ),
    "frequency": (
        "Le prospect poste-t-il régulièrement (>1 post/semaine) sur des "
        "sujets finance/bourse/investissement ? Compte actif vs zombie."
    ),
    "expertise": (
        "Le prospect a-t-il une expertise réelle (cite des ratios, parle "
        "de DCF, comprend les comparables) vs un débutant qui partage "
        "juste des screenshots Boursorama ?"
    ),
    "icp_fit": (
        "Le prospect correspond-il à l'ICP particulier FR : 30-55 ans, "
        "PEA > 50k€ probable, vraie capacité de payer 20€/mois ? Pas un "
        "étudiant qui découvre, pas un retraité qui ne change plus."
    ),
}

_WEIGHTS = {"intent": 20, "persona": 25, "frequency": 15,
             "expertise": 20, "icp_fit": 20}

# Pondération alternative quand pas de posts visibles (CSV import simple,
# sans champ recent_posts). On réduit intent + frequency (impossibles à
# évaluer sans contenu) et on redistribue vers persona/expertise/icp_fit.
# Sinon le profil retail valide perd 35% (intent 20 + freq 15 = 0/35).
# Audit 27/04 : Haiku scorait 6 prospects à 1-31 alors qu'ils sont
# clairement retail finance OK — par penalisation injuste sur axes posts.
_WEIGHTS_NO_POSTS = {"intent": 5, "persona": 30, "frequency": 5,
                     "expertise": 30, "icp_fit": 30}


@dataclass
class QualificationResult:
    score: int                   # 0-100
    breakdown: dict              # {axe: 0-100} pour chaque axe
    reasoning: str               # 80-120 mots résumant l'analyse
    target_ticker: Optional[str] # ticker pertinent à analyser pour ce prospect


def qualify_prospect(
    name: str,
    headline: str,
    bio: Optional[str] = None,
    recent_posts: Optional[list[dict]] = None,
) -> QualificationResult:
    """Score un prospect via Claude Haiku, retourne breakdown détaillé.

    Args:
        name : nom complet
        headline : titre LinkedIn (ex: "Ingénieur · Investisseur PEA")
        bio : texte "À propos" (optionnel)
        recent_posts : liste de {date, text, url} des 3-5 derniers posts

    Returns:
        QualificationResult avec score 0-100, breakdown 5 axes et un
        target_ticker que le prospect a mentionné dans ses posts (si trouvé).
    """
    posts_text = ""
    has_posts = bool(recent_posts and len(recent_posts) > 0)
    if has_posts:
        for p in recent_posts[:5]:
            d = p.get("date", "")
            t = (p.get("text") or "")[:600]
            posts_text += f"\n— [{d}] {t}\n"

    # Pondération dynamique selon disponibilité posts
    weights_active = _WEIGHTS if has_posts else _WEIGHTS_NO_POSTS

    rubric = "\n".join([
        f"  • {axe.upper()} (poids {weights_active[axe]}/100) : {desc}"
        for axe, desc in _AXES.items()
    ])

    no_posts_hint = (
        "\nIMPORTANT : aucun post visible dans le profil. NE MET PAS intent "
        "et frequency à 0 ou très bas par défaut. Évalue à 40-60 (neutre) "
        "sauf si la bio contient explicitement un signal négatif. Concentre "
        "ton jugement sur persona/expertise/icp_fit (poids redistribués)."
        if not has_posts else ""
    )

    prompt = (
        f"Profil LinkedIn à scorer pour FinSight (analyse financière B2C, "
        f"cible particuliers FR investisseurs actifs PEA).\n\n"
        f"PROSPECT\n"
        f"Nom : {name}\n"
        f"Headline : {headline}\n"
        f"Bio : {(bio or '')[:800]}\n"
        f"Posts récents :{posts_text or ' (aucun)'}\n"
        f"{no_posts_hint}\n"
        f"TÂCHE\n"
        f"Évalue ce prospect sur 5 axes, chacun de 0 à 100 :\n{rubric}\n\n"
        f"Identifie aussi un ticker boursier que ce prospect a mentionné "
        f"explicitement dans ses posts (ex: AAPL, LVMH, MC.PA, NVDA). Si "
        f"plusieurs, prends le plus récent. Si aucun, retourne null.\n\n"
        f"FORMAT RÉPONSE — JSON STRICT, sans markdown, sans préambule :\n"
        f'{{"intent": <0-100>, "persona": <0-100>, "frequency": <0-100>, '
        f'"expertise": <0-100>, "icp_fit": <0-100>, '
        f'"reasoning": "<résumé 80-120 mots en français des points clés>", '
        f'"target_ticker": "<ticker ou null>"}}'
    )

    try:
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="anthropic",
                            model="claude-haiku-4-5-20251001")
        raw = llm.generate(prompt,
                             system="Analyste qualif sales pragmatique. JSON only.",
                             max_tokens=600)
    except Exception as e:
        log.warning(f"[qualif] anthropic échec, fallback groq : {e}")
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
        raw = llm.generate(prompt, system="JSON only.", max_tokens=600)

    return _parse_qualification(raw, weights=weights_active)


def _parse_qualification(raw: str, weights: Optional[dict] = None) -> QualificationResult:
    """Parse la réponse JSON tolérante (markdown, préambule, etc.).

    Args:
        raw : raw LLM JSON output
        weights : pondérations à utiliser pour le score composite. Si None,
                  fallback _WEIGHTS standard. Permet pondération dynamique
                  selon contexte (avec/sans posts).
    """
    weights = weights or _WEIGHTS
    txt = (raw or "").strip()
    if txt.startswith("```"):
        txt = txt.split("```", 2)[1]
        if txt.lower().startswith("json"):
            txt = txt[4:]
    if txt.endswith("```"):
        txt = txt[:-3]
    start = txt.find("{")
    end = txt.rfind("}")
    if start < 0 or end <= start:
        log.warning(f"[qualif] JSON introuvable : {raw[:200]}")
        return _empty_result()
    try:
        data = json.loads(txt[start:end + 1])
    except json.JSONDecodeError as e:
        log.warning(f"[qualif] JSON invalide : {e} -- {raw[:200]}")
        return _empty_result()

    breakdown = {axe: int(_clamp(data.get(axe, 0), 0, 100))
                 for axe in _AXES}
    # Score pondéré — utilise les poids dynamiques (avec/sans posts)
    score = round(sum(breakdown[axe] * weights[axe] / 100
                       for axe in _AXES))
    score = int(_clamp(score, 0, 100))

    target = data.get("target_ticker")
    if target and isinstance(target, str):
        # Nettoyage : MAJUSCULES, retire $/€/whitespace, valide format
        t = target.strip().upper().lstrip("$").rstrip(".")
        if re.match(r"^[A-Z0-9\.\-]{1,12}$", t) and t != "NULL":
            target = t
        else:
            target = None
    else:
        target = None

    reasoning = str(data.get("reasoning", "")).strip()[:600]

    return QualificationResult(score=score, breakdown=breakdown,
                                 reasoning=reasoning, target_ticker=target)


def _clamp(v, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, f))


def _empty_result() -> QualificationResult:
    return QualificationResult(
        score=0,
        breakdown={axe: 0 for axe in _AXES},
        reasoning="Qualification échouée (LLM JSON parse).",
        target_ticker=None,
    )


if __name__ == "__main__":
    # Test manuel
    import sys
    logging.basicConfig(level=logging.INFO)
    r = qualify_prospect(
        name="Pierre Dupont",
        headline="Ingénieur informatique · Investisseur PEA depuis 8 ans",
        bio="Passionné par l'analyse fondamentale, je partage régulièrement "
             "mes thèses d'investissement. Focus sur les valeurs européennes "
             "sous-évaluées. Pas un conseil en investissement.",
        recent_posts=[
            {"date": "2026-04-20",
              "text": "Schneider Electric (SU.PA) reste un de mes top picks. "
                       "P/E 30x peut sembler cher mais le ROIC 18% justifie. "
                       "DCF base 295€, upside 7% sur les 12 mois."},
            {"date": "2026-04-15",
              "text": "Discussion intéressante hier sur la valorisation "
                       "du luxe. LVMH 27x earnings vs Hermès 50x — qui mérite "
                       "la prime ? Je penche Hermès pour le pricing power."},
        ],
    )
    print(f"Score    : {r.score}/100")
    print(f"Breakdown: {r.breakdown}")
    print(f"Target   : {r.target_ticker}")
    print(f"Reasoning: {r.reasoning}")
