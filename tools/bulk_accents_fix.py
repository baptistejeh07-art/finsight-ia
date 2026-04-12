"""Correction bulk des accents français dans les strings Python.
Utilise une regex pour ne remplacer que dans les strings, pas dans les identifiants.
"""
import re
import sys
import ast
from pathlib import Path

REPLACEMENTS = {
    # Adjectifs accordés
    'elevee': 'élevée', 'elevees': 'élevées', 'eleves': 'élevés', 'eleve ': 'élevé ',
    'Elevee': 'Élevée', 'Eleves': 'Élevés', 'Eleve ': 'Élevé ',
    'moderee': 'modérée', 'moderees': 'modérées', 'moderes': 'modérés', 'modere ': 'modéré ',
    'Moderee': 'Modérée', 'Modere ': 'Modéré ',
    'fragmente': 'fragmenté', 'fragmentes': 'fragmentés',
    'fragmentee': 'fragmentée', 'fragmentees': 'fragmentées',
    'Decote': 'Décote', 'decote': 'décote', 'decotes': 'décotes', 'decotee': 'décotée',
    'normalise': 'normalisé', 'normalisee': 'normalisée',
    'normalises': 'normalisés', 'normalisees': 'normalisées',
    'elaboree': 'élaborée',
    # Noms français
    'mediane': 'médiane', 'medianes': 'médianes',
    'Mediane': 'Médiane', 'Medianes': 'Médianes',
    'rentabilite': 'rentabilité', 'rentabilites': 'rentabilités',
    'selectivite': 'sélectivité',
    'strategique': 'stratégique', 'strategiques': 'stratégiques',
    'Strategique': 'Stratégique',
    'heterogene': 'hétérogène', 'heterogenes': 'hétérogènes',
    'specificite': 'spécificité', 'specificites': 'spécificités',
    'generation': 'génération', 'generations': 'générations',
    'caracteristique': 'caractéristique', 'caracteristiques': 'caractéristiques',
    'periode': 'période', 'periodes': 'périodes',
    'criteres': 'critères', 'critere ': 'critère ',
    'representatif': 'représentatif', 'representatifs': 'représentatifs',
    'representative': 'représentative',
    'developpement': 'développement', 'developpements': 'développements',
    'ecosysteme': 'écosystème',
    'Resultats': 'Résultats', 'resultats': 'résultats',
    'Recession': 'Récession', 'recession': 'récession',
    'Regulation': 'Régulation',
    'revision': 'révision', 'Revision': 'Révision', 'revisions': 'révisions',
    'Amelioration': 'Amélioration', 'amelioration': 'amélioration',
    'Negatif': 'Négatif', 'negatif': 'négatif',
    'evenements': 'événements', 'Evenements': 'Événements',
    'Themes': 'Thèmes', 'themes': 'thèmes',
    'evaluation': 'évaluation', 'reevaluation': 'réévaluation',
    'eleves penalise': 'élevés pénalise',
    'interet': 'intérêt', 'interets': 'intérêts',
    'superieure': 'supérieure', 'superieur': 'supérieur',
    'superieures': 'supérieures', 'superieurs': 'supérieurs',
    'inferieure': 'inférieure', 'inferieur': 'inférieur',
    'inferieures': 'inférieures', 'inferieurs': 'inférieurs',
    'generateur': 'générateur', 'generateurs': 'générateurs',
    'reflete': 'reflète', 'refletent': 'reflètent',
    'sensibilite': 'sensibilité',
    'asymetrie': 'asymétrie', 'asymetries': 'asymétries',
    'asymetrique': 'asymétrique',
    'derriere': 'derrière', 'derniere': 'dernière', 'premiere': 'première',
    'dernieres': 'dernières', 'premieres': 'premières',
    'integree': 'intégrée', 'integre ': 'intègre ', 'integres': 'intégrés',
    'integrees': 'intégrées',
    'diversifie': 'diversifié', 'diversifiee': 'diversifiée',
    'positionne': 'positionné', 'positionnee': 'positionnée',
    'positionnes': 'positionnés', 'positionnees': 'positionnées',
    # Participes passés
    'genere ': 'généré ', 'generee': 'générée',
    'gener� par IA': 'généré par IA',
    'Document genere par IA': 'Document généré par IA',
    'Document gener� par IA': 'Document généré par IA',
    'genere par IA': 'généré par IA',
    'pondere': 'pondéré', 'ponderee': 'pondérée',
    'ponderes': 'pondérés', 'ponderees': 'pondérées',
    'traitee': 'traitée', 'traites': 'traités', 'traitees': 'traitées',
    'etabli ': 'établi ', 'etablie': 'établie',
    'etablis': 'établis', 'etablies': 'établies',
    'etudie': 'étudié', 'etudiee': 'étudiée',
    'protege ': 'protégé ', 'protegee': 'protégée',
    'justifie ': 'justifié ', 'justifiee': 'justifiée',
    'justifies ': 'justifiés ', 'justifiees ': 'justifiées ',
    'compresse ': 'compressé ', 'compressee': 'compressée',
    'accelere ': 'accéléré ', 'acceleree': 'accélérée',
    'differencie': 'différencié', 'differenciee': 'différenciée',
    'differencies': 'différenciés', 'differenciees': 'différenciées',
    # Mots courants
    'donnees financieres': 'données financières',
    'donnees ': 'données ',
    'Donnees ': 'Données ',
    'fiabilite': 'fiabilité',
    'probabilite': 'probabilité', 'probabilites': 'probabilités',
    'Probabilite': 'Probabilité', 'Probabilites': 'Probabilités',
    'presse financiere': 'presse financière',
    'financieres': 'financières', 'financiere ': 'financière ',
    'activite': 'activité', 'activites': 'activités',
    'opportunite': 'opportunité', 'opportunites': 'opportunités',
    'liquidite': 'liquidité', 'liquidites': 'liquidités',
    'volatilite': 'volatilité',
    'qualite': 'qualité', 'qualites': 'qualités',
    'Qualite': 'Qualité',
    'rentabilite': 'rentabilité',
    'disponibilite': 'disponibilité',
    'visibilite': 'visibilité',
    'credibilite': 'crédibilité',
    'specialise': 'spécialisé', 'specialisee': 'spécialisée',
    'adequat': 'adéquat', 'adequate': 'adéquate',
    'adequats': 'adéquats', 'adequates': 'adéquates',
    'detresse': 'détresse',
    'strategie ': 'stratégie ', 'strategies': 'stratégies',
    'Strategie': 'Stratégie',
    'progresse ': 'progressé ', 'progressee': 'progressée',
    'reglementaire': 'réglementaire', 'reglementaires': 'réglementaires',
    'Reglementaire': 'Réglementaire',
    'tresorerie': 'trésorerie',
    'levier excessif': 'levier excessif',  # ok
    'Levier excessif': 'Levier excessif',  # ok
    'regulier': 'régulier', 'reguliers': 'réguliers',
    'reguliere': 'régulière', 'regulieres': 'régulières',
    'secteur fragmentees': 'secteur fragmenté',
    'A l\'inverse': 'À l\'inverse',
    'a l\'inverse': 'à l\'inverse',
    'apres': 'après',
    'tres ': 'très ',
    'Tres ': 'Très ',
    'methodologie': 'méthodologie',
    'Methodologie': 'Méthodologie',
    'methodologique': 'méthodologique',
    'echeance': 'échéance', 'echeances': 'échéances',
    'theme ': 'thème ', 'Themes principaux': 'Thèmes principaux',
    'incoherence': 'incohérence', 'Incoherence': 'Incohérence',
    'coherence': 'cohérence',
    'coherent ': 'cohérent ', 'coherente': 'cohérente',
    'coherents': 'cohérents', 'coherentes': 'cohérentes',
    'experiment': 'expériment',
    'experience': 'expérience',
    'retrocession': 'rétrocession',
    'execute ': 'exécute ', 'executee': 'exécutée',
    'execution': 'exécution',
    'internationale': 'internationale',  # ok
    'international ': 'international ',  # ok
    'confidentialite': 'confidentialité',
    'fideliser': 'fidéliser',
    'penurie': 'pénurie',
    'penalise': 'pénalise',
    'sante': 'santé',  # (sauf dans les cas particuliers)
    'retention': 'rétention',
    'operationnel': 'opérationnel', 'operationnels': 'opérationnels',
    'operationnelle': 'opérationnelle', 'operationnelles': 'opérationnelles',
    'Operationnel': 'Opérationnel',
    'conservateur recommande': 'conservateur recommandé',
    'non disponible': 'non disponible',
    'deteriore': 'détériore',
    'deterioration': 'détérioration',
    'Deterioration': 'Détérioration',
    'a l\'entree': 'à l\'entrée',
    'a l\'entree elevees': 'à l\'entrée élevées',
    'barriere': 'barrière', 'barrieres': 'barrières',
    'Barriere': 'Barrière', 'Barrieres': 'Barrières',
    'dependance': 'dépendance',
    'depend ': 'dépend ', 'dependent': 'dépendent',
    'gestionnaire': 'gestionnaire',  # ok
    'etalon': 'étalon',
    'Lecture croisee': 'Lecture croisée',
    'lecture croisee': 'lecture croisée',
    'coherente': 'cohérente',
    'regulatoire': 'régulatoire', 'regulatoires': 'régulatoires',
    'renforcement': 'renforcement',  # ok
    'Retour capital': 'Retour capital',  # ok
    'Publication guidance': 'Publication guidance',  # ok
    'cash actionnaires': 'cash actionnaires',  # ok
    'conformite': 'conformité',
    'marquee': 'marquée', 'marquees': 'marquées',
    'Marquee': 'Marquée',
    'degradation': 'dégradation',
    'Degradation': 'Dégradation',
    # Adverbes
    'historiquement': 'historiquement',  # ok
    'actuellement': 'actuellement',  # ok
    'potentiellement': 'potentiellement',  # ok
    'generalement': 'généralement',
    'parallellement': 'parallèlement',
    'notamment': 'notamment',  # ok
    'definitivement': 'définitivement',
    'structurellement': 'structurellement',  # ok
    'transitoirement': 'transitoirement',  # ok
    'lineairement': 'linéairement',
    'eventuellement': 'éventuellement',
    'effectivement': 'effectivement',  # ok
    # Verbes
    'beneficie ': 'bénéficie ', 'beneficient': 'bénéficient',
    'beneficier': 'bénéficier',
    'fragmente': 'fragmenté',
    'se differencie': 'se différencie',  # ok
    'demontrer': 'démontrer',
    'renegociation': 'renégociation',
    'degenerer': 'dégénérer',
    'regenerer': 'régénérer',
    'verifier': 'vérifier',
    # "S&P; 500" → "S&P 500" (artefact XML)
    'S&P;&nbsp;500': 'S&amp;P 500',
    'S&P; 500': 'S&amp;P 500',
}


