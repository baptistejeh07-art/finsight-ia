"""
Mapping des codes de la liasse fiscale française (Cerfa 2050-2059) vers les
champs YearAccounts utilisés par le moteur analytique.

Le XLSX Pappers reproduit les formulaires Cerfa officiels :
- 2050 : Bilan actif (régime réel normal)
- 2051 : Bilan passif
- 2052 : Compte de résultat (charges)
- 2053 : Compte de résultat (produits)

Chaque ligne du Cerfa a un **code à 2 lettres** (AA, AB, ... HN, HO) qui reste
stable d'une société à l'autre. Le parser XLSX scanne ces codes et lit la
valeur "Net exercice N" dans la ligne correspondante.

Source officielle des formulaires :
https://www.impots.gouv.fr/formulaire/2050-liasse/liasse-fiscale-bic-is-regime-reel-normal
"""

from __future__ import annotations

# ==============================================================================
# Bilan actif (Cerfa 2050)
#   Les codes "Brut" + "Amort." → Net.
#   On privilégie la colonne "Net" (dernière colonne numérique de la ligne)
#   via l'heuristique du parser, mais on liste ici le code principal pour
#   identification.
# ==============================================================================

BILAN_ACTIF: dict[str, str] = {
    # Actif immobilisé
    "AB": "immobilisations_incorporelles",   # Frais d'établissement
    "AD": "immobilisations_incorporelles",   # Frais de développement
    "AF": "immobilisations_incorporelles",   # Concessions, brevets, droits similaires
    "AH": "immobilisations_incorporelles",   # Fonds commercial
    "AJ": "immobilisations_incorporelles",   # Autres immobilisations incorporelles (souvent le total)
    "AL": "immobilisations_incorporelles",   # Avances et acomptes sur immo incorp
    "AN": "immobilisations_corporelles",     # Terrains
    "AP": "immobilisations_corporelles",     # Constructions
    "AR": "immobilisations_corporelles",     # Installations techniques
    "AT": "immobilisations_corporelles",     # Autres immobilisations corporelles
    "AV": "immobilisations_corporelles",     # Immobilisations en cours
    "AX": "immobilisations_corporelles",     # Avances et acomptes
    "CS": "immobilisations_financieres",     # Participations (mises en équiv.)
    "CU": "immobilisations_financieres",     # Autres participations
    "BB": "immobilisations_financieres",     # Créances rattachées à des participations
    "BD": "immobilisations_financieres",     # Autres titres immobilisés
    "BF": "immobilisations_financieres",     # Prêts
    "BH": "immobilisations_financieres",     # Autres immobilisations financières
    "BJ": "_total_actif_immobilise",         # TOTAL II (aggrégat, non stocké direct)

    # Actif circulant
    "BL": "stocks",                          # Matières premières
    "BN": "stocks",                          # En-cours production biens
    "BP": "stocks",                          # En-cours production services
    "BR": "stocks",                          # Produits finis
    "BT": "stocks",                          # Marchandises
    "BV": "autres_creances",                 # Avances et acomptes versés
    "BX": "creances_clients",                # Créances clients et comptes rattachés
    "BZ": "autres_creances",                 # Autres créances
    "CB": "autres_creances",                 # Capital souscrit - appelé non versé
    "CD": "disponibilites",                  # Valeurs mobilières de placement
    "CF": "disponibilites",                  # Disponibilités
    "CH": "autres_creances",                 # Charges constatées d'avance
    "CJ": "_total_actif_circulant",          # TOTAL III
    "CO": "total_actif",                     # TOTAL GÉNÉRAL (I+II+III+IV+V)
}


# ==============================================================================
# Bilan passif (Cerfa 2051)
# ==============================================================================

