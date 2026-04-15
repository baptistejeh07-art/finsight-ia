"""
tools/test_render_llm.py — FinSight IA
Tests unitaires pour _render_llm_structured (sans LLM, 100% local).

Usage :
  python tools/test_render_llm.py

Objectif : valider que le helper parse correctement les outputs LLM avec
differents formats (markdown, tirets, accents, separateurs ---, numerotation)
et extrait les sous-titres correctement.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from outputs.pdf_writer import _render_llm_structured, S_SUBSECTION, S_BODY


class MockParagraph:
    """Mock ReportLab Paragraph pour inspection test."""
    def __init__(self, text, style):
        self.text = text
        self.style = style

    def __repr__(self):
        style_name = getattr(self.style, 'name', 'unknown')
        return f"Para[{style_name}]({self.text[:50]!r})"


class MockSpacer:
    def __init__(self, w, h):
        self.w, self.h = w, h

    def __repr__(self):
        return f"Spacer({self.h})"


# Monkey patch Paragraph and Spacer to avoid ReportLab dependency issue
import outputs.pdf_writer as pw
_orig_Paragraph = pw.Paragraph
_orig_Spacer = pw.Spacer
pw.Paragraph = MockParagraph
pw.Spacer = MockSpacer


def run_test(name: str, text: str, section_map: dict = None,
             expect_subtitles: list = None, expect_paragraphs: int = None) -> bool:
    """Run un test et valide les assertions."""
    elems = []
    _render_llm_structured(elems, text, section_map=section_map)

    # Compte les Paragraph (en excluant les Spacer)
    paragraphs = [e for e in elems if isinstance(e, MockParagraph)]
    subtitles = [p.text for p in paragraphs if hasattr(p.style, 'name') and 'subsec' in getattr(p.style, 'name', '').lower()]
    # Alternative : les subsection ont S_SUBSECTION en style (same object as S_SUBSECTION)
    subtitles = [p.text for p in paragraphs if p.style is S_SUBSECTION]

    errors = []
    if expect_subtitles is not None:
        for title in expect_subtitles:
            if not any(title in s for s in subtitles):
                errors.append(f"Missing subtitle: {title!r} (got: {subtitles})")

    if expect_paragraphs is not None:
        if len(paragraphs) < expect_paragraphs:
            errors.append(f"Expected >= {expect_paragraphs} paragraphs, got {len(paragraphs)}")

    status = "OK" if not errors else "FAIL"
    print(f"[{status}] {name}")
    for err in errors:
        print(f"       - {err}")
    if not errors:
        return True
    return False


def main():
    print("=" * 70)
    print("  TESTS _render_llm_structured")
    print("=" * 70)

    results = []

    # ─── CAS 1 : Format standard attendu ───────────────────────────────
    results.append(run_test(
        "1. Format standard TITRE MAJ : body",
        text=(
            "TENDANCE : Le P/E de MSFT est passe de 30x a 28x sur 5 ans.\n\n"
            "MEAN-REVERSION : Les multiples convergent vers la moyenne.\n\n"
            "CONCLUSION : Le niveau est soutenable."
        ),
        section_map={
            "TENDANCE": "Tendance des multiples",
            "MEAN-REVERSION": "Mean-reversion",
            "CONCLUSION": "Conclusion",
        },
        expect_subtitles=["Tendance des multiples", "Mean-reversion", "Conclusion"],
        expect_paragraphs=6,  # 3 subtitles + 3 bodies
    ))

    # ─── CAS 2 : Markdown bold **TITRE** au debut ──────────────────────
    results.append(run_test(
        "2. Markdown bold **TITRE** au debut",
        text=(
            "**ATTRACTIVITE CIBLE** : Microsoft presente des caracteristiques robustes.\n\n"
            "**LEVIER** : Le profil de levier est solide.\n\n"
            "**CREATION DE VALEUR** : Trois leviers principaux."
        ),
        section_map={
            "ATTRACTIVITE CIBLE": "Attractivite en tant que cible PE",
            "LEVIER": "Capacite d'endettement",
            "CREATION DE VALEUR": "Leviers de creation de valeur",
        },
        expect_subtitles=[
            "Attractivite en tant que cible PE",
            "Capacite d'endettement",
            "Leviers de creation de valeur",
        ],
        expect_paragraphs=6,
    ))

    # ─── CAS 3 : Titres avec tirets (MEAN-REVERSION, RE-RATING) ────────
    results.append(run_test(
        "3. Titres avec tirets dans le nom",
        text=(
            "MEAN-REVERSION : Les multiples reviennent vers leur moyenne.\n\n"
            "RE-RATING : Potentiel de re-rating positif."
        ),
        expect_subtitles=["MEAN-REVERSION", "RE-RATING"],
        expect_paragraphs=4,
    ))

    # ─── CAS 4 : Separateurs --- entre paragraphes ─────────────────────
    results.append(run_test(
        "4. Separateurs --- dans le texte LLM",
        text=(
            "QUALITE FCF : Le FCF est stable.\n"
            "---\n"
            "ALLOCATION : Les capex sont bien geres.\n"
            "---\n"
            "CONCLUSION : Le profil est solide."
        ),
        section_map={
            "QUALITE FCF": "Qualite du FCF",
            "ALLOCATION": "Allocation du capital",
            "CONCLUSION": "Conclusion",
        },
        expect_subtitles=["Qualite du FCF", "Allocation du capital", "Conclusion"],
        expect_paragraphs=6,
    ))

    # ─── CAS 5 : Numerotation 1. 2. 3. devant les titres ───────────────
    results.append(run_test(
        "5. Numerotation devant titres",
        text=(
            "1. TENDANCE : Le P/E est stable.\n\n"
            "2. VALUATION : Les multiples reflettent la qualite.\n\n"
            "3. CONCLUSION : Niveau soutenable."
        ),
        expect_subtitles=["TENDANCE", "VALUATION", "CONCLUSION"],
        expect_paragraphs=6,
    ))

    # ─── CAS 6 : Accents dans les titres ───────────────────────────────
    results.append(run_test(
        "6. Accents francais dans titres",
        text=(
            "QUALITE MARGES : Marges robustes.\n\n"
            "STRUCTURE COUTS : Couts optimises.\n\n"
            "POSITIONNEMENT : Leader du marche."
        ),
        section_map={
            "QUALITE MARGES": "Qualité des marges",
            "STRUCTURE COUTS": "Structure de coûts",
            "POSITIONNEMENT": "Positionnement concurrentiel",
        },
        expect_subtitles=[
            "Qualité des marges",
            "Structure de coûts",
            "Positionnement concurrentiel",
        ],
        expect_paragraphs=6,
    ))

    # ─── CAS 7 : Format mixte markdown + tirets + accents ──────────────
    results.append(run_test(
        "7. Format mixte : **MEAN-REVERSION** + accents",
        text=(
            "**MEAN-REVERSION** : Les multiples actuels sont en dessous de leur moyenne.\n\n"
            "**RE-RATING** : Catalyseurs d'expansion a surveiller."
        ),
        expect_subtitles=["MEAN-REVERSION", "RE-RATING"],
        expect_paragraphs=4,
    ))

    # ─── CAS 8 : Texte sans sous-titres (paragraphes simples) ──────────
    results.append(run_test(
        "8. Texte sans sous-titres (MC Interp)",
        text=(
            "Le modele GBM predit un cours median de 374 USD.\n\n"
            "Les limites du GBM sont importantes.\n\n"
            "L'usage du P50 doit etre croise avec le DCF."
        ),
        expect_subtitles=[],  # aucun sous-titre attendu
        expect_paragraphs=3,  # juste 3 body paragraphs
    ))

    # ─── CAS 9 : Triple --- avec \\n multiples ─────────────────────────
    results.append(run_test(
        "9. Separateurs varies et newlines multiples",
        text=(
            "SECTION A : Texte A.\n\n\n\n"
            "=== \n"
            "SECTION B : Texte B.\n\n"
            "***\n"
            "SECTION C : Texte C."
        ),
        expect_paragraphs=6,  # 3 titles + 3 bodies
    ))

    # ─── CAS 10 : Titre avec chiffres (BENCHMARK 2024) ─────────────────
    results.append(run_test(
        "10. Titres avec chiffres (BENCHMARK 2024)",
        text=(
            "BENCHMARK 2024 : Comparaison vs pairs.\n\n"
            "IRR 20% : Rendement cible atteint."
        ),
        expect_paragraphs=4,
    ))

    # ─── CAS 11 : Long paragraphe sans titre (fallback body) ───────────
    results.append(run_test(
        "11. Long paragraphe sans titre",
        text=(
            "Ce texte est un paragraphe long sans structure. Il contient plusieurs "
            "phrases mais pas de titre. Le helper doit le rendre comme body simple "
            "sans extraction de titre."
        ),
        expect_subtitles=[],
        expect_paragraphs=1,
    ))

    # ─── CAS 12 : Empty string ────────────────────────────────────────
    results.append(run_test(
        "12. String vide",
        text="",
        expect_paragraphs=0,
    ))

    # ─── CAS 13 : Whitespace only ─────────────────────────────────────
    results.append(run_test(
        "13. Whitespace only",
        text="   \n\n\n   ",
        expect_paragraphs=0,
    ))

    # ─── CAS 14 : Section_map avec accent vs sans accent ──────────────
    results.append(run_test(
        "14. Section_map insensible aux accents",
        text="QUALITE FCF : Le cash flow est robuste.",
        section_map={"QUALITE FCF": "Qualité du FCF"},
        expect_subtitles=["Qualité du FCF"],
    ))

    # ─── CAS 15 : Titre tres long (proche limite 60 chars) ─────────────
    results.append(run_test(
        "15. Titre long (50+ chars)",
        text="CAPACITE D'ENDETTEMENT ET LEVIER SOUTENABLE : Marge confortable.",
        expect_subtitles=["CAPACITE D'ENDETTEMENT ET LEVIER SOUTENABLE"],
    ))

    # ─── CAS 16 : Em dash separateur (PF : texte) ─────────────────────
    results.append(run_test(
        "16. Em dash au lieu de colon",
        text="TENDANCE - Les multiples sont stables sur 5 ans.",
        expect_subtitles=["TENDANCE"],
    ))

    # ─── CAS 17 : Titre avec apostrophe ────────────────────────────────
    results.append(run_test(
        "17. Titre avec apostrophe (L'ENDETTEMENT)",
        text="CAPACITE D'ENDETTEMENT : Marge financiere solide.",
        expect_subtitles=["CAPACITE D'ENDETTEMENT"],
    ))

    # ─── CAS 18 : Triple ** et __ (markdown variations) ───────────────
    results.append(run_test(
        "18. Markdown variations ** et __",
        text=(
            "**QUALITE** : Premiere section.\n\n"
            "__RISQUES__ : Deuxieme section."
        ),
        expect_subtitles=["QUALITE", "RISQUES"],
    ))

    # ─── CAS 19 : Multi-paragraphe avec body contenant des : ──────────
    results.append(run_test(
        "19. Body contient des colons (faux positifs a eviter)",
        text=(
            "TENDANCE : Le multiple est de 28x : c'est stable. "
            "En 2023 il etait de 30x : leger recul depuis."
        ),
        expect_subtitles=["TENDANCE"],
        expect_paragraphs=2,  # 1 title + 1 body
    ))

    # ─── CAS 20 : Format "1. TITRE MAJUSCULE : body" ───────────────────
    results.append(run_test(
        "20. Format 'N. TITRE : body' combine",
        text=(
            "1. TENDANCE : Multiples stables.\n\n"
            "2. MEAN-REVERSION : Retour a la moyenne.\n\n"
            "3. CONCLUSION : Niveau soutenable."
        ),
        expect_subtitles=["TENDANCE", "MEAN-REVERSION", "CONCLUSION"],
        expect_paragraphs=6,
    ))

    # ─── CAS 21 : Premier paragraphe SANS titre, suivants AVEC ─────────
    # Edge case observe sur AAPL : le LLM oublie parfois le titre du
    # premier paragraphe. Le helper doit injecter le premier key du
    # section_map par defaut.
    results.append(run_test(
        "21. 1er paragraphe sans titre, suivants avec (injection default)",
        text=(
            "Apple affiche une qualite operationnelle exceptionnelle, "
            "avec des marges brutes de 46.9%.\n\n"
            "STRUCTURE COUTS : La structure de couts d'Apple est optimisee.\n\n"
            "POSITIONNEMENT : Apple beneficie d'un moat multidimensionnel."
        ),
        section_map={
            "QUALITE MARGES":     "Qualite des marges",
            "STRUCTURE COUTS":    "Structure de couts",
            "POSITIONNEMENT":     "Positionnement concurrentiel",
        },
        expect_subtitles=[
            "Qualite des marges",
            "Structure de couts",
            "Positionnement concurrentiel",
        ],
        expect_paragraphs=6,
    ))

    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"  RESULTAT : {passed}/{total} tests passent")
    print("=" * 70)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
