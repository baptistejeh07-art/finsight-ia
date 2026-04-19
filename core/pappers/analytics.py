"""
Moteur analytique PME — 100% Python déterministe.

Calcule :
- SIG (Soldes Intermédiaires de Gestion) selon Plan Comptable Général FR
- Ratios rentabilité / solidité / efficacité / croissance
- Score santé FinSight 0-100 (pondéré selon profil sectoriel)
- Score bankabilité 0-100 (ratios bancaires)
- Altman Z-Score adapté non-coté (Altman 1995)

Input : liste `YearAccounts` (bilan + P&L par année) + `SectorProfile`
Output : dataclass `PmeAnalysis` avec tous les indicateurs + classifications
         (red/orange/green) selon les seuils sectoriels.

Aucun LLM n'intervient ici.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from core.pappers.sector_profiles import SectorProfile, Threshold

log = logging.getLogger(__name__)


# ==============================================================================
# Modèle de données : comptes annuels PME (schéma PCG simplifié)
# ==============================================================================

@dataclass
class YearAccounts:
    """Comptes annuels d'une PME — lignes du PCG FR simplifiées.

    Toutes les valeurs en euros. None = non disponible dans le dépôt source.
    """

    annee: int                         # ex: 2024
    date_cloture: str | None = None    # "2024-12-31"

    # ─── Compte de résultat (P&L) ───
    chiffre_affaires: float | None = None              # Production vendue + marchandises
    production_vendue: float | None = None
    production_stockee: float | None = None
    production_immobilisee: float | None = None
    subventions_exploitation: float | None = None

    # Charges principales
    achats_marchandises: float | None = None
    variation_stocks_marchandises: float | None = None
    achats_matieres_premieres: float | None = None
    variation_stocks_matieres: float | None = None
    autres_achats_charges_externes: float | None = None
    impots_taxes: float | None = None

    # Personnel
    salaires_traitements: float | None = None
    charges_sociales: float | None = None

    # Amortissements / provisions
    dotations_amortissements: float | None = None
    dotations_provisions_exploitation: float | None = None

    # Financier
    produits_financiers: float | None = None
    charges_financieres: float | None = None

    # Exceptionnel
    produits_exceptionnels: float | None = None
    charges_exceptionnelles: float | None = None

    # Impôts
    participation_salaries: float | None = None
    impots_sur_benefices: float | None = None

    # Résultat (optionnel — si fourni directement par le dépôt)
    resultat_exploitation: float | None = None
    resultat_financier: float | None = None
    resultat_exceptionnel: float | None = None
    resultat_net: float | None = None

    # ─── Bilan actif ───
    immobilisations_incorporelles: float | None = None
    immobilisations_corporelles: float | None = None
    immobilisations_financieres: float | None = None
    stocks: float | None = None
    creances_clients: float | None = None
    autres_creances: float | None = None
    disponibilites: float | None = None
    total_actif: float | None = None

    # ─── Bilan passif ───
    capital_social: float | None = None
    reserves: float | None = None
    report_a_nouveau: float | None = None
    provisions_risques: float | None = None
    dettes_financieres: float | None = None        # Emprunts LT + MT
    concours_bancaires: float | None = None        # Découverts, CT
    dettes_fournisseurs: float | None = None
    dettes_fiscales_sociales: float | None = None
    autres_dettes: float | None = None
    total_passif: float | None = None
    capitaux_propres: float | None = None

    # ─── Effectif déclaré dans les comptes ───
    effectif_moyen: int | None = None


# ==============================================================================
# SIG (Soldes Intermédiaires de Gestion)
# ==============================================================================

@dataclass
class SIG:
    """Soldes intermédiaires de gestion (calculés d'après le PCG FR)."""

    annee: int

    marge_commerciale: float | None = None        # Ventes marchandises - coût d'achat
    production_exercice: float | None = None       # Prod vendue + stockée + immobilisée
    valeur_ajoutee: float | None = None            # VA = Prod + marge - consomm. externes
    ebe: float | None = None                       # EBE = VA - charges perso - impôts
    resultat_exploitation: float | None = None     # REX = EBE - amortissements
    resultat_courant_av_impots: float | None = None  # RCAI = REX + rés. financier
    resultat_exceptionnel_net: float | None = None
    resultat_net: float | None = None

    # Dérivés utiles
    capacite_autofinancement: float | None = None  # CAF ≈ RN + amortissements
    charges_personnel_total: float | None = None   # Salaires + charges sociales
    consommations_externes: float | None = None    # Achats + autres charges externes


def _sum(*vals: float | None) -> float | None:
    """Somme qui ignore les None (renvoie None si TOUS les inputs sont None)."""
    non_none = [v for v in vals if v is not None]
    return sum(non_none) if non_none else None


def _safe_diff(a: float | None, b: float | None) -> float | None:
    if a is None and b is None:
        return None
    return (a or 0) - (b or 0)


def compute_sig(y: YearAccounts) -> SIG:
    """Calcule les SIG d'une année d'après les lignes du PCG FR."""

    # ─── Marge commerciale ───
    # = Ventes marchandises − (Achats marchandises ± Var. stocks marchandises)
    # Simplification : si chiffre_affaires est donné sans distinction, on suppose
    # que marge_commerciale = CA - achats_marchandises - var_stocks
    marge_comm = None
    if y.achats_marchandises is not None:
        achats_net = (y.achats_marchandises or 0) + (y.variation_stocks_marchandises or 0)
        ca_marchandises = y.chiffre_affaires or 0
        marge_comm = ca_marchandises - achats_net

    # ─── Production de l'exercice ───
    # = Prod vendue + Prod stockée + Prod immobilisée
    # Le XLSX Pappers peut ne pas ventiler production_vendue (déjà incluse dans CA).
    # Dans ce cas, on utilise CA comme base + stockée/immobilisée.
    prod_vendue = y.production_vendue if y.production_vendue is not None else y.chiffre_affaires
    prod = _sum(prod_vendue, y.production_stockee, y.production_immobilisee)

    # ─── Consommations externes ───
    # = Achats matières + Var stocks matières + Autres achats et charges externes
    conso_ext = _sum(
        y.achats_matieres_premieres,
        y.variation_stocks_matieres,
        y.autres_achats_charges_externes,
    )

    # ─── Valeur ajoutée ───
    # VA = Marge commerciale + Production - Consommations externes
    va = None
    if prod is not None or marge_comm is not None or conso_ext is not None:
        va = (marge_comm or 0) + (prod or 0) - (conso_ext or 0)
        # Si aucun composant fourni, VA reste None
        if all(v is None for v in [marge_comm, prod, conso_ext]):
            va = None

    # ─── EBE ───
    # EBE = VA + Subventions - Impôts/taxes - Charges personnel
    charges_perso = _sum(y.salaires_traitements, y.charges_sociales)
    ebe = None
    if va is not None:
        ebe = (
            va
            + (y.subventions_exploitation or 0)
            - (y.impots_taxes or 0)
            - (charges_perso or 0)
        )

    # ─── Résultat d'exploitation ───
    # REX = EBE - Dotations aux amortissements - Dotations aux provisions
    rex = y.resultat_exploitation
    if rex is None and ebe is not None:
        rex = ebe - (y.dotations_amortissements or 0) - (y.dotations_provisions_exploitation or 0)

    # ─── Résultat financier ───
    res_fi = y.resultat_financier
    if res_fi is None:
        res_fi = _safe_diff(y.produits_financiers, y.charges_financieres)

    # ─── RCAI ───
    rcai = None
    if rex is not None:
        rcai = rex + (res_fi or 0)

    # ─── Résultat exceptionnel ───
    res_exc = y.resultat_exceptionnel
    if res_exc is None:
        res_exc = _safe_diff(y.produits_exceptionnels, y.charges_exceptionnelles)

    # ─── Résultat net ───
    rn = y.resultat_net
    if rn is None and rcai is not None:
        rn = (
            rcai + (res_exc or 0)
            - (y.participation_salaries or 0)
            - (y.impots_sur_benefices or 0)
        )

    # ─── CAF (approximation simple : RN + dotations amortissements) ───
    caf = None
    if rn is not None:
        caf = rn + (y.dotations_amortissements or 0) + (y.dotations_provisions_exploitation or 0)

    return SIG(
        annee=y.annee,
        marge_commerciale=marge_comm,
        production_exercice=prod,
        valeur_ajoutee=va,
        ebe=ebe,
        resultat_exploitation=rex,
        resultat_courant_av_impots=rcai,
        resultat_exceptionnel_net=res_exc,
        resultat_net=rn,
        capacite_autofinancement=caf,
        charges_personnel_total=charges_perso,
        consommations_externes=conso_ext,
    )


# ==============================================================================
# Ratios financiers
# ==============================================================================

@dataclass
class Ratios:
    """Ratios financiers calculés pour une année."""

    annee: int

    # ─── Rentabilité ───
    marge_brute: float | None = None       # Marge commerciale / CA
    marge_ebitda: float | None = None      # EBE / CA
    marge_nette: float | None = None       # RN / CA
    roce: float | None = None              # REX / Capitaux employés
    roe: float | None = None               # RN / Capitaux propres

    # ─── Solidité ───
    dette_nette_ebitda: float | None = None
    couverture_interets: float | None = None   # EBIT / Charges financières
    autonomie_financiere: float | None = None  # FP / Total bilan
    bfr: float | None = None                   # en euros
    bfr_jours_ca: float | None = None
    tresorerie_nette: float | None = None

    # ─── Efficacité ───
    dso_jours: float | None = None
    dpo_jours: float | None = None
    rotation_stocks: float | None = None
    ca_par_employe: float | None = None
    charges_perso_ca: float | None = None


def _ratio(num: float | None, den: float | None) -> float | None:
    """Ratio sûr : None si num ou den absent, None si den proche de 0."""
    if num is None or den is None:
        return None
    if abs(den) < 1e-9:
        return None
    return num / den


def compute_ratios(y: YearAccounts, sig: SIG) -> Ratios:
    """Calcule les ratios standards à partir des comptes et SIG."""

    ca = y.chiffre_affaires

    # ─── Rentabilité ───
    marge_brute = _ratio(sig.marge_commerciale, ca) if sig.marge_commerciale is not None else None
    marge_ebitda = _ratio(sig.ebe, ca)
    marge_nette = _ratio(sig.resultat_net, ca)

    # Capitaux employés = FP + dettes financières
    cap_employes = _sum(y.capitaux_propres, y.dettes_financieres)
    roce = _ratio(sig.resultat_exploitation, cap_employes)
    roe = _ratio(sig.resultat_net, y.capitaux_propres)

    # ─── Solidité ───
    # Dette nette = Dettes financières + concours bancaires - disponibilités
    dette_nette = None
    if y.dettes_financieres is not None or y.disponibilites is not None:
        dette_nette = (
            (y.dettes_financieres or 0)
            + (y.concours_bancaires or 0)
            - (y.disponibilites or 0)
        )

    dette_nette_ebitda = _ratio(dette_nette, sig.ebe)

    # Couverture intérêts = EBIT / Charges financières
    # EBIT ≈ REX ; on exclut charges financières négatives (absurdes)
    couv_int = None
    if sig.resultat_exploitation is not None and y.charges_financieres is not None:
        if y.charges_financieres > 0:
            couv_int = sig.resultat_exploitation / y.charges_financieres
        else:
            couv_int = 999.0  # pas de dette → couverture quasi infinie

    autonomie = _ratio(y.capitaux_propres, y.total_passif)

    # BFR = Créances clients + Stocks - Dettes fournisseurs - Dettes fiscales/sociales
    bfr = None
    if any(v is not None for v in [y.creances_clients, y.stocks, y.dettes_fournisseurs]):
        bfr = (
            (y.creances_clients or 0)
            + (y.stocks or 0)
            + (y.autres_creances or 0)
            - (y.dettes_fournisseurs or 0)
            - (y.dettes_fiscales_sociales or 0)
        )

    bfr_jours_ca = None
    if bfr is not None and ca is not None and ca > 0:
        bfr_jours_ca = (bfr / ca) * 365

    # Trésorerie nette = Disponibilités - Concours bancaires
    tresorerie = None
    if y.disponibilites is not None or y.concours_bancaires is not None:
        tresorerie = (y.disponibilites or 0) - (y.concours_bancaires or 0)

    # ─── Efficacité ───
    # DSO = Créances clients / (CA TTC / 365) ; approx avec CA HT
    dso = None
    if y.creances_clients is not None and ca is not None and ca > 0:
        dso = (y.creances_clients / ca) * 365

    # DPO = Dettes fournisseurs / (Achats + Autres charges externes) * 365
    achats_total = _sum(
        y.achats_marchandises,
        y.achats_matieres_premieres,
        y.autres_achats_charges_externes,
    )
    dpo = None
    if y.dettes_fournisseurs is not None and achats_total and achats_total > 0:
        dpo = (y.dettes_fournisseurs / achats_total) * 365

    # Rotation stocks = Achats / Stocks moyens
    rotation = None
    if y.stocks is not None and y.stocks > 0 and achats_total:
        rotation = achats_total / y.stocks

    # CA par employé
    ca_employe = _ratio(ca, y.effectif_moyen) if y.effectif_moyen else None

    # Charges perso / CA
    cp_ca = _ratio(sig.charges_personnel_total, ca)

    return Ratios(
        annee=y.annee,
        marge_brute=marge_brute,
        marge_ebitda=marge_ebitda,
        marge_nette=marge_nette,
        roce=roce,
        roe=roe,
        dette_nette_ebitda=dette_nette_ebitda,
        couverture_interets=couv_int,
        autonomie_financiere=autonomie,
        bfr=bfr,
        bfr_jours_ca=bfr_jours_ca,
        tresorerie_nette=tresorerie,
        dso_jours=dso,
        dpo_jours=dpo,
        rotation_stocks=rotation,
        ca_par_employe=ca_employe,
        charges_perso_ca=cp_ca,
    )


# ==============================================================================
# Scoring Altman Z adapté non-coté (Altman 1995 / Z"-Score)
# ==============================================================================

def compute_altman_z_private(y: YearAccounts, sig: SIG) -> float | None:
    """Altman Z"-Score adapté aux sociétés non cotées (Altman 1995).

    Z" = 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X4

    avec :
      X1 = (Actif circulant − Passif circulant) / Total actif   (working capital ratio)
      X2 = Bénéfices non distribués / Total actif               (retained earnings ratio)
      X3 = EBIT / Total actif                                    (operating efficiency)
      X4 = Valeur comptable FP / Total dettes                    (equity buffer)

    Interprétation (non-manufacturing) :
      Z" > 2.60  → zone safe (risque faible)
      1.10 < Z" < 2.60 → zone grise
      Z" < 1.10  → détresse probable
    """
    if y.total_actif is None or y.total_actif <= 0:
        return None

    # X1 : working capital ratio
    # Actif circulant = Stocks + Créances + Disponibilités + Autres créances
    # Passif circulant = Dettes fournisseurs + Fiscales + Concours + Autres dettes CT
    actif_circulant = _sum(
        y.stocks, y.creances_clients, y.disponibilites, y.autres_creances
    ) or 0
    passif_circulant = _sum(
        y.dettes_fournisseurs, y.dettes_fiscales_sociales, y.concours_bancaires, y.autres_dettes
    ) or 0
    x1 = (actif_circulant - passif_circulant) / y.total_actif

    # X2 : bénéfices non distribués = Report à nouveau + Réserves (approximation)
    retained = _sum(y.report_a_nouveau, y.reserves) or 0
    x2 = retained / y.total_actif

    # X3 : EBIT / Total actif
    ebit = sig.resultat_exploitation or 0
    x3 = ebit / y.total_actif

    # X4 : FP / Total dettes
    total_dettes = _sum(
        y.dettes_financieres, y.concours_bancaires, y.dettes_fournisseurs,
        y.dettes_fiscales_sociales, y.autres_dettes,
    ) or 0
    if total_dettes > 0 and y.capitaux_propres is not None:
        x4 = y.capitaux_propres / total_dettes
    else:
        x4 = 10.0  # pas de dette → ratio très élevé, on cap pour éviter divergence

    return 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4


def altman_z_verdict(z: float | None) -> str:
    """Interprétation Altman Z" pour non-manufacturing."""
    if z is None:
        return "non_calculable"
    if z > 2.60:
        return "safe"
    if z > 1.10:
        return "grey"
    return "distress"


# ==============================================================================
# Score santé FinSight 0-100
# ==============================================================================

def _score_ratio(value: float | None, threshold: Threshold | None) -> float | None:
    """Convertit une valeur de ratio en score 0-100 via Threshold.

    Règle :
      - 100 si dans [normal_low, normal_high]
      - 60-90 si warn zone (interpolation linéaire)
      - 0-40 si red zone
      - None si threshold None ou value None
    """
    if value is None or threshold is None:
        return None

    # Cas "higher_is_better" (marge, ROE, couverture, etc.)
    if threshold.higher_is_better:
        if value >= threshold.normal_high:
            # Bonus : zone haute mais décroissant si anormalement élevé (ex: marge 95% chez commerce)
            if value > threshold.warn_high:
                return 60.0
            return 100.0
        if value >= threshold.normal_low:
            # linear 70→100 dans [normal_low, normal_high]
            span = threshold.normal_high - threshold.normal_low
            if span <= 0:
                return 100.0
            return 70.0 + 30.0 * (value - threshold.normal_low) / span
        if value >= threshold.warn_low:
            span = threshold.normal_low - threshold.warn_low
            if span <= 0:
                return 40.0
            return 40.0 + 30.0 * (value - threshold.warn_low) / span
        # value < warn_low
        return 0.0

    # Cas "lower_is_better" (dette/EBITDA, DSO, BFR jours, charges perso/CA)
    else:
        if value <= threshold.normal_low:
            # Très bas = très bon, mais pas trop (DSO 0j c'est suspect aussi)
            return 100.0
        if value <= threshold.normal_high:
            span = threshold.normal_high - threshold.normal_low
            if span <= 0:
                return 100.0
            return 100.0 - 30.0 * (value - threshold.normal_low) / span
        if value <= threshold.warn_high:
            span = threshold.warn_high - threshold.normal_high
            if span <= 0:
                return 40.0
            return 70.0 - 30.0 * (value - threshold.normal_high) / span
        # value > warn_high
        return 0.0


def _average_non_none(scores: list[float | None]) -> float | None:
    non_none = [s for s in scores if s is not None]
    if not non_none:
        return None
    return sum(non_none) / len(non_none)


def compute_health_score(ratios: Ratios, profile: SectorProfile, sig: SIG) -> float | None:
    """Score santé FinSight 0-100, pondéré selon le profil sectoriel.

    5 familles (pondération fixée dans SectorProfile) :
      - rentabilité  (marges, ROCE, ROE)
      - solidité     (dette/EBITDA, couverture intérêts, autonomie fin., BFR)
      - efficacité   (DSO, DPO, rotation stocks, CA/employé)
      - croissance   (à calculer sur plusieurs années — renvoie None ici)
      - BODACC       (à ajouter en J6, ici 100.0 par défaut)
    """
    # Rentabilité
    score_renta = _average_non_none([
        _score_ratio(ratios.marge_ebitda, profile.marge_ebitda),
        _score_ratio(ratios.marge_nette, profile.marge_nette),
        _score_ratio(ratios.roce, profile.roce),
        _score_ratio(ratios.roe, profile.roe),
    ])

    # Solidité
    score_solid = _average_non_none([
        _score_ratio(ratios.dette_nette_ebitda, profile.dette_nette_ebitda),
        _score_ratio(ratios.couverture_interets, profile.couverture_interets),
        _score_ratio(ratios.autonomie_financiere, profile.autonomie_financiere),
        _score_ratio(ratios.bfr_jours_ca, profile.bfr_jours_ca),
    ])

    # Efficacité
    score_eff = _average_non_none([
        _score_ratio(ratios.dso_jours, profile.dso_jours),
        _score_ratio(ratios.rotation_stocks, profile.rotation_stocks),
        _score_ratio(ratios.ca_par_employe, profile.ca_par_employe),
        _score_ratio(ratios.charges_perso_ca, profile.charges_perso_ca),
    ])

    # Croissance : N/A sur 1 année
    score_growth = None

    # BODACC : J6 le fera ; pour l'instant 100 (pas de procédure)
    score_bodacc = 100.0

    # Pondération
    components = [
        (score_renta, profile.weight_rentabilite),
        (score_solid, profile.weight_solidite),
        (score_eff, profile.weight_efficacite),
        (score_growth, profile.weight_croissance),
        (score_bodacc, profile.weight_bodacc),
    ]
    weighted: list[tuple[float, float]] = [(s, w) for s, w in components if s is not None]
    if not weighted:
        return None
    total_weight = sum(w for _, w in weighted)
    if total_weight <= 0:
        return None
    return sum(s * w for s, w in weighted) / total_weight


# ==============================================================================
# Score bankabilité
# ==============================================================================

def compute_bankability_score(ratios: Ratios, sig: SIG, y: YearAccounts) -> float | None:
    """Score bankabilité 0-100 : les ratios que les banques regardent.

    Sont fortement pondérés :
      - dette nette / EBITDA (seuil banque : < 3x pour investment grade)
      - couverture intérêts (> 3x requis)
      - autonomie financière (> 25% préféré)
      - CAF / CA (capacité à rembourser)
    """
    components: list[tuple[float, float]] = []

    # Dette / EBITDA : score inverse (0-100)
    if ratios.dette_nette_ebitda is not None:
        d = ratios.dette_nette_ebitda
        if d < 0:
            s = 100.0  # trésorerie nette positive
        elif d < 1.5:
            s = 90.0
        elif d < 3.0:
            s = 70.0
        elif d < 4.5:
            s = 40.0
        else:
            s = 10.0
        components.append((s, 0.30))

    # Couverture intérêts
    if ratios.couverture_interets is not None:
        c = ratios.couverture_interets
        if c >= 10:
            s = 100.0
        elif c >= 5:
            s = 85.0
        elif c >= 3:
            s = 65.0
        elif c >= 2:
            s = 40.0
        else:
            s = 10.0
        components.append((s, 0.25))

    # Autonomie financière
    if ratios.autonomie_financiere is not None:
        a = ratios.autonomie_financiere
        if a >= 0.40:
            s = 100.0
        elif a >= 0.25:
            s = 75.0
        elif a >= 0.15:
            s = 50.0
        else:
            s = 20.0
        components.append((s, 0.20))

    # CAF / CA
    if sig.capacite_autofinancement is not None and y.chiffre_affaires:
        caf_ca = sig.capacite_autofinancement / y.chiffre_affaires
        if caf_ca >= 0.10:
            s = 100.0
        elif caf_ca >= 0.06:
            s = 75.0
        elif caf_ca >= 0.03:
            s = 50.0
        elif caf_ca >= 0:
            s = 25.0
        else:
            s = 0.0
        components.append((s, 0.25))

    if not components:
        return None
    total_w = sum(w for _, w in components)
    return sum(s * w for s, w in components) / total_w


def estimate_debt_capacity(ratios: Ratios, sig: SIG) -> float | None:
    """Estime le montant de dette additionnelle accessible (target 3x EBITDA).

    Target : dette nette / EBITDA = 3.0
    Dette nette additionnelle = 3 * EBITDA - dette nette actuelle
    """
    if sig.ebe is None or sig.ebe <= 0:
        return 0.0  # pas d'EBITDA positif → 0 capacité
    if ratios.dette_nette_ebitda is None:
        return 3.0 * sig.ebe
    current_debt = ratios.dette_nette_ebitda * sig.ebe
    target_debt = 3.0 * sig.ebe
    return max(0.0, target_debt - current_debt)


# ==============================================================================
# Croissance (calculs multi-années)
# ==============================================================================

@dataclass
class GrowthMetrics:
    """Métriques de croissance calculées sur plusieurs exercices."""

    cagr_ca: float | None = None              # CAGR chiffre d'affaires
    cagr_ebitda: float | None = None          # CAGR EBE
    cagr_resultat_net: float | None = None
    tendance_marge_ebitda: float | None = None  # variation %pts entre 1er et dernier
    nb_annees: int = 0


def compute_growth(yearly_data: list[tuple[YearAccounts, SIG]]) -> GrowthMetrics:
    """Calcule CAGR et tendances à partir de plusieurs exercices triés par année."""
    if len(yearly_data) < 2:
        return GrowthMetrics(nb_annees=len(yearly_data))

    # Tri ascendant par année
    sorted_data = sorted(yearly_data, key=lambda t: t[0].annee)
    first_y, first_sig = sorted_data[0]
    last_y, last_sig = sorted_data[-1]
    nb_years = last_y.annee - first_y.annee

    def _cagr(start: float | None, end: float | None, n: int) -> float | None:
        if start is None or end is None or n <= 0:
            return None
        if start <= 0 or end <= 0:
            return None
        return (end / start) ** (1 / n) - 1

    cagr_ca = _cagr(first_y.chiffre_affaires, last_y.chiffre_affaires, nb_years)
    cagr_ebitda = _cagr(first_sig.ebe, last_sig.ebe, nb_years)
    cagr_rn = _cagr(first_sig.resultat_net, last_sig.resultat_net, nb_years)

    # Tendance marge EBITDA (variation absolue)
    first_marge = None
    last_marge = None
    if first_y.chiffre_affaires and first_y.chiffre_affaires > 0 and first_sig.ebe is not None:
        first_marge = first_sig.ebe / first_y.chiffre_affaires
    if last_y.chiffre_affaires and last_y.chiffre_affaires > 0 and last_sig.ebe is not None:
        last_marge = last_sig.ebe / last_y.chiffre_affaires
    tend_marge = None
    if first_marge is not None and last_marge is not None:
        tend_marge = last_marge - first_marge

    return GrowthMetrics(
        cagr_ca=cagr_ca,
        cagr_ebitda=cagr_ebitda,
        cagr_resultat_net=cagr_rn,
        tendance_marge_ebitda=tend_marge,
        nb_annees=nb_years,
    )


# ==============================================================================
# Orchestrateur : PmeAnalysis (tout-en-un par société)
# ==============================================================================

@dataclass
class PmeAnalysis:
    """Analyse complète d'une PME : SIG + ratios multi-années + scoring."""

    siren: str
    profile: SectorProfile
    sig_by_year: dict[int, SIG] = field(default_factory=dict)
    ratios_by_year: dict[int, Ratios] = field(default_factory=dict)
    altman_z: float | None = None
    altman_verdict: str = "non_calculable"
    health_score: float | None = None                # 0-100, dernière année
    bankability_score: float | None = None           # 0-100, dernière année
    debt_capacity_estimate: float | None = None      # €, dernière année
    growth: GrowthMetrics = field(default_factory=GrowthMetrics)


def analyze_pme(
    siren: str,
    yearly_accounts: list[YearAccounts],
    profile: SectorProfile,
) -> PmeAnalysis:
    """Analyse complète : calcule tout à partir des comptes + profil sectoriel."""
    if not yearly_accounts:
        return PmeAnalysis(siren=siren, profile=profile)

    # Calculs année par année
    sig_by_year: dict[int, SIG] = {}
    ratios_by_year: dict[int, Ratios] = {}
    for y in yearly_accounts:
        sig = compute_sig(y)
        ratios = compute_ratios(y, sig)
        sig_by_year[y.annee] = sig
        ratios_by_year[y.annee] = ratios

    # Dernière année pour les scores
    last_year = max(ratios_by_year.keys())
    last_y_accounts = next(y for y in yearly_accounts if y.annee == last_year)
    last_sig = sig_by_year[last_year]
    last_ratios = ratios_by_year[last_year]

    # Scoring
    altman = compute_altman_z_private(last_y_accounts, last_sig)
    verdict = altman_z_verdict(altman)
    health = compute_health_score(last_ratios, profile, last_sig)
    bank = compute_bankability_score(last_ratios, last_sig, last_y_accounts)
    debt_cap = estimate_debt_capacity(last_ratios, last_sig)

    # Croissance
    pairs = [(y, sig_by_year[y.annee]) for y in yearly_accounts]
    growth = compute_growth(pairs)

    return PmeAnalysis(
        siren=siren,
        profile=profile,
        sig_by_year=sig_by_year,
        ratios_by_year=ratios_by_year,
        altman_z=altman,
        altman_verdict=verdict,
        health_score=health,
        bankability_score=bank,
        debt_capacity_estimate=debt_cap,
        growth=growth,
    )
