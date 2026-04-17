"""Standards de prompts LLM FinSight — blocs réutilisables.

Objectif : uniformiser la qualité des sorties LLM (tonalité institutionnelle,
longueur stricte respectée, anti-hallucination, français avec accents) à travers
TOUS les prompts du projet (writers, agents, app.py).

Usage simple :
    from core.prompt_standards import (
        RULE_FRENCH_ACCENTS,
        RULE_INSTITUTIONAL_TONE,
        RULE_NO_MARKDOWN,
        RULE_NO_HALLUCINATION,
        length_rule,
        pptx_overflow_rule,
        build_system_prompt,
    )

    prompt = (
        f"{build_system_prompt(role='senior sell-side analyst JPMorgan')}\n\n"
        f"{length_rule(min_words=120, max_words=180)}\n\n"
        f"{pptx_overflow_rule(zone='slide 10 droite')}\n\n"
        f"Données : ..."
    )
"""

from __future__ import annotations


# =============================================================================
# RÈGLES DE BASE — accessibles partout
# =============================================================================

RULE_FRENCH_ACCENTS = (
    "LANGUE : français correct avec TOUS les accents (é è ê à ù ç î ô û œ). "
    "Aucun mot sans accent. Cédilles obligatoires. Apostrophes droites ' et "
    "guillemets français « »."
)

RULE_INSTITUTIONAL_TONE = (
    "TON : prose technique sell-side senior (JPMorgan, Morgan Stanley, "
    "Goldman Sachs). Vocabulaire IB : valorisation relative, multiples, "
    "momentum, révisions BPA, prime de risque, discount DCF. Pas de "
    "vulgarisation, pas de phrases de présentation (« Voici... », « Nous "
    "allons... »). Attaque directe sur les faits et l'analyse."
)

RULE_NO_MARKDOWN = (
    "FORMAT : prose pure. INTERDIT : markdown (**, *, #), bullets, emojis, "
    "numérotations, puces, tableaux ASCII. Paragraphes séparés uniquement "
    "par des sauts de ligne doubles."
)

RULE_NO_HALLUCINATION = (
    "ANTI-HALLUCINATION : utilise UNIQUEMENT les chiffres présents dans le "
    "contexte fourni. JAMAIS inventer de multiple, de croissance, de taux, "
    "de date, de nom de société. Si une donnée manque, écris « non disponible » "
    "plutôt que d'inventer. Cite toujours les chiffres exacts (ex: "
    "« EV/EBITDA 12,3x » et non « autour de 12x »)."
)

RULE_JSON_ONLY = (
    "SORTIE : JSON valide uniquement. Aucun texte avant ou après le JSON. "
    "Pas de commentaires, pas de balises markdown (```json), pas "
    "d'explications. Le JSON DOIT commencer par { et finir par }."
)


# =============================================================================
# GÉNÉRATEURS DE RÈGLES PARAMÉTRÉES
# =============================================================================

def length_rule(min_words: int, max_words: int, *, hard: bool = True) -> str:
    """Règle de longueur STRICTE en mots.

    Préférer mots > caractères : plus naturel pour le LLM, moins de troncature.
    Utiliser hard=False pour une borne indicative (analyses libres).
    """
    strict = "STRICT — dépassement = sortie cassée" if hard else "indicatif"
    return (
        f"LONGUEUR ({strict}) : minimum {min_words} mots, maximum "
        f"{max_words} mots. Compte les mots avant de rendre ta réponse."
    )


def pptx_overflow_rule(*, zone: str = "", max_words: int = 120) -> str:
    """Règle spécifique PPTX : la text box a une taille fixe, tout dépassement
    coupe le texte visuellement. Le LLM doit ABSOLUMENT respecter la limite.
    """
    zone_info = f" (zone : {zone})" if zone else ""
    return (
        f"CONTRAINTE D'AFFICHAGE{zone_info} : le texte sera rendu dans une "
        f"text box de taille fixe. DÉPASSEMENT = texte coupé = rendu cassé. "
        f"Maximum absolu {max_words} mots. Préférer concision + densité "
        f"analytique à exhaustivité."
    )


def pdf_section_rule(*, min_words: int = 80, max_words: int = 140) -> str:
    """Règle spécifique PDF : plus de latitude que PPTX mais pas illimité."""
    return (
        f"SECTION PDF : paragraphe analytique dense, {min_words}-{max_words} "
        f"mots. Chaque phrase doit apporter une information ou un argument. "
        f"Zéro phrase de remplissage."
    )


