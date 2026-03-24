# =============================================================================
# FinSight IA — Constitution v1.0
# config/constitution.py
#
# 7 articles fondamentaux regissant le comportement du systeme multi-agents.
# Toute modification passe par l'Agent Justice (processus formel Article 7).
#
# References dans le code :
#   - Article 1 : core/graph.py → blocked_node
#   - Article 2 : core/graph.py → route_after_fetch, fallback_node
#   - Article 3 : core/graph.py → route_after_qa
#   - Article 4 : outputs/excel_writer.py → _safe_write
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Article dataclass
# ---------------------------------------------------------------------------

@dataclass
class Article:
    number: int
    title:  str
    text:   str
    # Seuil operationnel associe (si numerique) — facilite la surveillance
    threshold:    Optional[float] = None
    threshold_key: Optional[str]  = None   # cle dans FinSightState ou metriques RH

    def __str__(self) -> str:
        hdr = f"Article {self.number} — {self.title}"
        sep = "-" * len(hdr)
        return f"{hdr}\n{sep}\n{self.text}"


# ---------------------------------------------------------------------------
# Les 7 articles
# ---------------------------------------------------------------------------

ARTICLES: list[Article] = [

    Article(
        number=1,
        title="Confiance minimale",
        text=(
            "Aucune recommandation d'investissement ne peut etre emise si le score "
            "de confiance de l'Agent Synthese est inferieur a 65 %. "
            "Le pipeline est alors interrompu (blocked=True) et l'utilisateur est "
            "informe que les conditions d'analyse sont insuffisantes. "
            "Ce seuil s'applique a tout ticker, toute session."
        ),
        threshold=0.45,
        threshold_key="confidence_score",
    ),

    Article(
        number=2,
        title="Qualite de donnees minimale",
        text=(
            "Le pipeline ne peut produire de synthese que si la qualite des donnees "
            "brutes (data_quality) est superieure ou egale a 70 % apres la phase "
            "d'enrichissement (fallback_node inclus). "
            "En dessous de ce seuil, le pipeline passe en mode degrade : "
            "les outputs sont generes avec un avertissement explicite, "
            "la recommandation est forcee a HOLD, et aucune cible de prix n'est emise."
        ),
        threshold=0.70,
        threshold_key="data_quality",
    ),

    Article(
        number=3,
        title="Politique de retry QA",
        text=(
            "En cas d'echec de la validation QA (erreur critique detectee par "
            "AgentQAPython), le pipeline est autorise a re-executer une seule fois "
            "l'Agent Synthese (qa_retries <= 1). "
            "Un second echec entraine l'emission d'un rapport avec les flags QA "
            "en evidence, sans bloquer l'output. "
            "Cette politique protege contre les boucles infinies tout en offrant "
            "une seconde chance a l'analyse."
        ),
        threshold=1.0,
        threshold_key="qa_retries",
    ),

    Article(
        number=4,
        title="Integrite des outputs Excel",
        text=(
            "Il est interdit d'ecraser toute cellule contenant une formule Excel "
            "dans TEMPLATE.xlsx. La protection est double : "
            "(a) liste statique FORMULA_CELLS dans config/excel_mapping.py, "
            "(b) verification dynamique de la valeur courante de la cellule. "
            "Toute tentative d'ecriture bloquee est logguee en ERROR. "
            "Les colonnes de formule dans COMPARABLES (H, I, L) sont egalement "
            "protegees. Aucune exception a cette regle n'est permise."
        ),
    ),

    Article(
        number=5,
        title="Droits et devoirs des agents observateurs",
        text=(
            "Les agents observateurs (AgentSociologue, AgentEnquete, AgentJournaliste) "
            "ont acces en lecture seule a tous les logs V2 et metriques RH. "
            "Ils ne peuvent ni modifier l'etat du pipeline, ni emettre de "
            "recommandations financieres. "
            "Leurs rapports sont informatifs et destines exclusivement a la "
            "gouvernance interne et a l'amelioration continue du systeme. "
            "L'AgentJournaliste publie un rapport hebdomadaire de synthese."
        ),
    ),

    Article(
        number=6,
        title="Pouvoirs de l'Agent Justice",
        text=(
            "L'Agent Justice est le seul agent habilite a proposer des amendements "
            "a la presente Constitution. "
            "Il opere de facon independante, consulte la base vectorielle "
            "(knowledge/vector_store.py), les rapports des agents observateurs, "
            "et les metriques de l'Agent RH. "
            "Chaque proposition d'amendement doit etre accompagnee : "
            "(a) d'une justification basee sur des evidences quantifiees, "
            "(b) d'une simulation d'impact sur les seuils operationnels, "
            "(c) d'une periode d'observation recommandee avant adoption. "
            "L'amendement entre en vigueur uniquement apres validation humaine explicite."
        ),
    ),

    Article(
        number=7,
        title="Processus d'amendement",
        text=(
            "Toute modification de la Constitution suit le processus formel suivant : "
            "1. L'Agent Justice produit une PropositionAmendement formalisee. "
            "2. La proposition est archivee dans knowledge/amendments/ avec horodatage. "
            "3. Une periode d'observation de minimum 7 jours doit s'ecouler. "
            "4. La validation humaine est requise (flag validated=True dans le JSON). "
            "5. Apres validation, le code operationnel est mis a jour pour reflechir "
            "le nouvel article. "
            "6. L'ancienne version est preservee dans l'historique (version N-1). "
            "Aucun agent ne peut auto-amender la Constitution."
        ),
    ),
]

# Index par numero pour acces rapide
ARTICLES_BY_NUMBER: dict[int, Article] = {a.number: a for a in ARTICLES}

# Metadonnees Constitution
CONSTITUTION_VERSION = "1.0"
CONSTITUTION_DATE    = date(2026, 3, 13)
CONSTITUTION_AUTHOR  = "FinSight IA — Phase 9 Gouvernance"


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_article(number: int) -> Optional[Article]:
    """Retourne un Article par son numero (1-7), None si inexistant."""
    return ARTICLES_BY_NUMBER.get(number)


def get_threshold(key: str) -> Optional[float]:
    """Retourne le seuil operationnel associe a une cle (ex: 'confidence_score')."""
    for art in ARTICLES:
        if art.threshold_key == key:
            return art.threshold
    return None


def check_compliance(state: dict) -> list[dict]:
    """
    Verifie la conformite d'un FinSightState (ou dict generique) par rapport
    aux articles a seuil numerique.
    Retourne une liste de violations {article, threshold, actual, compliant}.
    """
    violations = []
    for art in ARTICLES:
        if art.threshold is None or art.threshold_key is None:
            continue
        actual = state.get(art.threshold_key)
        if actual is None:
            continue
        # Article 1 & 2 : valeur doit etre >= seuil
        # Article 3 : valeur doit etre <= seuil (nb de retries)
        if art.number == 3:
            compliant = float(actual) <= art.threshold
        else:
            compliant = float(actual) >= art.threshold
        violations.append({
            "article":   art.number,
            "title":     art.title,
            "threshold": art.threshold,
            "actual":    actual,
            "compliant": compliant,
        })
    return violations


def summary() -> str:
    """Retourne un resume textuel de la Constitution."""
    lines = [
        f"Constitution FinSight IA v{CONSTITUTION_VERSION} ({CONSTITUTION_DATE})",
        "=" * 60,
    ]
    for art in ARTICLES:
        thr = f" [seuil: {art.threshold}]" if art.threshold is not None else ""
        lines.append(f"Art.{art.number} — {art.title}{thr}")
    return "\n".join(lines)