BILAN_PASSIF: dict[str, str] = {
    # Capitaux propres
    "DA": "capital_social",
    "DB": "capital_social",                  # Capital souscrit non appelé
    "DC": "capital_social",                  # Primes d'émission, fusion, apport
    "DD": "reserves",                        # Écarts de réévaluation
    "DE": "reserves",                        # Réserve légale
    "DF": "reserves",                        # Réserves statutaires
    "DG": "reserves",                        # Réserves réglementées
    "DH": "reserves",                        # Autres réserves
    "DI": "report_a_nouveau",                # Report à nouveau
    "DJ": "_resultat_exercice",              # Résultat de l'exercice (→ resultat_net)
    "DK": "_subventions_investissement",     # Subventions d'investissement
    "DL": "_provisions_reglementees",        # Provisions réglementées
    "DM": "capitaux_propres",                # TOTAL I (Capitaux propres)

    # Autres fonds propres
    "DN": "_autres_fonds_propres",           # Produits des émissions (titres part.)
    "DO": "_autres_fonds_propres",           # Avances conditionnées
    "DP": "_autres_fonds_propres",           # TOTAL II (autres fonds propres)

    # Provisions
    "DR": "provisions_risques",              # Provisions pour risques
    "DS": "provisions_risques",              # Provisions pour charges
    "DT": "provisions_risques",              # TOTAL III provisions

    # Dettes
    "DU": "dettes_financieres",              # Emprunts obligataires convertibles
    "DV": "dettes_financieres",              # Autres emprunts obligataires
    "DW": "dettes_financieres",              # Emprunts et dettes crédit (dont concours)
    "DX": "dettes_financieres",              # Emprunts et dettes financières divers
    "DY": "autres_dettes",                   # Avances et acomptes reçus
    "DZ": "dettes_fournisseurs",             # Dettes fournisseurs et comptes rattachés
    "EA": "dettes_fiscales_sociales",        # Dettes fiscales et sociales
    "EB": "autres_dettes",                   # Dettes sur immobilisations
    "EC": "autres_dettes",                   # Autres dettes
    "ED": "autres_dettes",                   # Produits constatés d'avance
    "EE": "_total_dettes",                   # TOTAL IV dettes

    "EF": "_ecarts_conversion_passif",
    "EG": "total_passif",                    # TOTAL GÉNÉRAL PASSIF
}


