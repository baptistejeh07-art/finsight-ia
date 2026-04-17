# -*- coding: utf-8 -*-
"""
agents/agent_lbo.py — Agent LLM dedie au LBO Model FinSight.

Genere 4 textes analytiques accentues pour les slides LBO du PPTX societe :
  1. Eligibilite (bandeau slide 13)
  2. Hypotheses du modele (footer slide 13)
  3. Lecture des returns (footer slide 14)
  4. Risques principaux (footer slide 15)

Utilise un LLM (Mistral / Anthropic / Groq) avec regle absolue typographie
francaise (cf. CLAUDE.md). Fallback texte deterministe si LLM echoue.
"""
from __future__ import annotations

import logging
import json
import re
from typing import Optional

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de formatage
# ─────────────────────────────────────────────────────────────────────────────

def _f(v, dp=1, suffix=""):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{dp}f}{suffix}".replace(".", ",")
    except Exception:
        return "N/A"


def _pct(v, dp=1):
    if v is None:
        return "N/A"
    try:
        fv = float(v)
        if abs(fv) <= 2:
            fv *= 100
        return f"{fv:.{dp}f}%".replace(".", ",")
    except Exception:
        return "N/A"


def _x(v, dp=1):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{dp}f}x".replace(".", ",")
    except Exception:
        return "N/A"


# ─────────────────────────────────────────────────────────────────────────────
# Generation des 4 textes
# ─────────────────────────────────────────────────────────────────────────────

