"""Pipeline LLM Portrait d'entreprise.

Orchestration : sources → enrichissement → générations LLM par section
→ assemblage state final pour le writer PDF.

Cascade LLM (cohérent avec /qa) :
  1. Groq llama-3.3-70b (rapide, gratuit)
  2. Mistral large (fallback)
  3. Anthropic Haiku 4.5 (fallback ultime)

Sections générées (15 pages cible) :
  1. Cover (statique)
  2. Snapshot exécutif
  3. Histoire & jalons
  4. Vision & ADN
  5. Modèle économique
  6. Segments & revenus
  7. Dirigeants (CEO + management) — 2-3 pages selon nb d'officers
  8. Marché & paysage concurrentiel
  9. Risques & opportunités
  10. Stratégie 12-24 mois
  11. Devil's advocate
  12. Verdict + valorisation contextuelle
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional
from datetime import datetime

from .sources import (
    CompanyContext,
    fetch_yfinance_context,
    enrich_with_wikipedia,
    enrich_officers_with_wikipedia,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State du portrait
# ---------------------------------------------------------------------------
@dataclass
class PortraitState:
    ticker: str
    generated_at: str
    context: CompanyContext

    # Sections générées par LLM (str ou None si échec)
    snapshot: Optional[str] = None
    history: Optional[str] = None
    vision: Optional[str] = None
    business_model: Optional[str] = None
    segments: Optional[str] = None
    leadership_intro: Optional[str] = None
    market: Optional[str] = None
    risks: Optional[str] = None
    strategy: Optional[str] = None
    devil_advocate: Optional[str] = None
    verdict: Optional[str] = None

    # Données techniques
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SYSTEM_FR = (
    "Tu es analyste senior chez FinSight IA. Tu rédiges en français professionnel "
    "(accents complets, ponctuation soignée). Tu es factuel, dense, sans formule "
    "creuse. Aucune phrase d'introduction du type 'Voici…' ou 'Dans cette section…'. "
    "Tu vas droit au but. Style éditorial sobre type Bloomberg/L'Agefi."
)


def _ctx_block(ctx: CompanyContext, ratios_hint: Optional[dict] = None) -> str:
    """Construit le bloc contexte commun à tous les prompts."""
    lines = [
        f"Société : {ctx.name} ({ctx.ticker})",
        f"Secteur : {ctx.sector or 'n/a'} · Industrie : {ctx.industry or 'n/a'}",
        f"Pays : {ctx.country or 'n/a'} · Site : {ctx.website or 'n/a'}",
    ]
    if ctx.employees:
        lines.append(f"Effectif : {ctx.employees:,}".replace(",", " "))
    if ctx.market_cap:
        lines.append(f"Capi boursière : {ctx.market_cap/1e9:.1f} Mds {ctx.currency or ''}".strip())
    if ctx.long_business_summary:
        lines.append(f"\nDescription officielle (yfinance) :\n{ctx.long_business_summary[:1200]}")
    if ctx.wiki_intro:
        lines.append(f"\nWikipedia (intro) :\n{ctx.wiki_intro[:1500]}")
    if ratios_hint:
        lines.append(f"\nRatios clés : {ratios_hint}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cascade LLM
# ---------------------------------------------------------------------------
def _llm_call(prompt: str, system: str, max_tokens: int = 700) -> str:
    """Cascade Groq → Mistral → Anthropic. Retourne du texte ou lève."""
    from core.llm_provider import LLMProvider

    last_err = None
    for prov, model in [
        ("groq", "llama-3.3-70b-versatile"),
        ("mistral", None),
        ("anthropic", None),
    ]:
        try:
            llm = LLMProvider(provider=prov, model=model)
            ans = llm.generate(prompt, system=system, max_tokens=max_tokens)
            if ans and ans.strip():
                return ans.strip()
        except Exception as e:
            last_err = e
            log.warning(f"[portrait/pipeline] {prov} failed: {e}")
            continue
    raise RuntimeError(f"Tous les providers LLM ont échoué : {last_err}")


# ---------------------------------------------------------------------------
# Sections (chaque section = 1 fonction)
# ---------------------------------------------------------------------------
def _gen_snapshot(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Rédige un snapshot exécutif en 4-5 phrases denses : "
        "qui est cette société, ce qu'elle fait, sa position dans son industrie, "
        "et un point clé qui résume sa trajectoire récente. "
        "Pas de bullets, pas de titres, juste un paragraphe."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=350)


def _gen_history(ctx: CompanyContext) -> str:
    history_hint = ctx.wiki_history[:3000] if ctx.wiki_history else ""
    extra = f"\n\nÉlément Wikipedia (section History) :\n{history_hint}" if history_hint else ""
    p = (
        f"{_ctx_block(ctx)}{extra}\n\n"
        "Raconte l'histoire de cette société en 3-4 paragraphes : fondation, "
        "jalons clés (acquisitions, IPO, pivots), crises traversées. "
        "Style narratif éditorial, dates précises quand possible."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=900)


def _gen_vision(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Décris la vision et l'ADN culturel de cette société en 2-3 paragraphes : "
        "valeurs, signature stratégique, ce qui la différencie de ses pairs sur le plan culturel. "
        "Évite les généralités creuses ('innovation', 'excellence'), sois spécifique."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=600)


def _gen_business_model(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Décris le modèle économique en 3 paragraphes : "
        "(1) sources de revenus principales et leur mix approximatif, "
        "(2) structure de coûts dominante (CapEx-intensif, OpEx, R&D…), "
        "(3) leviers de pricing power et marges associées. "
        "Sois quantitatif quand tu connais les ordres de grandeur."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=750)


def _gen_segments(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Découpe la société en 3 à 5 segments d'activité majeurs. Pour chaque segment : "
        "nom, part du CA approximative, dynamique de croissance, marges typiques. "
        "Format : un paragraphe court par segment, séparés par une ligne vide. "
        "Pas de bullet points."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=800)


def _gen_leadership_intro(ctx: CompanyContext) -> str:
    leaders = ", ".join([f"{o.name} ({o.title})" for o in ctx.officers[:5] if o.name])
    p = (
        f"{_ctx_block(ctx)}\n\nDirigeants principaux : {leaders or 'non communiqués'}\n\n"
        "Rédige une introduction au leadership en 2 paragraphes : "
        "(1) profil global du management (ancienneté, fondateurs vs externes, gouvernance), "
        "(2) signaux récents (départs, recrutements, succession plan)."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=550)


def _gen_market(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Décris le marché et le paysage concurrentiel en 3 paragraphes : "
        "(1) taille du marché adressable et sa croissance, "
        "(2) 3-4 concurrents directs nommés avec positionnement relatif, "
        "(3) barrières à l'entrée et menaces de disruption."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=800)


def _gen_risks(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Liste et explique les 4 à 6 risques majeurs spécifiques à cette société. "
        "Pour chaque risque : nom court (gras dans le rendu final) + 1-2 phrases d'explication. "
        "Ordre par sévérité décroissante. Couvre : risques de marché, opérationnels, "
        "réglementaires, géopolitiques, technologiques, financiers."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=900)


def _gen_strategy(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Décris la stratégie de la société pour les 12 à 24 mois à venir, en 3-4 paragraphes : "
        "priorités d'investissement, M&A potentiels, expansion géographique, lancements produits, "
        "restructurations annoncées. Cite les éléments publics et signale ce qui relève de la lecture analytique."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=800)


def _gen_devil(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Endosse le rôle de devil's advocate. Construis la thèse inverse : "
        "pourquoi cette société pourrait sous-performer ou être une mauvaise allocation de capital "
        "sur 24-36 mois ? 3 arguments distincts, chacun en un paragraphe, étayé par des éléments "
        "factuels (concurrence, exécution, valuation, structure de coûts, dépendances)."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=900)


def _gen_verdict(ctx: CompanyContext) -> str:
    p = (
        f"{_ctx_block(ctx)}\n\n"
        "Conclus le portrait par un verdict synthétique en 3 paragraphes : "
        "(1) ce qu'il faut retenir de cette société (3 points clés en prose), "
        "(2) profil d'investisseur pour qui elle est adaptée et durée de détention recommandée, "
        "(3) signal clé à surveiller dans les 6 prochains mois. "
        "Reste factuel, ne formule pas de recommandation explicite d'achat/vente."
    )
    return _llm_call(p, SYSTEM_FR, max_tokens=750)


# ---------------------------------------------------------------------------
# Orchestration principale
# ---------------------------------------------------------------------------
def generate_portrait(
    ticker: str,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> PortraitState:
    """Pipeline complet : sources → enrichissement → génération sections.

    Args:
        ticker: ticker boursier (AAPL, MC.PA, etc.)
        progress_cb: callback(progress_pct, message) optionnel

    Returns:
        PortraitState avec toutes les sections remplies (ou warnings).
    """
    def _step(pct: int, msg: str):
        log.info(f"[portrait] {pct}% — {msg}")
        if progress_cb:
            try:
                progress_cb(pct, msg)
            except Exception:
                pass

    state = PortraitState(
        ticker=ticker,
        generated_at=datetime.utcnow().isoformat(),
        context=CompanyContext(ticker=ticker, name=ticker),
    )

    # --- 1. Sources ---
    _step(5, "Récupération des données yfinance")
    try:
        state.context = fetch_yfinance_context(ticker)
    except Exception as e:
        state.warnings.append(f"yfinance: {e}")

    _step(15, "Enrichissement Wikipedia (intro + history)")
    try:
        state.context = enrich_with_wikipedia(state.context)
    except Exception as e:
        state.warnings.append(f"wikipedia: {e}")

    _step(25, "Recherche photos & bios des dirigeants")
    try:
        state.context.officers = enrich_officers_with_wikipedia(
            state.context.officers, state.context.name
        )
    except Exception as e:
        state.warnings.append(f"officers enrichment: {e}")

    # --- 2. Sections LLM ---
    sections = [
        ("snapshot", _gen_snapshot, 35, "Snapshot exécutif"),
        ("history", _gen_history, 42, "Histoire & jalons"),
        ("vision", _gen_vision, 50, "Vision & ADN"),
        ("business_model", _gen_business_model, 57, "Modèle économique"),
        ("segments", _gen_segments, 64, "Segments d'activité"),
        ("leadership_intro", _gen_leadership_intro, 70, "Leadership"),
        ("market", _gen_market, 76, "Marché & concurrence"),
        ("risks", _gen_risks, 82, "Risques"),
        ("strategy", _gen_strategy, 87, "Stratégie 12-24 mois"),
        ("devil_advocate", _gen_devil, 92, "Devil's advocate"),
        ("verdict", _gen_verdict, 98, "Verdict final"),
    ]

    for attr, fn, pct, label in sections:
        _step(pct, label)
        try:
            value = fn(state.context)
            setattr(state, attr, value)
        except Exception as e:
            log.error(f"[portrait] section {attr} failed: {e}")
            state.warnings.append(f"{attr}: {str(e)[:200]}")

    _step(100, "Portrait prêt")
    return state