# ==============================================================================
# Compte de résultat — Charges (Cerfa 2052)
# Structure vérifiée sur XLSX Pappers EDF 2024 :
#
#   Ligne 16 : Achats de marchandises                   → FS
#   Ligne 17 : Variation de stocks (marchandises)       → FT
#   Ligne 18 : Achats matières premières et approv.     → FU
#   Ligne 19 : Variation de stocks (matières)           → FV
#   Ligne 20 : Autres achats et charges externes        → FW
#   Ligne 21 : Impôts, taxes et versements assimilés    → FX
#   Ligne 22 : Salaires et traitements                   → FY
#   Ligne 23 : Charges sociales                          → FZ
#   Ligne 24 : Dotations aux amortissements (immo)       → GA
#   Ligne 25 : Dotations aux dépréciations (immo)        → GB
#   Ligne 26 : Dotations sur actif circulant             → GC
#   Ligne 27 : Dotations provisions risques et charges   → GD
#   Ligne 28 : Autres charges                            → GE
#   Ligne 29 : TOTAL CHARGES EXPLOITATION                → GF
#   Ligne 30 : 1 — RÉSULTAT D'EXPLOITATION               → GG
#
#   Charges financières (section suivante) :
#   Ligne XX : Dotations financières                     → GH
#   Ligne XX : Intérêts et charges assimilées            → GJ (ou GI selon versions)
#   Ligne XX : Différences négatives de change           → GK
#   Ligne XX : Charges nettes cessions VMP               → GL
#   Ligne XX : TOTAL CHARGES FINANCIÈRES                 → GM
#
#   Résultat courant avant impôts → GU / GW
#
#   Charges exceptionnelles (HC/HD/HE/HF) :
#   HC : Charges excep sur opérations de gestion
#   HD : Charges excep sur opérations en capital
#   HE : Dotations exceptionnelles
#   HF : TOTAL CHARGES EXCEPTIONNELLES
#
#   Participations / impôts :
#   HJ : Participation des salariés aux résultats
#   HK : Impôts sur les bénéfices
#   HL : TOTAL DES CHARGES
#   HN : BÉNÉFICE OU PERTE
COMPTE_RESULTAT_CHARGES: dict[str, str] = {
    # Charges d'exploitation
    "FS": "achats_marchandises",
    "FT": "variation_stocks_marchandises",
    "FU": "achats_matieres_premieres",
    "FV": "variation_stocks_matieres",
    "FW": "autres_achats_charges_externes",
    "FX": "impots_taxes",
    "FY": "salaires_traitements",
    "FZ": "charges_sociales",
    "GA": "dotations_amortissements",
    "GB": "dotations_amortissements",                 # dépréciations immobilisations
    "GC": "dotations_provisions_exploitation",        # DAP sur actif circulant
    "GD": "dotations_provisions_exploitation",        # DAP risques et charges
    "GE": "_autres_charges_exploitation",
    "GF": "_charges_exploitation_total",              # TOTAL

    # Résultat d'exploitation
    "GG": "resultat_exploitation",                    # 1 — RÉSULTAT D'EXPLOITATION

    # Charges financières
    "GH": "_dotations_financieres",
    "GJ": "charges_financieres",                      # Intérêts et charges assimilées
    "GI": "charges_financieres",                      # (variante)
    "GK": "_differences_change_negatives",
    "GL": "_charges_nettes_cessions_vmp",
    "GM": "_charges_financieres_total",

    # Résultat financier / courant
    "GT": "resultat_financier",                       # 2 — RÉSULTAT FINANCIER
    "GU": "_resultat_courant_av_impots",              # 3 — RCAI
    "GV": "_resultat_courant_av_impots",              # variante

    # Charges exceptionnelles
    "HC": "charges_exceptionnelles",                  # Sur opérations de gestion
    "HD": "charges_exceptionnelles",                  # Sur opérations en capital
    "HE": "charges_exceptionnelles",                  # Dotations exceptionnelles
    "HF": "_charges_exceptionnelles_total",

    # Participations et impôts
    "HJ": "participation_salaries",
    "HK": "impots_sur_benefices",
    "HL": "_total_charges",

    "HN": "resultat_net",                             # BÉNÉFICE OU PERTE (final)
}


# ==============================================================================
# Compte de résultat — Produits (Cerfa 2053)
# ==============================================================================

COMPTE_RESULTAT_PRODUITS: dict[str, str] = {
    # Produits d'exploitation
    "FC_P": "chiffre_affaires",              # (pour éviter collision avec FC charges)
    "FC ": "chiffre_affaires",               # Vente de marchandises (note : espace trailing intentionnel)
    # Note : dans le Cerfa 2053, les codes produits commencent par F (FA-FN) puis continuent
    # en G (GA-GW). Il y a collision avec les codes charges (FA-FN) du 2052 !
    # On gère cela en détectant le CONTEXTE de la feuille avant d'appliquer le mapping.
}