def generate_lbo_texts(lbo_data: dict, m: dict = None) -> dict:
    """Genere les 4 textes LLM analytiques pour le LBO.

    Args:
        lbo_data: dict retourne par lbo_model.read_lbo_data() avec
                  eligible, mega_flag, irr_base, moic_base, irr_bull, irr_bear,
                  leverage_exit, equity_entry, equity_exit, company_name, ticker
        m: dict optionnel des metriques societe (m_a) pour enrichir le contexte
           (sector, ev, ebitda_margin, etc.)

    Returns:
        dict avec les 4 cles :
          - eligibility_text : 60 mots, bandeau verdict eligibilite
          - hypotheses_text : 100 mots, footer slide cadre du deal
          - returns_text : 130 mots, footer slide returns sponsor
          - risks_text : 130 mots, footer slide stress test

        Tous en francais correct avec accents (ou fallback deterministe si LLM KO).
    """
    m = m or {}
    eligible = bool(lbo_data.get("eligible", False))
    mega_flag = str(lbo_data.get("mega_flag", "standard"))
    company = lbo_data.get("company_name") or m.get("company_name_a") or "la societe"
    ticker = lbo_data.get("ticker") or m.get("ticker_a") or ""
    sector = m.get("sector") or m.get("sector_a") or "non precise"

    irr_base = lbo_data.get("irr_base")
    moic_base = lbo_data.get("moic_base")
    irr_bull = lbo_data.get("irr_bull")
    irr_bear = lbo_data.get("irr_bear")
    lvg_exit = lbo_data.get("leverage_exit")
    eq_entry = lbo_data.get("equity_entry")
    eq_exit = lbo_data.get("equity_exit")

    # Tentative LLM
    try:
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="mistral", model="mistral-small-latest")

        from core.prompt_standards import build_system_prompt
        _sys_lbo = build_system_prompt(
            role="analyste senior PE/M&A sell-side (JPMorgan, Goldman Sachs)",
            include_json=True,
        )
        prompt = (
            f"{_sys_lbo}\n\n"
            f"MISSION : rédiger 4 textes analytiques rigoureux sur le LBO "
            f"théorique de {company} ({ticker}) — secteur {sector}.\n\n"
            f"DONNÉES LBO :\n"
            f"- Éligibilité : {'OUI' if eligible else 'NON'}\n"
            f"- Flag taille deal : {mega_flag}\n"
            f"- IRR sponsor base : {_pct(irr_base)}\n"
            f"- MOIC base : {_x(moic_base)}\n"
            f"- IRR bull / bear : {_pct(irr_bull)} / {_pct(irr_bear)}\n"
            f"- Leverage exit : {_x(lvg_exit)}\n"
            f"- Equity sponsor entrée : {_f(eq_entry, 0)} M$\n"
            f"- Equity sponsor sortie : {_f(eq_exit, 0)} M$\n"
            f"- Marge EBITDA société : {_pct(m.get('ebitda_margin_ltm'))}\n"
            f"- ROIC : {_pct(m.get('roic'))}\n"
            f"- Net Debt / EBITDA actuel : {_x(m.get('net_debt_ebitda'))}\n\n"
            f"LONGUEURS STRICTES (en MOTS) par champ :\n"
            f'{{\n'
            f'  "eligibility_text": "40-60 mots : verdict éligibilité LBO de {company}, '
            f'critères passés/non passés (marge EBITDA, cash conv, levier), conclusion '
            f'profil LBO-able ou non. Si mega_flag != standard, mentionner contexte mega-deal.",\n'
            f'  "hypotheses_text": "75-100 mots : justification hypothèses retenues — '
            f'multiple d entrée, leverage 5x EBITDA (Senior 3.5x + Mezz 1.5x), coûts dette, '
            f'multiple sortie conservateur. Distinguer données société vs standards marché.",\n'
            f'  "returns_text": "100-130 mots : analyse returns sponsor — IRR base {_pct(irr_base)} '
            f'vs seuils PE typiques (>=20% top quartile, 15-20% mid, <15% sous-performance). '
            f'MOIC {_x(moic_base)}. Lecture de la sensibilité (zones robustes/fragiles). '
            f'Conclusion sur l attractivité du deal pour un sponsor PE.",\n'
            f'  "risks_text": "EXACTEMENT 55-65 mots STRICT (box etroite 23x1.5cm slide 19) : '
            f'3 risques principaux du LBO en 1 phrase chacun — operationnel (compression '
            f'marges), financier (covenants, refinancing), marche (multiple compression). '
            f'Cite les chiffres bear (IRR {_pct(irr_bear)}, leverage exit)."\n'
            f'}}'
        )

        resp = llm.generate(prompt, max_tokens=1500)
        match = re.search(r'\{.*\}', resp, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            log.info("[agent_lbo] LLM texts OK (%d champs)", len(data))
            # Verifier que les 4 cles sont presentes
            required = ["eligibility_text", "hypotheses_text", "returns_text", "risks_text"]
            if all(k in data for k in required):
                return data
            log.warning("[agent_lbo] LLM JSON incomplet — fallback")
    except Exception as e:
        log.warning("[agent_lbo] LLM generation failed: %s — fallback determinist", e)

    # ─── Fallback deterministe (toujours en francais accentue) ───
    return _fallback_texts(lbo_data, m, eligible, mega_flag, company, ticker, sector,
                            irr_base, moic_base, irr_bull, irr_bear, lvg_exit)


def _fallback_texts(lbo_data, m, eligible, mega_flag, company, ticker, sector,
                    irr_base, moic_base, irr_bull, irr_bear, lvg_exit) -> dict:
    """Textes deterministes (avec accents) en cas d echec LLM."""
    margin = _pct(m.get("ebitda_margin_ltm")) if m else "N/A"
    nd_ebitda = _x(m.get("net_debt_ebitda")) if m else "N/A"

    if eligible:
        eligibility_text = (
            f"{company} satisfait les critères standards d'éligibilité LBO mid-market : "
            f"marge EBITDA de {margin} (>15%), cash conversion solide, "
            f"leverage actuel ND/EBITDA de {nd_ebitda} (<3,5x). "
            f"Le profil opérationnel et financier permet d'envisager un montage "
            f"sponsor-driven crédible."
        )
    else:
        eligibility_text = (
            f"{company} ne satisfait pas tous les critères d'un LBO mid-market standard. "
            f"Les principaux freins identifiés sont la marge EBITDA ({margin}), la "
            f"capacité de cash conversion ou le niveau de levier déjà élevé "
            f"({nd_ebitda}). Le profil reste analysé à titre théorique."
        )

    if mega_flag == "theorique":
        eligibility_text += (
            " Note : EV > 100 Md$, scénario théorique hors marché LBO historique."
        )
    elif mega_flag == "mega":
        eligibility_text += (
            " Note : mega-deal nécessitant un syndicat de sponsors (type Twitter/X)."
        )

    hypotheses_text = (
        f"Le modèle retient un multiple d'entrée par défaut de 14x EBITDA (paramétrable), "
        f"un leverage total de 5x EBITDA réparti entre Senior Term Loan B (3,5x à coût "
        f"~8% SOFR + 400 bps) et Mezzanine (1,5x à coût all-in 10% cash + PIK). "
        f"Le multiple de sortie est conservateur (identique à l'entrée, pas de multiple "
        f"expansion supposée). Les projections opérationnelles (revenue growth, marge "
        f"EBITDA, capex, ΔBFR) sont importées du modèle DCF FinSight pour cohérence. "
        f"Tax rate effective issue de l'historique {company}."
    )

    returns_text = (
        f"Le sponsor récupère un IRR base de {_pct(irr_base)} et un MOIC de {_x(moic_base)} "
        f"sur 5 ans. "
    )
    if irr_base is not None:
        try:
            irr_val = float(irr_base)
            if abs(irr_val) <= 2:
                irr_val *= 100
            if irr_val >= 20:
                returns_text += (
                    "Ce niveau dépasse le seuil minimum PE top quartile (≥ 20%), "
                    "rendant le deal très attractif pour un sponsor institutionnel. "
                )
            elif irr_val >= 15:
                returns_text += (
                    "Ce niveau correspond au seuil PE mid-market (15-20%), "
                    "deal viable pour un sponsor de qualité. "
                )
            else:
                returns_text += (
                    "Ce niveau reste sous le seuil PE typique (<15%), "
                    "rendant le deal peu attractif sans création de valeur opérationnelle additionnelle. "
                )
        except Exception:
            pass
    returns_text += (
        f"La sensibilité IRR aux multiples d'entrée et de sortie permet d'identifier "
        f"les zones de robustesse (combinaisons multiple bas / sortie élevée) et de "
        f"fragilité (multiple haut / sortie basse). À croiser avec le scénario bear "
        f"(IRR {_pct(irr_bear)}) pour calibrer le risque downside."
    )

    risks_text = (
        f"Les risques principaux du montage portent sur quatre dimensions. "
        f"(1) Opérationnel : compression des marges EBITDA en cas de ralentissement "
        f"sectoriel, exécution du business plan sponsor (réduction coûts, croissance "
        f"organique). (2) Financier : respect des covenants leverage et coverage, "
        f"capacité de refinancement à 5 ans dans un environnement de taux incertain. "
        f"(3) Marché : compression des multiples de sortie sous l'effet d'un re-rating "
        f"sectoriel ou macro. (4) Stress : le scénario bear projette un IRR de "
        f"{_pct(irr_bear)} avec leverage exit {_x(lvg_exit)}, traduisant la sensibilité "
        f"du deal aux hypothèses centrales. La thèse s'invalide si la marge EBITDA "
        f"perd plus de 200 bps ou si le multiple de sortie chute de 2x."
    )

    return {
        "eligibility_text": eligibility_text,
        "hypotheses_text": hypotheses_text,
        "returns_text": returns_text,
        "risks_text": risks_text,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper (consistance avec les autres agents FinSight)
# ─────────────────────────────────────────────────────────────────────────────

class AgentLBO:
    """Agent dedie a la generation de textes LBO."""

    def generate(self, lbo_data: dict, metrics: dict = None) -> dict:
        return generate_lbo_texts(lbo_data, metrics)