def fix_file(filepath: str) -> int:
    """Applique les corrections sur un fichier, return nb de remplacements."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    count = 0

    for old, new in REPLACEMENTS.items():
        # Pattern : remplacer old seulement s'il est dans une string (entre " ou ')
        # Simple approche : regex globale, pour les mots qui ne sont PAS des identifiants
        # Python. On check qu'ils sont précédés/suivis par un caractère non-identifiant
        # OU qu'ils sont au début/fin de ligne dans un contexte string.
        # Approche safe : on remplace seulement dans les littéraux strings.
        # Pattern pour matcher une string : "..." ou '...'
        def replace_in_strings(m):
            nonlocal count
            s = m.group(0)
            if old in s:
                n = s.count(old)
                count += n
                return s.replace(old, new)
            return s
        # Strings à double ou simple quote (sans gestion multiline pour simplicité)
        content = re.sub(r'"[^"\n]*"', replace_in_strings, content)
        content = re.sub(r"'[^'\n]*'", replace_in_strings, content)

    if content != original:
        # Vérifier syntaxe avant d'écrire
        try:
            ast.parse(content)
        except SyntaxError as e:
            print(f'  SYNTAX ERROR dans {filepath}: {e}', file=sys.stderr)
            return 0
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return count


def main():
    outputs_dir = Path('outputs')
    total = 0
    for py_file in sorted(outputs_dir.glob('*.py')):
        if py_file.name in ('__init__.py',):
            continue
        n = fix_file(str(py_file))
        if n > 0:
            print(f'  {py_file.name:40} {n:4} remplacements')
        total += n
    print(f'\nTOTAL : {total} remplacements')


if __name__ == '__main__':
    main()