# Codes Cerfa 2053 "Produits" (compte de résultat produits) —
# Structure vérifiée sur XLSX Pappers EDF 2024 :
#
#   Ligne 6 : Ventes de marchandises         → FA (France) | FB (Export) | FC (TOTAL)
#   Ligne 7 : Production vendue de biens     → FD (France) | FE (Export) | FF (TOTAL)
#   Ligne 8 : Production vendue de services  → FG (France) | FH (Export) | FI (TOTAL)
#   Ligne 9 : CHIFFRE D'AFFAIRES NET         → FJ (France) | FK (Export) | FL (TOTAL)
#   Ligne 10 : Production stockée            → FM
#   Ligne 11 : Production immobilisée        → FN
#   Ligne 12 : Subventions d'exploitation    → FO
#   Ligne 13 : Reprises amort/prov.           → FP
#   Ligne 14 : Autres produits               → FQ
#   Ligne 15 : TOTAL PRODUITS EXPLOITATION   → FR
#
# On ne mappe que les **codes TOTAL** (colonne L), pas les ventilations France/Export.
CR_PRODUITS: dict[str, str] = {
    # Produits d'exploitation
    "FC": "_ventes_marchandises_total",      # Total ventes marchandises
    "FF": "production_vendue",               # Total production vendue biens
    "FI": "_production_vendue_services",     # Total production vendue services
    "FL": "chiffre_affaires",                # CHIFFRE D'AFFAIRES NET TOTAL (ligne principale)
    "FM": "production_stockee",              # Production stockée
    "FN": "production_immobilisee",          # Production immobilisée
    "FO": "subventions_exploitation",        # Subventions d'exploitation
    "FP": "_reprises_amort_prov_expl",       # Reprises sur amortissements et provisions
    "FQ": "_autres_produits_exploitation",   # Autres produits (ex: transferts charges)
    "FR": "_produits_exploitation_total",    # TOTAL PRODUITS D'EXPLOITATION

    # Produits financiers
    "GA": "produits_financiers",             # Produits de participations
    "GB": "produits_financiers",             # Produits autres valeurs mob.
    "GC": "produits_financiers",             # Autres intérêts et produits assimilés
    "GD": "produits_financiers",             # Reprises sur provisions/transferts
    "GE": "produits_financiers",             # Différences positives de change
    "GF": "produits_financiers",             # Produits nets cessions VMP
    "GG": "_produits_financiers_total",      # TOTAL PRODUITS FINANCIERS

    # Produits exceptionnels
    "HA": "produits_exceptionnels",          # Opérations de gestion
    "HB": "produits_exceptionnels",          # Opérations en capital
    "HC": "produits_exceptionnels",          # Reprises provisions
    "HD": "_produits_exceptionnels_total",   # TOTAL PRODUITS EXCEPTIONNELS

    "HI": "_total_produits",                 # TOTAL DES PRODUITS
}


# ==============================================================================
# Code Cerfa → feuille d'origine (pour désambiguer les collisions FA/FE/FI...
# qui existent dans plusieurs formulaires)
# ==============================================================================

def get_mapping_for_sheet(sheet_name: str) -> dict[str, str]:
    """Renvoie le dictionnaire de mapping adapté à la feuille XLSX Pappers.

    Les feuilles Pappers sont nommées :
    - "Actif" ou "Bilan (actif et passif)" pour le 2050+2051 combinés
    - "Passif"
    - "Compte de résultat" pour le 2052+2053
    - "Immobilisations — Amortissement"
    - "Provisions"
    """
    lname = sheet_name.lower()
    if "actif" in lname and "passif" not in lname:
        return BILAN_ACTIF
    if "passif" in lname and "actif" not in lname:
        return BILAN_PASSIF
    if "bilan" in lname or ("actif" in lname and "passif" in lname):
        # Bilan combiné : on merge actif + passif
        return {**BILAN_ACTIF, **BILAN_PASSIF}
    if "compte" in lname and ("résultat" in lname or "resultat" in lname):
        # Compte de résultat complet : charges + produits
        return {**COMPTE_RESULTAT_CHARGES, **CR_PRODUITS}
    if "immobilisation" in lname:
        # Détail amortissements — rien d'extrait pour YearAccounts (déjà via AJ/AT)
        return {}
    if "provision" in lname:
        return {}
    return {}


def is_valid_cerfa_code(value: str) -> bool:
    """Un code Cerfa valide = exactement 2 lettres majuscules A-Z (ex: AA, BJ, HN)."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    return len(v) == 2 and v.isalpha() and v.isupper()