def narration_rule(*, date_required: bool = True) -> str:
    """Règle pour les narrations de cours boursier (slide 20 FTSE etc.).

    Exige un rattachement aux dates et à l'actualité (demande Baptiste
    2026-04-17 : slide 20 doit narrer les fluctuations cours boursier avec
    dates et rattachement à l'actu).
    """
    date_req = (
        "OBLIGATOIRE : chaque inflexion majeure doit être datée (mois + "
        "année au minimum). Rattacher chaque pic / creux à l'événement "
        "macro ou sectoriel correspondant (publication résultats, annonce "
        "banque centrale, guerre, pandémie, rachat, M&A, etc.)."
        if date_required else
        "Dates bienvenues sans être obligatoires."
    )
    return (
        "NARRATION COURS BOURSIER : raconte la trajectoire du titre comme "
        "un analyste qui commente une performance historique. Structure : "
        "phase haussière / baissière / consolidation, dates des inflexions, "
        "catalyseurs associés. " + date_req
    )


def forbidden_phrases_rule(extras: list[str] | None = None) -> str:
    """Phrases bannies : toutes les formulations creuses / génériques qui
    polluent les sorties LLM.
    """
    base = [
        "Voici...", "Nous allons...", "Il est important de noter",
        "En conclusion", "Pour résumer", "Dans cette analyse",
        "Il convient de", "Il faut souligner que",
        "Cette analyse démontre", "comme le montre",
    ]
    banned = base + (extras or [])
    return (
        "PHRASES BANNIES : " + ", ".join(f'« {p} »' for p in banned) +
        ". Attaque direct sur le fait ou l'analyse."
    )


# =============================================================================
# BUILDERS DE SYSTEM PROMPT
# =============================================================================

def build_system_prompt(
    *,
    role: str = "analyste sell-side senior sur marchés cotés",
    include_accents: bool = True,
    include_institutional: bool = True,
    include_no_markdown: bool = True,
    include_no_halluc: bool = True,
    include_json: bool = False,
    extra_rules: list[str] | None = None,
) -> str:
    """Compose un system prompt standard.

    Exemples :
        # Pour writer PPTX avec JSON output :
        build_system_prompt(role="analyste M&A JPMorgan", include_json=True)

        # Pour commentaire libre PDF :
        build_system_prompt(role="analyste sectoriel")
    """
    parts = [f"Tu es {role}."]
    if include_accents:
        parts.append(RULE_FRENCH_ACCENTS)
    if include_institutional:
        parts.append(RULE_INSTITUTIONAL_TONE)
    if include_no_markdown:
        parts.append(RULE_NO_MARKDOWN)
    if include_no_halluc:
        parts.append(RULE_NO_HALLUCINATION)
    if include_json:
        parts.append(RULE_JSON_ONLY)
    if extra_rules:
        parts.extend(extra_rules)
    return "\n\n".join(parts)


# =============================================================================
# BUILDERS DE LONGUEUR PAR CONTEXTE
# =============================================================================

# Tailles recommandées par zone d'affichage.
# Basé sur tests réels PPTX 25.4cm × 14.3cm, PDF A4, slide FTSE 100.
LENGTH_PRESETS = {
    # PPTX — text boxes typiques
    "pptx_exec_summary":   (80, 120),   # synthèse top d'une slide
    "pptx_read_box":       (90, 140),   # box "Lecture" à droite d'un graph
    "pptx_thesis_long":    (140, 200),  # thèse détaillée
    "pptx_narration_stock":(150, 220),  # slide 20 narration cours boursier
    "pptx_methodo":        (60, 100),   # slide 21 méthodo/sources
    "pptx_signal_synth":   (100, 150),  # slide 2 synthèse signal
    # PDF — sections
    "pdf_short_commentary":(60, 100),
    "pdf_paragraph":       (100, 160),
    "pdf_deep_analysis":   (160, 240),
    # Agents
    "agent_thesis_item":   (35, 55),
    "agent_risk_item":     (25, 40),
    "agent_description":   (50, 70),
}


def preset_length(key: str, *, hard: bool = True) -> str:
    """Récupère la règle de longueur standardisée pour une zone connue."""
    _min, _max = LENGTH_PRESETS.get(key, (80, 150))
    return length_rule(_min, _max, hard=hard)
