"""
core/glossary.py — Glossaire contextuel FinSight IA.

Chaque carte du glossaire est associée à un ensemble de contextes où elle
est pertinente. Le rendu dans l'app.py filtre les cartes selon :

  - type_analyse : "societe" | "secteur" | "indice" | "cmp_societe" |
                   "cmp_secteur" | "cmp_indice"
  - profile      : "STANDARD" | "BANK" | "INSURANCE" | "REIT" | "UTILITY" |
                   "OIL_GAS" (pour le mode "societe")

Convention : chaque card déclare `contexts` = set de slugs du type :
  - "societe:STANDARD" / "societe:BANK" / "societe:INSURANCE" / ...
  - "secteur"
  - "indice"
  - "cmp_societe" / "cmp_secteur" / "cmp_indice"
  - "societe:*" = toutes les sociétés (tous profils)

On peut aussi utiliser des wildcards : "societe:*" couvre tous les profils.
"""
from __future__ import annotations

from typing import Iterable


# ═════════════════════════════════════════════════════════════════════════════
# CARTES DU GLOSSAIRE — chacune taguée par contexte
# ═════════════════════════════════════════════════════════════════════════════

GlossaryCard = dict  # {"title": str, "entries": [(term, def)], "contexts": set[str]}


_CARDS: list[GlossaryCard] = [
    # --------------------------------------------------------------------------
    # Valorisation corporate (STANDARD)
    # --------------------------------------------------------------------------
    {
        "title": "Valorisation",
        "contexts": {"societe:STANDARD", "societe:UTILITY", "societe:OIL_GAS",
                     "secteur", "indice", "cmp_societe", "cmp_secteur", "cmp_indice"},
        "entries": [
            ("PER (P/E)", "Prix / Bénéfice par action. Indique combien le marché paie pour 1 EUR de bénéfice. Un PER élevé reflète des attentes de croissance."),
            ("EV/EBITDA", "Valeur d'entreprise / EBITDA. Multiple de valorisation indépendant de la structure de capital et fiscalité."),
            ("FCF Yield", "Free Cash Flow / Market Cap. Rendement du cash généré après investissements. Plus élevé = meilleur."),
            ("PEG", "PER / Taux de croissance des bénéfices. PEG <1 suggère une valorisation attractive relativement à la croissance."),
            ("DCF", "Discounted Cash Flow. Valorisation par actualisation des flux futurs estimés au taux WACC. Dépend fortement des hypothèses de croissance."),
            ("P/S (Price-to-Sales)", "Prix / Chiffre d'affaires. Utilisé pour les sociétés sans EBITDA positif (SaaS, biotech en croissance)."),
        ],
    },
    # --------------------------------------------------------------------------
    # Valorisation BANK / INSURANCE — P/TBV, P/B, ROE > COE
    # --------------------------------------------------------------------------
    {
        "title": "Valorisation (banques/assurance)",
        "contexts": {"societe:BANK", "societe:INSURANCE"},
        "entries": [
            ("P/TBV", "Prix / Tangible Book Value. Multiple central pour les banques, exclut goodwill et intangibles. <1 = décote sur capital tangible."),
            ("P/B (Price-to-Book)", "Prix / Valeur comptable. Rapport capitalisation / actif net comptable. <1 = potentielle sous-valorisation, >1,5 = prime pour ROE élevé."),
            ("P/E Forward", "Prix / BPA consensus 12 mois. Reste une métrique clé pour mesurer le pricing de la rentabilité future des institutions financières."),
            ("ROE vs COE", "Return on Equity vs Coût des fonds propres. Banque crée de la valeur si ROE > COE (typiquement 9-11%). Spread ROE-COE = vrai moteur du P/B."),
            ("Dividend Yield", "Dividende annuel / cours. Métrique clé pour les financières (distribution régulière) — à croiser avec payout ratio et stabilité."),
        ],
    },
    # --------------------------------------------------------------------------
    # Valorisation REIT — P/FFO, NAV discount, Cap Rate
    # --------------------------------------------------------------------------
    {
        "title": "Valorisation (foncières / REIT)",
        "contexts": {"societe:REIT"},
        "entries": [
            ("P/FFO", "Prix / Funds From Operations. Multiple standard REIT — FFO = Net Income + D&A - Gains immobiliers. Remplace P/E (biaisé par dépréciations)."),
            ("P/AFFO", "Prix / Adjusted FFO. FFO - capex de maintenance. Approxime le FCF distribuable. Typique 15-25x selon segment."),
            ("NAV Discount/Premium", "Décote/prime du cours vs Net Asset Value par action. Décote > 15% = opportunité value, prime > 10% = narrative forte."),
            ("Cap Rate", "Taux de capitalisation = NOI / Valeur immobilier. Spread vs taux 10Y = prime de risque immobilier. Cap Rate bas = actifs premium."),
            ("Dividend Yield REIT", "Rendement distribué — REITs obligés de distribuer 90%+ du revenu imposable. Typiquement 3-6%, sensible aux taux."),
            ("Debt/EBITDA REIT", "Levier spécifique foncières — 5-7x normal, > 9x signale stress. À croiser avec DSCR (Debt Service Coverage Ratio)."),
        ],
    },
    # --------------------------------------------------------------------------
    # Valorisation OIL & GAS — EV/Production, reserves
    # --------------------------------------------------------------------------
    {
        "title": "Valorisation (pétrole & gaz)",
        "contexts": {"societe:OIL_GAS"},
        "entries": [
            ("EV/DACF", "EV / Debt Adjusted Cash Flow. Multiple sectoriel O&G, corrige EBITDA de la dette financière. Alternative plus fine à EV/EBITDA."),
            ("EV/Reserves", "EV / Réserves prouvées (bbl ou Mcf). Valorise chaque baril en terre. Comparable par segment (upstream, offshore, shale)."),
            ("Breakeven Price", "Prix pétrole/gaz à partir duquel la production devient profitable. Décote majeure pour majors avec breakeven < 40 USD/bbl."),
            ("Reserve Life Index", "Réserves prouvées / Production annuelle. Exprimé en années. > 12 ans = profil long, < 7 ans = production en déclin."),
        ],
    },
    # --------------------------------------------------------------------------
    # Profitabilité corporate (STANDARD + UTILITY + OIL_GAS)
    # --------------------------------------------------------------------------
    {
        "title": "Profitabilité",
        "contexts": {"societe:STANDARD", "societe:UTILITY", "societe:OIL_GAS",
                     "secteur", "indice", "cmp_societe", "cmp_secteur"},
        "entries": [
            ("EBITDA Margin", "EBITDA / CA. Marge opérationnelle avant amortissements, intérêts et impôts. Reflet de la rentabilité brute d'exploitation."),
            ("EBIT Margin", "EBIT / CA. Marge opérationnelle après amortissements. Reflète l'efficacité opérationnelle réelle."),
            ("Net Margin", "Résultat net / CA. Part du CA restant après toutes charges. Dépend aussi de l'effet de levier et de la fiscalité."),
            ("ROIC", "Return on Invested Capital. NOPAT / Capital investi. Mesure la capacité à créer de la valeur sur les capitaux déployés. ROIC > WACC = création de valeur."),
            ("ROE", "Return on Equity. Résultat net / Fonds propres. Rentabilité pour l'actionnaire. Peut être gonflé par l'endettement."),
            ("CAGR CA 3 ans", "Taux de croissance annualisé du chiffre d'affaires sur 3 ans."),
        ],
    },
    # --------------------------------------------------------------------------
    # Profitabilité banques
    # --------------------------------------------------------------------------
    {
        "title": "Profitabilité (banques)",
        "contexts": {"societe:BANK"},
        "entries": [
            ("NIM", "Net Interest Margin. (Intérêts perçus - Intérêts payés) / Actifs rémunérateurs. Cœur de rentabilité bancaire — typiquement 1,5-3,5%."),
            ("Cost/Income Ratio", "Charges opérationnelles / Produit net bancaire. Mesure d'efficacité. Banques de détail ~55-65%, banques d'investissement ~65-75%."),
            ("ROA", "Return on Assets. Résultat net / Total bilan. Mesure de rendement moins biaisée par le levier que le ROE. Banque saine : ROA > 0,8%."),
            ("ROE", "Return on Equity — mesure centrale pour les banques. ROE > 10% sur cycle = création de valeur. À comparer au COE (8-10%)."),
            ("Provisions (Cost of Risk)", "Provisions pour risque de crédit / Encours. Reflète la qualité des portefeuilles de prêts. 30-50bps = normal, > 100bps = stress."),
        ],
    },
    # --------------------------------------------------------------------------
    # Profitabilité assurance
    # --------------------------------------------------------------------------
    {
        "title": "Profitabilité (assurance)",
        "contexts": {"societe:INSURANCE"},
        "entries": [
            ("Combined Ratio", "(Sinistres + Frais) / Primes acquises. Métrique clé P&C. <100% = souscription profitable, >100% = sinistres + frais > primes."),
            ("Loss Ratio", "Sinistres / Primes acquises. Mesure la sinistralité pure (hors frais). Varie fortement par branche (auto ~70%, habitation ~65%)."),
            ("Expense Ratio", "Frais / Primes acquises. Efficacité opérationnelle de la souscription et gestion. Typique 25-30%."),
            ("Solvency II Ratio", "Fonds propres éligibles / SCR (capital règlementaire). > 150% = confortable, <130% = pression régulatoire."),
            ("ROE assurance", "Résultat net / Fonds propres. 9-12% sur cycle pour groupes diversifiés. Composé de underwriting + investment income + dividends."),
            ("Embedded Value", "Valeur actuelle des profits futurs des contrats existants (vie). Alternative à P/B pour les assureurs-vie."),
        ],
    },
    # --------------------------------------------------------------------------
    # Profitabilité REIT
    # --------------------------------------------------------------------------
    {
        "title": "Profitabilité (foncières)",
        "contexts": {"societe:REIT"},
        "entries": [
            ("NOI", "Net Operating Income. Loyers - Charges d'exploitation. Indépendant de la structure financière. Base du Cap Rate."),
            ("Same-Store NOI Growth", "Croissance organique du NOI sur périmètre constant (hors acquisitions/cessions). Meilleur indicateur de pricing power."),
            ("FFO Growth", "Croissance FFO par action. Moteur principal du P/FFO et du dividende. Objectif : 3-6% sur cycle."),
            ("Occupancy Rate", "% des surfaces louées. Benchmarks : résidentiel ~95%+, bureaux core ~92%+, retail ~90%+."),
        ],
    },
    # --------------------------------------------------------------------------
    # Structure financière corporate
    # --------------------------------------------------------------------------
    {
        "title": "Structure financière & Levier",
        "contexts": {"societe:STANDARD", "societe:UTILITY", "societe:OIL_GAS", "societe:REIT",
                     "secteur", "indice", "cmp_societe", "cmp_secteur"},
        "entries": [
            ("ND/EBITDA", "Dette nette / EBITDA. Nb d'années d'EBITDA pour rembourser la dette nette. <2x = faible levier, >4x = levier élevé."),
            ("Interest Coverage", "EBIT / Frais financiers. Capacité à couvrir les intérêts. <1,5x = zone de risque."),
            ("Current Ratio", "Actifs courants / Passifs courants. Liquidité à court terme. >1 = couverture des dettes court terme."),
            ("Quick Ratio", "Actifs liquides (sans stocks) / Passifs courants. Version stricte du current ratio."),
            ("WACC", "Weighted Average Cost of Capital. Coût moyen pondéré du capital (dette + fonds propres). Taux d'actualisation du DCF."),
            ("Free Cash Flow", "Cash opérationnel - Capex. Flux de trésorerie disponible après investissements. Base de la valeur intrinsèque."),
        ],
    },
    # --------------------------------------------------------------------------
    # Structure financière banques
    # --------------------------------------------------------------------------
    {
        "title": "Structure & capital règlementaire (banques)",
        "contexts": {"societe:BANK"},
        "entries": [
            ("CET1 Ratio", "Common Equity Tier 1 / Risk-Weighted Assets. Capital dur vs risques pondérés. Minimum règlementaire 8-11%, confortable > 14%."),
            ("RWA", "Risk-Weighted Assets. Actifs pondérés par risque selon règles Bâle III. Dénominateur central des ratios de solvabilité."),
            ("LCR", "Liquidity Coverage Ratio. Actifs liquides / Sorties nettes 30j. > 100% exigé, banques confortables > 140%."),
            ("NSFR", "Net Stable Funding Ratio. Financements stables / Besoins stables (>1 an). > 100% exigé."),
            ("Loan/Deposit Ratio", "Prêts / Dépôts. Mesure de liquidité structurelle. < 100% = excédent dépôts (retail), > 110% = dépendance marchés."),
        ],
    },
    # --------------------------------------------------------------------------
    # Qualité comptable corporate
    # --------------------------------------------------------------------------
    {
        "title": "Qualité comptable",
        "contexts": {"societe:STANDARD", "societe:UTILITY", "societe:OIL_GAS",
                     "cmp_societe"},
        "entries": [
            ("Piotroski F-Score", "Score 0-9 sur 9 critères (rentabilité, liquidité, levier, efficacité). >6 = bonne santé financière, <3 = signaux négatifs."),
            ("Beneish M-Score", "Modèle de détection de manipulation comptable. >-1,78 = risque potentiel de fraude aux résultats."),
            ("Altman Z-Score", "Score de risque de faillite. >2,99 = zone sûre, 1,81-2,99 = zone grise, <1,81 = zone de détresse."),
            ("Sloan Accruals", "Mesure la part du résultat comptable non soutenue par le cash. Un ratio élevé suggère des bénéfices de moindre qualité."),
            ("Cash Conversion", "FCF / Résultat net. Qualité de conversion des bénéfices comptables en cash. Idéalement >0,8."),
        ],
    },
    # --------------------------------------------------------------------------
    # Risque & marché — toujours pertinent
    # --------------------------------------------------------------------------
    {
        "title": "Risque & Marché",
        "contexts": {"societe:*", "secteur", "indice",
                     "cmp_societe", "cmp_secteur", "cmp_indice"},
        "entries": [
            ("Bêta", "Sensibilité du titre aux mouvements du marché. Bêta=1 = même volatilité que le marché. >1 = plus volatil, <1 = plus défensif."),
            ("Volatilité 52S", "Écart-type annualisé des rendements journaliers sur 52 semaines. Mesure l'amplitude des fluctuations du cours."),
            ("VaR 95% 1M", "Value at Risk mensuelle à 95%. Perte maximale attendue dans 95% des cas sur un mois."),
            ("52W High / Low", "Plus haut / plus bas du cours sur les 52 dernières semaines. Repères techniques de la fourchette de trading récente."),
            ("ERP", "Equity Risk Premium. Prime de risque des actions vs taux sans risque. Pilote le coût des fonds propres dans le WACC."),
        ],
    },
    # --------------------------------------------------------------------------
    # Scores FinSight — toujours pertinent
    # --------------------------------------------------------------------------
    {
        "title": "Scores FinSight",
        "contexts": {"societe:*", "secteur", "indice",
                     "cmp_societe", "cmp_secteur", "cmp_indice"},
        "entries": [
            ("Score FinSight", "Score composite 0-100 : Valeur (25pts) + Croissance (25pts) + Qualité (25pts) + Momentum (25pts)."),
            ("Score Momentum", "Score 0-100 basé sur la performance boursière 3 mois."),
            ("Conviction IA", "Niveau de certitude de l'agent de synthèse dans sa recommandation (0-100%)."),
            ("Delta conviction", "Variation de conviction après passage de l'agent Devil's Advocate. Un delta négatif = arguments baissiers ont affaibli la thèse."),
            ("Recommandation", "ACHETER / CONSERVER / VENDRE. Synthèse de l'ensemble des analyses quantitatives et qualitatives. Ne constitue pas un conseil en investissement."),
        ],
    },
    # --------------------------------------------------------------------------
    # LBO & PE — uniquement corporate (pas banques/assurance : non applicable)
    # --------------------------------------------------------------------------
    {
        "title": "LBO & Private Equity",
        "contexts": {"societe:STANDARD", "societe:UTILITY", "societe:OIL_GAS", "societe:REIT"},
        "entries": [
            ("LBO", "Leveraged Buyout — rachat financé majoritairement par dette (60-80%) et par les fonds propres d'un sponsor PE."),
            ("Multiple d'entrée", "EV/EBITDA payé pour acquérir la cible. Détermine le prix d'achat et le levier soutenable."),
            ("TLB (Term Loan B)", "Dette senior amortissable avec cash sweep. Coût ~7-9%, structure prioritaire au remboursement."),
            ("IRR Sponsor", "Taux de rendement interne pour l'investisseur PE. Cible institutionnelle : 20%+ tier-1."),
            ("MOIC", "Multiple on Invested Capital. Multiple cash sur le capital investi (equity exit / equity entry). 2x = doublement."),
            ("Cash Sweep", "Mécanisme imposant que tout FCF excédentaire serve à rembourser la dette par anticipation."),
            ("Covenant", "Clause contractuelle imposant des seuils financiers (levier max, ICR min)."),
        ],
    },
    # --------------------------------------------------------------------------
    # Allocation & macro — uniquement indice / secteur / cmp_*
    # --------------------------------------------------------------------------
    {
        "title": "Allocation & Macro",
        "contexts": {"secteur", "indice", "cmp_secteur", "cmp_indice"},
        "entries": [
            ("Surpondérer", "Recommandation d'allocation : poids supérieur au benchmark (score FinSight >= 65). Conviction haussière forte sur 6-12 mois."),
            ("Neutre", "Poids égal au benchmark (score 45-64). Pas de conviction directionnelle marquée."),
            ("Sous-pondérer", "Poids inférieur au benchmark (score < 45). Conviction baissière ou risque structurel identifié."),
            ("Régime macro", "Phase de cycle économique (expansion / ralentissement / récession / reprise). Détermine les secteurs/indices favorisés."),
            ("Allocation optimale", "Pondération obtenue par optimisation Markowitz maximisant Sharpe ou minimisant volatilité sous contraintes de poids min/max."),
            ("Mean reversion", "Hypothèse de retour à la moyenne historique d'un multiple ou d'un ratio. Base des stratégies value/contrarian."),
            ("Re-rating", "Variation du multiple (P/E, EV/EBITDA) qu'un investisseur est prêt à payer. Re-rating positif = expansion du multiple."),
        ],
    },
    # --------------------------------------------------------------------------
    # Allocation optimale indice — techniques Markowitz
    # --------------------------------------------------------------------------
    {
        "title": "Optimisation de portefeuille",
        "contexts": {"indice", "cmp_indice"},
        "entries": [
            ("Min-Variance", "Portefeuille minimisant la variance (risque total). Privilégie les actifs faiblement corrélés, souvent défensif."),
            ("Tangency (Max Sharpe)", "Portefeuille maximisant le ratio de Sharpe = (rendement attendu - taux sans risque) / volatilité."),
            ("Equal Risk Contribution", "Chaque actif contribue autant au risque total. Approche diversifiée, robuste aux erreurs d'estimation."),
            ("Matrice de corrélation", "Mesure la co-dépendance des rendements entre secteurs. Une corrélation faible (<0,5) améliore la diversification."),
            ("Frontière efficiente", "Ensemble des portefeuilles optimaux au sens de Markowitz : rendement max pour chaque niveau de risque."),
        ],
    },
    # --------------------------------------------------------------------------
    # Comparatif spread (cmp uniquement)
    # --------------------------------------------------------------------------
    {
        "title": "Comparatif FinSight",
        "contexts": {"cmp_societe", "cmp_secteur", "cmp_indice"},
        "entries": [
            ("Spread FinSight", "Écart de scores entre deux entités comparées. >30 pts = bifurcation marquée, <15 pts = convergence."),
            ("Titre préféré", "Désignation du titre dominant sur la combinaison valorisation / qualité / momentum."),
            ("Dispersion sectorielle", "Écart-type des scores entre secteurs d'un indice. Une dispersion élevée crée des opportunités d'allocation tactique."),
        ],
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# API publique
# ═════════════════════════════════════════════════════════════════════════════

def _context_match(card_contexts: set[str], target: str) -> bool:
    """Retourne True si la card doit être affichée pour le contexte target."""
    if target in card_contexts:
        return True
    # Wildcard societe:* couvre tous les profils
    if target.startswith("societe:") and "societe:*" in card_contexts:
        return True
    return False


def get_cards_for_context(
    type_analyse: str,
    profile: str | None = None,
) -> list[GlossaryCard]:
    """Retourne les cartes pertinentes pour un contexte donné.

    Args:
        type_analyse : "societe" | "secteur" | "indice" | "cmp_societe" |
                       "cmp_secteur" | "cmp_indice"
        profile      : "STANDARD" | "BANK" | "INSURANCE" | "REIT" | "UTILITY" |
                       "OIL_GAS" — requis pour type_analyse = "societe",
                       ignoré sinon.

    Returns:
        Liste des cards à afficher, préservant l'ordre de définition.
    """
    if type_analyse == "societe":
        target = f"societe:{profile or 'STANDARD'}"
    else:
        target = type_analyse

    return [c for c in _CARDS if _context_match(c["contexts"], target)]


def list_all_terms(cards: Iterable[GlossaryCard]) -> set[str]:
    """Retourne l'ensemble des termes (clés) présents dans une liste de cards.
    Utilisé par l'audit glossaire pour vérifier la couverture."""
    terms = set()
    for c in cards:
        for term, _ in c["entries"]:
            terms.add(term.lower())
    return terms
