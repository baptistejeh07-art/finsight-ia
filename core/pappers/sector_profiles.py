"""
Registre des 50 profils sectoriels PME non cotées — FinSight.

Chaque profil = une dataclass `SectorProfile` qui encode :
- Les seuils d'alerte spécifiques par ratio (4 bornes : warn_low, normal_low,
  normal_high, warn_high)
- Les multiples de valorisation sectoriels (EV/EBITDA, EV/CA)
- Les médianes sectorielles indicatives (source INSEE ESANE 2023)
- Le vocabulaire narratif (pour le LLM en sortie)

Fonction `resolve_profile(code_naf)` → matche le prefix le plus précis.
Si aucun match : renvoie `GENERIC_SERVICES` / `GENERIC_COMMERCE` / `GENERIC_INDUSTRY`
selon la section NAF macro.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Threshold:
    """Bornes d'alerte pour un ratio (du pire au meilleur, ou inverse selon
    la nature — préciser `higher_is_better`).

    Interprétation :
      - valeur < warn_low  → rouge (ex: marge EBITDA négative)
      - warn_low ≤ valeur < normal_low  → orange
      - normal_low ≤ valeur ≤ normal_high → vert (zone de santé)
      - normal_high < valeur ≤ warn_high → orange (anormalement haut)
      - valeur > warn_high → rouge (ex: dette/EBITDA > 5)
    """
    warn_low: float
    normal_low: float
    normal_high: float
    warn_high: float
    higher_is_better: bool = True

    def classify(self, value: float) -> str:
        """Renvoie 'red' / 'orange' / 'green' / 'orange_high' / 'red_high'."""
        if value < self.warn_low:
            return "red" if self.higher_is_better else "green"
        if value < self.normal_low:
            return "orange" if self.higher_is_better else "orange"
        if value <= self.normal_high:
            return "green"
        if value <= self.warn_high:
            return "orange"
        return "red" if not self.higher_is_better else "orange"


@dataclass(frozen=True)
class SectorProfile:
    """Profil financier d'un secteur d'activité.

    Les `Threshold` encodent la norme sectorielle. Les champs `None` signalent
    qu'un ratio n'est pas pertinent pour ce secteur (ex: rotation stocks pour
    un cabinet d'expertise-comptable).
    """

    # ═══ Identité ═══
    code: str                        # identifiant court (ex: "cabinet_expertise")
    name: str                        # libellé humain FR
    naf_prefixes: tuple[str, ...]    # ex: ("69.20", "69.10")
    description: str                 # phrase descriptive courte

    # ═══ Rentabilité (higher_is_better=True) ═══
    marge_brute: Threshold | None = None         # marge commerciale / CA
    marge_ebitda: Threshold | None = None        # EBE / CA
    marge_nette: Threshold | None = None         # RN / CA
    roce: Threshold | None = None                # REX / capitaux employés
    roe: Threshold | None = None                 # RN / FP

    # ═══ Solidité (certains higher_is_better=False : dette/EBITDA) ═══
    dette_nette_ebitda: Threshold | None = None  # higher_is_better=False
    couverture_interets: Threshold | None = None # EBIT / charges fin.
    autonomie_financiere: Threshold | None = None  # FP / total bilan
    bfr_jours_ca: Threshold | None = None        # BFR en jours de CA (higher_is_better=False)

    # ═══ Efficacité (higher_is_better False pour délais, True pour rotations) ═══
    dso_jours: Threshold | None = None           # higher_is_better=False
    dpo_jours: Threshold | None = None           # neutre (trop haut = risque relation fourn.)
    rotation_stocks: Threshold | None = None     # nombre de rotations/an
    ca_par_employe: Threshold | None = None      # en €

    # ═══ Structure coûts ═══
    charges_perso_ca: Threshold | None = None    # higher_is_better=False mais variable selon sect.

    # ═══ Multiples de valorisation (benchmark M&A) ═══
    ev_ebitda_multiple: float = 6.0
    ev_ca_multiple: float = 0.8

    # ═══ Vocabulaire narratif LLM ═══
    vocab_secteur: str = "secteur"        # ex: "cabinet d'expertise-comptable"
    vocab_peers: str = "sociétés comparables"
    key_drivers: tuple[str, ...] = ()     # ex: ("charges personnel", "DSO", "CA/employé")

    # ═══ Pondération du score santé FinSight 0-100 ═══
    # Poids des 5 grandes familles (somme = 1.0)
    weight_rentabilite: float = 0.30
    weight_solidite: float = 0.30
    weight_efficacite: float = 0.15
    weight_croissance: float = 0.15
    weight_bodacc: float = 0.10


# ==============================================================================
# 50 PROFILS
# ==============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# INDUSTRIE (5)
# ──────────────────────────────────────────────────────────────────────────────

INDUSTRY_HEAVY = SectorProfile(
    code="industry_heavy",
    name="Industrie lourde / capitalistique",
    naf_prefixes=("19", "20.1", "24"),
    description="Sidérurgie, raffinage, chimie de base — CAPEX massif, amortissements longs, dette LT.",
    marge_brute=Threshold(0.10, 0.20, 0.40, 0.60),
    marge_ebitda=Threshold(0.05, 0.10, 0.25, 0.40),
    marge_nette=Threshold(0.00, 0.03, 0.12, 0.25),
    roce=Threshold(0.03, 0.06, 0.15, 0.30),
    roe=Threshold(0.00, 0.05, 0.18, 0.35),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.50, 0.80),
    bfr_jours_ca=Threshold(0, 30, 90, 150, higher_is_better=False),
    dso_jours=Threshold(30, 45, 75, 100, higher_is_better=False),
    dpo_jours=Threshold(30, 50, 90, 120),
    rotation_stocks=Threshold(2, 4, 10, 15),
    ca_par_employe=Threshold(150_000, 250_000, 500_000, 800_000),
    charges_perso_ca=Threshold(0.15, 0.22, 0.35, 0.45, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=0.9,
    vocab_secteur="site industriel", vocab_peers="industriels comparables",
    key_drivers=("CAPEX/amortissements", "dette LT", "couverture intérêts", "BFR stocks"),
)

INDUSTRY_LIGHT = SectorProfile(
    code="industry_light",
    name="Industrie biens de consommation (IAA, textile)",
    naf_prefixes=("10", "11", "13", "14", "15"),
    description="Agroalimentaire, textile, cuir — rotation stocks critique, marges modestes, saisonnalité.",
    marge_brute=Threshold(0.15, 0.25, 0.45, 0.65),
    marge_ebitda=Threshold(0.03, 0.06, 0.15, 0.25),
    marge_nette=Threshold(0.00, 0.02, 0.08, 0.15),
    roce=Threshold(0.05, 0.08, 0.18, 0.30),
    roe=Threshold(0.02, 0.08, 0.20, 0.35),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(0, 30, 75, 120, higher_is_better=False),
    dso_jours=Threshold(20, 40, 70, 100, higher_is_better=False),
    dpo_jours=Threshold(30, 45, 80, 110),
    rotation_stocks=Threshold(3, 5, 12, 20),
    ca_par_employe=Threshold(100_000, 180_000, 350_000, 600_000),
    charges_perso_ca=Threshold(0.15, 0.22, 0.38, 0.50, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.8,
    vocab_secteur="industriel biens de consommation", vocab_peers="industriels du secteur",
    key_drivers=("rotation stocks", "BFR", "saisonnalité", "pression distributeurs"),
)

INDUSTRY_PROCESS = SectorProfile(
    code="industry_process",
    name="Process continu (pharma, cosmétique, chimie fine)",
    naf_prefixes=("20.4", "21", "20.42"),
    description="R&D lourde, marges hautes, CAPEX process, pricing power.",
    marge_brute=Threshold(0.40, 0.55, 0.75, 0.90),
    marge_ebitda=Threshold(0.12, 0.18, 0.30, 0.45),
    marge_nette=Threshold(0.05, 0.10, 0.20, 0.35),
    roce=Threshold(0.08, 0.12, 0.25, 0.40),
    roe=Threshold(0.08, 0.12, 0.25, 0.40),
    dette_nette_ebitda=Threshold(0, 0.5, 2.5, 4.0, higher_is_better=False),
    couverture_interets=Threshold(3.0, 5.0, 12.0, 30.0),
    autonomie_financiere=Threshold(0.25, 0.40, 0.65, 0.85),
    bfr_jours_ca=Threshold(0, 20, 60, 100, higher_is_better=False),
    dso_jours=Threshold(30, 50, 80, 110, higher_is_better=False),
    rotation_stocks=Threshold(4, 6, 12, 18),
    ca_par_employe=Threshold(150_000, 250_000, 500_000, 900_000),
    charges_perso_ca=Threshold(0.15, 0.20, 0.35, 0.45, higher_is_better=False),
    ev_ebitda_multiple=9.0, ev_ca_multiple=1.5,
    vocab_secteur="laboratoire / site process", vocab_peers="sociétés pharma/cosméto",
    key_drivers=("R&D/CA", "pricing power", "CAPEX process", "conformité réglementaire"),
)

INDUSTRY_ASSEMBLY = SectorProfile(
    code="industry_assembly",
    name="Assemblage / sous-traitance mécanique",
    naf_prefixes=("25", "26", "27", "28", "29", "30"),
    description="Sous-traitance aéro/auto/élec — dépendance donneur d'ordre, charges variables dominantes.",
    marge_brute=Threshold(0.10, 0.15, 0.30, 0.45),
    marge_ebitda=Threshold(0.02, 0.05, 0.12, 0.20),
    marge_nette=Threshold(0.00, 0.02, 0.07, 0.12),
    roce=Threshold(0.04, 0.07, 0.15, 0.25),
    roe=Threshold(0.02, 0.06, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.0, 3.5, 5.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 3.0, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(0, 30, 80, 130, higher_is_better=False),
    dso_jours=Threshold(40, 60, 90, 120, higher_is_better=False),
    rotation_stocks=Threshold(3, 5, 12, 20),
    ca_par_employe=Threshold(100_000, 150_000, 300_000, 500_000),
    charges_perso_ca=Threshold(0.20, 0.28, 0.45, 0.55, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=0.6,
    vocab_secteur="atelier / usine d'assemblage", vocab_peers="sous-traitants",
    key_drivers=("dépendance donneur d'ordre", "DSO long", "marge variable", "concentration clients"),
)

INDUSTRY_AGRI = SectorProfile(
    code="industry_agri",
    name="Agro / viticulture / élevage",
    naf_prefixes=("01", "02", "03"),
    description="Cycles annuels, aides PAC, CAPEX terrain/bâtiments, météo-dépendant.",
    marge_brute=Threshold(0.10, 0.20, 0.40, 0.60),
    marge_ebitda=Threshold(0.00, 0.05, 0.18, 0.30),
    marge_nette=Threshold(-0.05, 0.00, 0.10, 0.20),
    roce=Threshold(0.02, 0.04, 0.10, 0.18),
    roe=Threshold(0.00, 0.04, 0.12, 0.25),
    dette_nette_ebitda=Threshold(0, 2.0, 5.0, 8.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.50, 0.70),
    bfr_jours_ca=Threshold(-30, 30, 180, 365, higher_is_better=False),
    ev_ebitda_multiple=7.0, ev_ca_multiple=1.2,
    vocab_secteur="exploitation agricole", vocab_peers="exploitations comparables",
    key_drivers=("cycle annuel", "aides PAC", "stocks agricoles", "CAPEX terrain"),
)

# ──────────────────────────────────────────────────────────────────────────────
# BTP + INGÉNIERIE (4)
# ──────────────────────────────────────────────────────────────────────────────

BTP_HEAVY = SectorProfile(
    code="btp_heavy",
    name="BTP — Gros œuvre",
    naf_prefixes=("41.2", "42.1", "42.2"),
    description="Chantiers longs, BFR lourd, cautions bancaires, appels d'offres publics.",
    marge_brute=Threshold(0.08, 0.12, 0.22, 0.35),
    marge_ebitda=Threshold(0.02, 0.04, 0.10, 0.18),
    marge_nette=Threshold(0.00, 0.01, 0.06, 0.12),
    roce=Threshold(0.04, 0.07, 0.15, 0.25),
    roe=Threshold(0.02, 0.06, 0.15, 0.30),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-30, 30, 90, 180, higher_is_better=False),
    dso_jours=Threshold(45, 60, 90, 120, higher_is_better=False),
    ca_par_employe=Threshold(120_000, 180_000, 320_000, 500_000),
    charges_perso_ca=Threshold(0.20, 0.28, 0.42, 0.55, higher_is_better=False),
    ev_ebitda_multiple=4.5, ev_ca_multiple=0.4,
    vocab_secteur="entreprise générale BTP", vocab_peers="sociétés de gros œuvre",
    key_drivers=("carnet commandes", "cautions", "BFR chantier", "délais paiement publics"),
)

BTP_LIGHT = SectorProfile(
    code="btp_light",
    name="BTP — Second œuvre",
    naf_prefixes=("43",),
    description="Plomberie, électricité, finitions — cycles courts, TVA auto-liquidation, BFR contenu.",
    marge_brute=Threshold(0.15, 0.22, 0.35, 0.50),
    marge_ebitda=Threshold(0.04, 0.07, 0.15, 0.22),
    marge_nette=Threshold(0.00, 0.02, 0.08, 0.15),
    roce=Threshold(0.06, 0.10, 0.20, 0.35),
    roe=Threshold(0.04, 0.08, 0.20, 0.35),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.50, 0.75),
    bfr_jours_ca=Threshold(0, 20, 60, 100, higher_is_better=False),
    dso_jours=Threshold(30, 45, 75, 100, higher_is_better=False),
    ca_par_employe=Threshold(100_000, 150_000, 280_000, 450_000),
    charges_perso_ca=Threshold(0.25, 0.32, 0.48, 0.60, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.5,
    vocab_secteur="entreprise second œuvre", vocab_peers="artisans et PME du second œuvre",
    key_drivers=("carnet commandes court", "intérim vs salariat", "RGE/qualifications"),
)

BTP_PUBLIC = SectorProfile(
    code="btp_public",
    name="Travaux publics / infrastructures",
    naf_prefixes=("42", "42.9"),
    description="Marchés publics, cautions solidaires, délais paiement État/collectivités.",
    marge_brute=Threshold(0.08, 0.12, 0.22, 0.32),
    marge_ebitda=Threshold(0.03, 0.05, 0.12, 0.20),
    marge_nette=Threshold(0.00, 0.02, 0.07, 0.12),
    roce=Threshold(0.04, 0.07, 0.15, 0.25),
    roe=Threshold(0.02, 0.06, 0.16, 0.30),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-30, 40, 120, 200, higher_is_better=False),
    dso_jours=Threshold(60, 75, 100, 130, higher_is_better=False),
    charges_perso_ca=Threshold(0.20, 0.28, 0.42, 0.55, higher_is_better=False),
    ev_ebitda_multiple=4.5, ev_ca_multiple=0.4,
    vocab_secteur="entreprise TP", vocab_peers="sociétés de TP",
    key_drivers=("dépendance marchés publics", "DSO 60-100j", "cautions", "CAPEX flotte"),
)

ARCHITECTURE_ENG = SectorProfile(
    code="architecture_engineering",
    name="Architecture / ingénierie / bureaux d'études",
    naf_prefixes=("71.1", "71.2"),
    description="Services intellectuels techniques — CA projet, CA/employé élevé, charges perso dominantes.",
    marge_brute=Threshold(0.40, 0.55, 0.75, 0.90),
    marge_ebitda=Threshold(0.05, 0.10, 0.20, 0.30),
    marge_nette=Threshold(0.02, 0.05, 0.15, 0.25),
    roce=Threshold(0.10, 0.15, 0.30, 0.50),
    roe=Threshold(0.08, 0.15, 0.30, 0.50),
    dette_nette_ebitda=Threshold(-2.0, 0, 2.0, 3.5, higher_is_better=False),
    couverture_interets=Threshold(3.0, 5.0, 15.0, 50.0),
    autonomie_financiere=Threshold(0.30, 0.45, 0.75, 0.95),
    bfr_jours_ca=Threshold(0, 30, 90, 120, higher_is_better=False),
    dso_jours=Threshold(40, 55, 85, 110, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 120_000, 200_000, 350_000),
    charges_perso_ca=Threshold(0.45, 0.55, 0.70, 0.80, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.8,
    vocab_secteur="cabinet d'architecture / bureau d'études",
    vocab_peers="cabinets et BET comparables",
    key_drivers=("charges personnel 55-70%", "DSO projet", "CA/employé", "honoraires vs forfait"),
    weight_rentabilite=0.30, weight_solidite=0.25, weight_efficacite=0.20, weight_croissance=0.15,
    weight_bodacc=0.10,
)

# ──────────────────────────────────────────────────────────────────────────────
# COMMERCE (8)
# ──────────────────────────────────────────────────────────────────────────────

COMMERCE_WHOLESALE_FOOD = SectorProfile(
    code="commerce_wholesale_food",
    name="Commerce de gros alimentaire",
    naf_prefixes=("46.3",),
    description="Rotation stocks critique, BFR équilibré, marges faibles sur volumes.",
    marge_brute=Threshold(0.08, 0.12, 0.20, 0.30),
    marge_ebitda=Threshold(0.02, 0.04, 0.08, 0.14),
    marge_nette=Threshold(0.00, 0.01, 0.04, 0.08),
    roce=Threshold(0.06, 0.10, 0.20, 0.35),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.65),
    bfr_jours_ca=Threshold(0, 15, 45, 80, higher_is_better=False),
    dso_jours=Threshold(15, 30, 60, 90, higher_is_better=False),
    dpo_jours=Threshold(30, 45, 75, 100),
    rotation_stocks=Threshold(10, 20, 40, 80),
    ca_par_employe=Threshold(250_000, 400_000, 800_000, 1_500_000),
    charges_perso_ca=Threshold(0.05, 0.08, 0.15, 0.22, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.3,
    vocab_secteur="grossiste alimentaire", vocab_peers="grossistes du secteur",
    key_drivers=("rotation stocks", "DPO stratégique", "marge faible volume", "logistique"),
)

COMMERCE_WHOLESALE_NONFOOD = SectorProfile(
    code="commerce_wholesale_nonfood",
    name="Commerce de gros non-alimentaire",
    naf_prefixes=("46.5", "46.6", "46.7", "46.9"),
    description="Produits industriels/B2B — marges plus hautes, DPO levier stratégique.",
    marge_brute=Threshold(0.15, 0.22, 0.35, 0.50),
    marge_ebitda=Threshold(0.04, 0.07, 0.14, 0.22),
    marge_nette=Threshold(0.01, 0.03, 0.08, 0.14),
    roce=Threshold(0.08, 0.12, 0.22, 0.35),
    roe=Threshold(0.06, 0.10, 0.20, 0.32),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(0, 30, 80, 120, higher_is_better=False),
    dso_jours=Threshold(30, 45, 70, 100, higher_is_better=False),
    dpo_jours=Threshold(40, 60, 90, 120),
    rotation_stocks=Threshold(4, 6, 12, 20),
    ca_par_employe=Threshold(200_000, 350_000, 700_000, 1_200_000),
    charges_perso_ca=Threshold(0.08, 0.12, 0.22, 0.32, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=0.5,
    vocab_secteur="grossiste / distributeur", vocab_peers="grossistes B2B",
    key_drivers=("DPO négociation fournisseurs", "marge produit", "stock mort"),
)

COMMERCE_RETAIL_FOOD = SectorProfile(
    code="commerce_retail_food",
    name="Commerce de détail alimentaire (GMS, proximité)",
    naf_prefixes=("47.1", "47.2"),
    description="Trésorerie J+1 ou J+0, marges faibles mais volume, saisonnalité fêtes.",
    marge_brute=Threshold(0.18, 0.24, 0.32, 0.42),
    marge_ebitda=Threshold(0.02, 0.04, 0.08, 0.14),
    marge_nette=Threshold(0.00, 0.01, 0.04, 0.07),
    roce=Threshold(0.06, 0.10, 0.20, 0.35),
    roe=Threshold(0.05, 0.10, 0.20, 0.35),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.65),
    bfr_jours_ca=Threshold(-20, -5, 20, 45, higher_is_better=False),
    dso_jours=Threshold(0, 2, 10, 20, higher_is_better=False),
    dpo_jours=Threshold(30, 45, 75, 100),
    rotation_stocks=Threshold(15, 25, 50, 100),
    ca_par_employe=Threshold(180_000, 280_000, 500_000, 900_000),
    charges_perso_ca=Threshold(0.08, 0.12, 0.20, 0.28, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.3,
    vocab_secteur="magasin alimentaire", vocab_peers="commerces alimentaires",
    key_drivers=("rotation stocks courte", "trésorerie quotidienne", "loyer/m²"),
)

COMMERCE_RETAIL_SPEC = SectorProfile(
    code="commerce_retail_spec",
    name="Commerce de détail spécialisé (mode, déco, sport)",
    naf_prefixes=("47.4", "47.5", "47.6", "47.7"),
    description="Marge+, forte saisonnalité, risque stock obsolète (mode), loyer/CA critique.",
    marge_brute=Threshold(0.30, 0.45, 0.60, 0.75),
    marge_ebitda=Threshold(0.05, 0.10, 0.18, 0.28),
    marge_nette=Threshold(0.01, 0.03, 0.10, 0.18),
    roce=Threshold(0.08, 0.12, 0.25, 0.40),
    roe=Threshold(0.06, 0.12, 0.25, 0.40),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-20, 20, 80, 150, higher_is_better=False),
    rotation_stocks=Threshold(3, 5, 10, 20),
    ca_par_employe=Threshold(120_000, 200_000, 400_000, 700_000),
    charges_perso_ca=Threshold(0.10, 0.15, 0.25, 0.35, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.8,
    vocab_secteur="boutique / enseigne spécialisée", vocab_peers="enseignes comparables",
    key_drivers=("rotation collection", "loyer/CA", "risque obsolescence stock", "saisonnalité"),
)

COMMERCE_ECOMMERCE = SectorProfile(
    code="commerce_ecommerce",
    name="E-commerce pure player",
    naf_prefixes=("47.91",),
    description="CAPEX tech + pub, logistique externe, CAC/LTV, croissance prioritaire.",
    marge_brute=Threshold(0.30, 0.45, 0.60, 0.75),
    marge_ebitda=Threshold(-0.05, 0.02, 0.12, 0.25),
    marge_nette=Threshold(-0.10, -0.02, 0.08, 0.18),
    roce=Threshold(0.00, 0.08, 0.25, 0.50),
    roe=Threshold(-0.05, 0.05, 0.25, 0.50),
    dette_nette_ebitda=Threshold(-5.0, -1.0, 2.0, 4.0, higher_is_better=False),
    couverture_interets=Threshold(1.0, 2.5, 8.0, 30.0),
    autonomie_financiere=Threshold(0.15, 0.30, 0.55, 0.85),
    bfr_jours_ca=Threshold(-60, -30, 20, 60, higher_is_better=False),
    rotation_stocks=Threshold(6, 10, 20, 40),
    ca_par_employe=Threshold(200_000, 350_000, 700_000, 1_500_000),
    charges_perso_ca=Threshold(0.08, 0.12, 0.22, 0.32, higher_is_better=False),
    ev_ebitda_multiple=10.0, ev_ca_multiple=1.5,
    vocab_secteur="pure player e-commerce", vocab_peers="e-commerces du secteur",
    key_drivers=("CAC/LTV", "marketing/CA", "logistique externalisée", "cash burn vs croissance"),
    weight_rentabilite=0.25, weight_solidite=0.25, weight_efficacite=0.15, weight_croissance=0.25,
    weight_bodacc=0.10,
)

COMMERCE_AUTO = SectorProfile(
    code="commerce_auto",
    name="Automobile (concession + réparation)",
    naf_prefixes=("45",),
    description="Stock véhicules massif, crédit client, SAV récurrent, marge constructeur.",
    marge_brute=Threshold(0.10, 0.15, 0.22, 0.32),
    marge_ebitda=Threshold(0.02, 0.04, 0.08, 0.14),
    marge_nette=Threshold(0.00, 0.01, 0.04, 0.08),
    roce=Threshold(0.05, 0.08, 0.15, 0.25),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 3.0, 7.0, 15.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.65),
    bfr_jours_ca=Threshold(0, 30, 90, 150, higher_is_better=False),
    rotation_stocks=Threshold(3, 5, 12, 20),
    ca_par_employe=Threshold(250_000, 400_000, 800_000, 1_500_000),
    charges_perso_ca=Threshold(0.08, 0.12, 0.20, 0.30, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.3,
    vocab_secteur="concession / garage", vocab_peers="concessions comparables",
    key_drivers=("stock véhicules", "marge constructeur", "SAV récurrent"),
)

COMMERCE_FUEL = SectorProfile(
    code="commerce_fuel",
    name="Stations-service / carburants",
    naf_prefixes=("47.3",),
    description="Marge très fine sur carburant, TICPE, volume dominant, shop en complément.",
    marge_brute=Threshold(0.05, 0.08, 0.15, 0.22),
    marge_ebitda=Threshold(0.01, 0.03, 0.07, 0.12),
    marge_nette=Threshold(-0.01, 0.01, 0.04, 0.08),
    roce=Threshold(0.04, 0.07, 0.15, 0.25),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.5, 3.5, 5.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 3.0, 7.0, 15.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-10, 5, 25, 50, higher_is_better=False),
    rotation_stocks=Threshold(20, 35, 70, 120),
    ca_par_employe=Threshold(500_000, 800_000, 1_500_000, 3_000_000),
    charges_perso_ca=Threshold(0.02, 0.04, 0.10, 0.15, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.15,
    vocab_secteur="station-service", vocab_peers="stations comparables",
    key_drivers=("volume carburant", "marge shop", "emplacement", "dépendance pétrolier"),
)

COMMERCE_PHARMA = SectorProfile(
    code="commerce_pharma",
    name="Pharmacie d'officine",
    naf_prefixes=("47.73",),
    description="Marge régulée LFSS, monopole territorial, CA remboursé stable, défenses élevées.",
    marge_brute=Threshold(0.22, 0.28, 0.35, 0.42),
    marge_ebitda=Threshold(0.06, 0.10, 0.16, 0.24),
    marge_nette=Threshold(0.02, 0.04, 0.10, 0.16),
    roce=Threshold(0.08, 0.12, 0.22, 0.35),
    roe=Threshold(0.06, 0.10, 0.20, 0.32),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(0, 20, 50, 80, higher_is_better=False),
    dso_jours=Threshold(10, 20, 45, 70, higher_is_better=False),  # CPAM paie à 30j
    rotation_stocks=Threshold(8, 12, 20, 35),
    ca_par_employe=Threshold(250_000, 350_000, 550_000, 800_000),
    charges_perso_ca=Threshold(0.10, 0.13, 0.20, 0.28, higher_is_better=False),
    ev_ebitda_multiple=7.0, ev_ca_multiple=0.75,
    vocab_secteur="officine", vocab_peers="pharmacies comparables",
    key_drivers=("CA remboursé", "marge réglementée", "parapharmacie", "emplacement"),
)

# ──────────────────────────────────────────────────────────────────────────────
# SERVICES B2B (6)
# ──────────────────────────────────────────────────────────────────────────────

CABINET_EXPERTISE = SectorProfile(
    code="cabinet_expertise",
    name="Cabinets d'expertise (compta, audit, avocats, notaires)",
    naf_prefixes=("69.20", "69.10", "74"),
    description="Services intellectuels B2B — charges personnel dominantes (70-85%), DSO long.",
    marge_brute=Threshold(0.70, 0.80, 0.95, 1.00),
    marge_ebitda=Threshold(0.05, 0.10, 0.22, 0.35),
    marge_nette=Threshold(0.03, 0.06, 0.16, 0.28),
    roce=Threshold(0.10, 0.18, 0.35, 0.60),
    roe=Threshold(0.10, 0.15, 0.30, 0.50),
    dette_nette_ebitda=Threshold(-3.0, -1.0, 1.5, 3.0, higher_is_better=False),
    couverture_interets=Threshold(3.0, 5.0, 15.0, 50.0),
    autonomie_financiere=Threshold(0.30, 0.45, 0.75, 0.95),
    bfr_jours_ca=Threshold(0, 30, 90, 150, higher_is_better=False),
    dso_jours=Threshold(45, 60, 90, 120, higher_is_better=False),
    ca_par_employe=Threshold(60_000, 85_000, 140_000, 220_000),
    charges_perso_ca=Threshold(0.50, 0.60, 0.80, 0.90, higher_is_better=False),
    ev_ebitda_multiple=6.5, ev_ca_multiple=1.2,
    vocab_secteur="cabinet", vocab_peers="cabinets comparables",
    key_drivers=("charges personnel 60-80%", "DSO 60-90j", "CA/employé", "associés vs salariés"),
    weight_rentabilite=0.30, weight_solidite=0.25, weight_efficacite=0.20, weight_croissance=0.15,
    weight_bodacc=0.10,
)

CONSEIL_STRATEGIC = SectorProfile(
    code="conseil_strategic",
    name="Conseil stratégique / digital",
    naf_prefixes=("70.2", "70.21", "70.22"),
    description="Missions à forte VA, CA/employé élevé, missions projet.",
    marge_brute=Threshold(0.60, 0.75, 0.90, 1.00),
    marge_ebitda=Threshold(0.10, 0.18, 0.30, 0.45),
    marge_nette=Threshold(0.05, 0.10, 0.22, 0.35),
    roce=Threshold(0.15, 0.25, 0.50, 0.80),
    roe=Threshold(0.12, 0.20, 0.40, 0.65),
    dette_nette_ebitda=Threshold(-3.0, -1.0, 1.5, 3.0, higher_is_better=False),
    couverture_interets=Threshold(3.0, 5.0, 15.0, 50.0),
    autonomie_financiere=Threshold(0.35, 0.50, 0.80, 0.95),
    bfr_jours_ca=Threshold(0, 40, 100, 150, higher_is_better=False),
    dso_jours=Threshold(45, 60, 90, 120, higher_is_better=False),
    ca_par_employe=Threshold(100_000, 150_000, 250_000, 400_000),
    charges_perso_ca=Threshold(0.40, 0.50, 0.70, 0.80, higher_is_better=False),
    ev_ebitda_multiple=7.5, ev_ca_multiple=1.5,
    vocab_secteur="cabinet de conseil", vocab_peers="cabinets de conseil",
    key_drivers=("CA/employé 150-250k€", "TJM vs forfait", "senior ratio"),
)

AGENCE_COMM = SectorProfile(
    code="agence_comm",
    name="Agences com/pub/marketing",
    naf_prefixes=("73",),
    description="CA projet, avances clients, saisonnalité, dépendance grands comptes.",
    marge_brute=Threshold(0.25, 0.35, 0.55, 0.75),
    marge_ebitda=Threshold(0.05, 0.08, 0.18, 0.28),
    marge_nette=Threshold(0.02, 0.04, 0.12, 0.20),
    roce=Threshold(0.10, 0.15, 0.30, 0.50),
    roe=Threshold(0.08, 0.12, 0.25, 0.45),
    dette_nette_ebitda=Threshold(-3.0, -1.0, 1.5, 3.0, higher_is_better=False),
    couverture_interets=Threshold(2.5, 4.0, 10.0, 25.0),
    autonomie_financiere=Threshold(0.25, 0.40, 0.65, 0.90),
    bfr_jours_ca=Threshold(-30, 10, 60, 120, higher_is_better=False),
    dso_jours=Threshold(30, 50, 85, 120, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 120_000, 200_000, 320_000),
    charges_perso_ca=Threshold(0.35, 0.45, 0.65, 0.75, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.8,
    vocab_secteur="agence", vocab_peers="agences comparables",
    key_drivers=("CA projet", "concentration clients", "acompte/facturation", "charges créa"),
)

ESN_SSII = SectorProfile(
    code="esn_ssii",
    name="ESN / SSII / infogérance",
    naf_prefixes=("62.01", "62.02", "62.03", "62.09"),
    description="Facturation TJM, masse salariale dominante, marge brute ~30-40%.",
    marge_brute=Threshold(0.20, 0.28, 0.40, 0.55),
    marge_ebitda=Threshold(0.04, 0.07, 0.13, 0.20),
    marge_nette=Threshold(0.02, 0.04, 0.09, 0.15),
    roce=Threshold(0.10, 0.15, 0.30, 0.50),
    roe=Threshold(0.08, 0.14, 0.28, 0.45),
    dette_nette_ebitda=Threshold(-2.0, -0.5, 1.5, 3.0, higher_is_better=False),
    couverture_interets=Threshold(3.0, 5.0, 15.0, 50.0),
    autonomie_financiere=Threshold(0.25, 0.40, 0.65, 0.85),
    bfr_jours_ca=Threshold(10, 30, 75, 110, higher_is_better=False),
    dso_jours=Threshold(45, 60, 90, 120, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 100_000, 150_000, 220_000),
    charges_perso_ca=Threshold(0.50, 0.60, 0.75, 0.85, higher_is_better=False),
    ev_ebitda_multiple=7.0, ev_ca_multiple=0.8,
    vocab_secteur="ESN / SSII", vocab_peers="ESN comparables",
    key_drivers=("taux occupation", "TJM", "tx de conversion inter-contrat", "turn-over"),
)

BPO_CALL = SectorProfile(
    code="bpo_call",
    name="BPO / centres d'appels / back-office",
    naf_prefixes=("82.2", "82.9"),
    description="Volume, marges faibles, masse salariale, offshore/nearshore.",
    marge_brute=Threshold(0.15, 0.22, 0.32, 0.45),
    marge_ebitda=Threshold(0.02, 0.05, 0.12, 0.20),
    marge_nette=Threshold(0.00, 0.02, 0.07, 0.12),
    roce=Threshold(0.06, 0.10, 0.20, 0.35),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(10, 30, 75, 110, higher_is_better=False),
    dso_jours=Threshold(30, 45, 75, 100, higher_is_better=False),
    ca_par_employe=Threshold(40_000, 55_000, 90_000, 140_000),
    charges_perso_ca=Threshold(0.55, 0.65, 0.80, 0.88, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=0.5,
    vocab_secteur="centre d'appels / BPO", vocab_peers="BPO comparables",
    key_drivers=("volume appels/ticket", "productivité/agent", "turn-over"),
)

INTERIM_RH = SectorProfile(
    code="interim_rh",
    name="Intérim / RH / recrutement",
    naf_prefixes=("78",),
    description="Masse salariale ≈ CA, URSSAF lourde, trésorerie J+45 clients, paiement intérim J+7.",
    marge_brute=Threshold(0.10, 0.14, 0.22, 0.30),
    marge_ebitda=Threshold(0.02, 0.04, 0.08, 0.14),
    marge_nette=Threshold(0.00, 0.01, 0.04, 0.08),
    roce=Threshold(0.08, 0.15, 0.30, 0.50),
    roe=Threshold(0.06, 0.12, 0.25, 0.45),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 5.0, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.05, 0.15, 0.35, 0.60),
    bfr_jours_ca=Threshold(20, 30, 55, 80, higher_is_better=False),
    dso_jours=Threshold(30, 45, 70, 100, higher_is_better=False),
    ca_par_employe=Threshold(250_000, 400_000, 800_000, 1_500_000),  # CA/permanent
    charges_perso_ca=Threshold(0.75, 0.80, 0.88, 0.93, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.3,
    vocab_secteur="agence d'intérim", vocab_peers="agences d'intérim",
    key_drivers=("délais paie intérimaire", "DSO client", "URSSAF", "marge permanents vs intérim"),
)

# ──────────────────────────────────────────────────────────────────────────────
# TECH / SOFTWARE (4)
# ──────────────────────────────────────────────────────────────────────────────

SAAS_B2B = SectorProfile(
    code="saas_b2b",
    name="SaaS B2B / éditeur logiciel",
    naf_prefixes=("58.29", "62.01"),  # note: 62.01 partagé ESN/éditeur, distinction via mots-clés
    description="MRR récurrent, CAPEX faible, R&D capitalisée, croissance prioritaire.",
    marge_brute=Threshold(0.60, 0.70, 0.85, 0.95),
    marge_ebitda=Threshold(-0.20, 0.00, 0.25, 0.40),
    marge_nette=Threshold(-0.25, -0.05, 0.15, 0.30),
    roce=Threshold(-0.10, 0.05, 0.30, 0.60),
    roe=Threshold(-0.20, 0.00, 0.25, 0.50),
    dette_nette_ebitda=Threshold(-5.0, -2.0, 2.0, 4.0, higher_is_better=False),
    couverture_interets=Threshold(0.0, 2.0, 10.0, 50.0),
    autonomie_financiere=Threshold(0.30, 0.50, 0.80, 0.95),
    bfr_jours_ca=Threshold(-90, -45, 30, 90, higher_is_better=False),
    dso_jours=Threshold(20, 35, 60, 90, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 150_000, 300_000, 600_000),
    charges_perso_ca=Threshold(0.35, 0.45, 0.65, 0.80, higher_is_better=False),
    ev_ebitda_multiple=12.0, ev_ca_multiple=4.0,
    vocab_secteur="éditeur SaaS", vocab_peers="éditeurs SaaS comparables",
    key_drivers=("MRR/ARR", "CAC/LTV", "NRR", "burn rate", "R&D/CA"),
    weight_rentabilite=0.20, weight_solidite=0.25, weight_efficacite=0.15, weight_croissance=0.30,
    weight_bodacc=0.10,
)

DEEP_TECH = SectorProfile(
    code="deep_tech",
    name="Deep tech / biotech / R&D intensive",
    naf_prefixes=("72",),
    description="Subventions CIR, cash burn long, cycles R&D 5-10 ans, valorisation actifs incorporels.",
    marge_brute=Threshold(0.30, 0.50, 0.80, 0.95),
    marge_ebitda=Threshold(-0.50, -0.20, 0.10, 0.30),
    marge_nette=Threshold(-0.60, -0.30, 0.05, 0.25),
    roce=Threshold(-0.30, -0.10, 0.15, 0.40),
    roe=Threshold(-0.40, -0.15, 0.15, 0.40),
    dette_nette_ebitda=Threshold(-10.0, -3.0, 2.0, 5.0, higher_is_better=False),
    autonomie_financiere=Threshold(0.40, 0.60, 0.85, 0.98),
    bfr_jours_ca=Threshold(-180, -60, 60, 180, higher_is_better=False),
    ca_par_employe=Threshold(30_000, 80_000, 200_000, 500_000),
    charges_perso_ca=Threshold(0.40, 0.55, 0.90, 1.50, higher_is_better=False),
    ev_ebitda_multiple=15.0, ev_ca_multiple=6.0,  # très difficile à estimer
    vocab_secteur="deep tech / labo R&D", vocab_peers="startups deep tech comparables",
    key_drivers=("runway", "burn rate", "subventions CIR/JEI", "dilution capital"),
    weight_rentabilite=0.15, weight_solidite=0.25, weight_efficacite=0.10, weight_croissance=0.40,
    weight_bodacc=0.10,
)

CLOUD_HOSTING = SectorProfile(
    code="cloud_hosting",
    name="Hébergement / cloud / datacenters",
    naf_prefixes=("63.11", "63.12"),
    description="CAPEX serveurs/datacenter, contrats récurrents, consommation énergie.",
    marge_brute=Threshold(0.30, 0.45, 0.60, 0.75),
    marge_ebitda=Threshold(0.15, 0.25, 0.40, 0.55),
    marge_nette=Threshold(0.05, 0.10, 0.20, 0.32),
    roce=Threshold(0.05, 0.10, 0.20, 0.35),
    roe=Threshold(0.06, 0.12, 0.25, 0.45),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(2.5, 4.0, 10.0, 25.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.55, 0.80),
    bfr_jours_ca=Threshold(-60, -30, 30, 60, higher_is_better=False),
    dso_jours=Threshold(15, 30, 60, 90, higher_is_better=False),
    ca_par_employe=Threshold(150_000, 250_000, 500_000, 1_000_000),
    charges_perso_ca=Threshold(0.15, 0.22, 0.40, 0.50, higher_is_better=False),
    ev_ebitda_multiple=10.0, ev_ca_multiple=3.0,
    vocab_secteur="hébergeur / datacenter", vocab_peers="hébergeurs comparables",
    key_drivers=("CAPEX serveurs", "contrats MRR/récurrents", "consommation énergie"),
)

GAMING_MEDIA = SectorProfile(
    code="gaming_media",
    name="Jeux vidéo / production audiovisuelle",
    naf_prefixes=("58.2", "59", "60"),
    description="IP propriétaire, catalogue, cycles projet longs, royalties, financement complexe.",
    marge_brute=Threshold(0.30, 0.45, 0.65, 0.85),
    marge_ebitda=Threshold(0.00, 0.08, 0.22, 0.40),
    marge_nette=Threshold(-0.10, 0.00, 0.15, 0.30),
    roce=Threshold(0.00, 0.08, 0.25, 0.50),
    roe=Threshold(-0.05, 0.06, 0.25, 0.50),
    dette_nette_ebitda=Threshold(-3.0, -0.5, 2.5, 5.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 3.0, 10.0, 50.0),
    autonomie_financiere=Threshold(0.20, 0.35, 0.65, 0.90),
    bfr_jours_ca=Threshold(-60, -20, 60, 180, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 150_000, 300_000, 600_000),
    charges_perso_ca=Threshold(0.30, 0.45, 0.65, 0.80, higher_is_better=False),
    ev_ebitda_multiple=9.0, ev_ca_multiple=2.0,
    vocab_secteur="studio de création", vocab_peers="studios comparables",
    key_drivers=("catalogue IP", "royalties/licences", "pré-financement projets"),
)

# ──────────────────────────────────────────────────────────────────────────────
# TÉLÉCOMS + MÉDIA (2)
# ──────────────────────────────────────────────────────────────────────────────

TELECOM_ISP = SectorProfile(
    code="telecom_isp",
    name="Télécoms opérateurs / FAI",
    naf_prefixes=("61",),
    description="CAPEX réseau massif, MRR abonnés, churn, régulation ARCEP.",
    marge_brute=Threshold(0.40, 0.55, 0.70, 0.85),
    marge_ebitda=Threshold(0.15, 0.25, 0.40, 0.55),
    marge_nette=Threshold(0.03, 0.08, 0.18, 0.30),
    roce=Threshold(0.04, 0.08, 0.15, 0.25),
    roe=Threshold(0.05, 0.10, 0.20, 0.35),
    dette_nette_ebitda=Threshold(0, 2.0, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.55, 0.80),
    bfr_jours_ca=Threshold(-45, -15, 30, 75, higher_is_better=False),
    dso_jours=Threshold(15, 30, 60, 90, higher_is_better=False),
    ca_par_employe=Threshold(150_000, 250_000, 500_000, 1_000_000),
    charges_perso_ca=Threshold(0.15, 0.22, 0.35, 0.45, higher_is_better=False),
    ev_ebitda_multiple=7.0, ev_ca_multiple=2.0,
    vocab_secteur="opérateur télécom / FAI", vocab_peers="opérateurs comparables",
    key_drivers=("CAPEX réseau", "churn abonnés", "ARPU", "régulation ARCEP"),
)

EDITION_PRESSE = SectorProfile(
    code="edition_presse",
    name="Édition / presse",
    naf_prefixes=("58.1",),
    description="Stocks invendus, pub/abonnements, droits d'auteur, distribution.",
    marge_brute=Threshold(0.30, 0.45, 0.60, 0.75),
    marge_ebitda=Threshold(0.02, 0.06, 0.15, 0.25),
    marge_nette=Threshold(0.00, 0.02, 0.08, 0.15),
    roce=Threshold(0.04, 0.08, 0.18, 0.30),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.55, 0.80),
    bfr_jours_ca=Threshold(0, 30, 90, 150, higher_is_better=False),
    rotation_stocks=Threshold(2, 4, 8, 15),
    ca_par_employe=Threshold(120_000, 180_000, 320_000, 550_000),
    charges_perso_ca=Threshold(0.20, 0.28, 0.45, 0.55, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.8,
    vocab_secteur="éditeur / titre de presse", vocab_peers="éditeurs comparables",
    key_drivers=("stocks invendus", "mix pub/abonnement", "droits"),
)

# ──────────────────────────────────────────────────────────────────────────────
# HÔTELLERIE / RESTAURATION (5)
# ──────────────────────────────────────────────────────────────────────────────

RESTAURATION_INDEP = SectorProfile(
    code="restauration_indep",
    name="Restauration indépendante",
    naf_prefixes=("56.10",),
    description="Encaissement J+0, loyer/CA critique, CCN lourde, saisonnalité.",
    marge_brute=Threshold(0.55, 0.65, 0.75, 0.85),
    marge_ebitda=Threshold(0.03, 0.06, 0.14, 0.22),
    marge_nette=Threshold(-0.02, 0.01, 0.06, 0.12),
    roce=Threshold(0.04, 0.08, 0.18, 0.35),
    roe=Threshold(0.04, 0.08, 0.20, 0.40),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.65),
    bfr_jours_ca=Threshold(-30, -10, 15, 40, higher_is_better=False),
    dso_jours=Threshold(0, 2, 10, 25, higher_is_better=False),
    rotation_stocks=Threshold(15, 25, 50, 100),
    ca_par_employe=Threshold(50_000, 70_000, 120_000, 200_000),
    charges_perso_ca=Threshold(0.28, 0.33, 0.42, 0.50, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.5,
    vocab_secteur="restaurant", vocab_peers="restaurants comparables",
    key_drivers=("loyer/CA", "ticket moyen", "emplacement", "charges perso/CA"),
)

RESTAURATION_CHAINE = SectorProfile(
    code="restauration_chaine",
    name="Chaîne de restauration / franchise",
    naf_prefixes=("56.10",),
    description="Royalties franchiseur, standardisation, scale, CAPEX multi-sites.",
    marge_brute=Threshold(0.55, 0.65, 0.75, 0.85),
    marge_ebitda=Threshold(0.06, 0.10, 0.18, 0.28),
    marge_nette=Threshold(0.00, 0.03, 0.10, 0.18),
    roce=Threshold(0.08, 0.15, 0.30, 0.50),
    roe=Threshold(0.08, 0.15, 0.30, 0.50),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 5.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    ca_par_employe=Threshold(60_000, 90_000, 150_000, 250_000),
    charges_perso_ca=Threshold(0.25, 0.30, 0.40, 0.48, higher_is_better=False),
    ev_ebitda_multiple=7.0, ev_ca_multiple=0.9,
    vocab_secteur="chaîne de restauration", vocab_peers="chaînes comparables",
    key_drivers=("royalties", "CAPEX multi-sites", "standardisation", "ticket moyen"),
)

DEBITS_BOISSONS = SectorProfile(
    code="debits_boissons",
    name="Débits de boissons / bars / discothèques",
    naf_prefixes=("56.3",),
    description="Licence IV, trésorerie J+0, marge alcool, saisonnalité nuit/week-end.",
    marge_brute=Threshold(0.55, 0.65, 0.75, 0.85),
    marge_ebitda=Threshold(0.04, 0.08, 0.18, 0.28),
    marge_nette=Threshold(0.00, 0.02, 0.10, 0.18),
    roce=Threshold(0.06, 0.12, 0.25, 0.45),
    roe=Threshold(0.06, 0.12, 0.25, 0.45),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 3.0, 7.0, 15.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.65),
    bfr_jours_ca=Threshold(-45, -15, 10, 30, higher_is_better=False),
    dso_jours=Threshold(0, 1, 5, 15, higher_is_better=False),
    ca_par_employe=Threshold(60_000, 90_000, 150_000, 250_000),
    charges_perso_ca=Threshold(0.20, 0.25, 0.35, 0.42, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.6,
    vocab_secteur="bar / discothèque", vocab_peers="établissements comparables",
    key_drivers=("licence IV", "marge alcool", "loyer/CA", "sécurité"),
)

TRAITEUR_EVENT = SectorProfile(
    code="traiteur_event",
    name="Traiteur / événementiel",
    naf_prefixes=("56.21", "82.3"),
    description="BFR projet, acomptes clients, saisonnalité forte, logistique.",
    marge_brute=Threshold(0.35, 0.45, 0.60, 0.75),
    marge_ebitda=Threshold(0.05, 0.08, 0.16, 0.25),
    marge_nette=Threshold(0.01, 0.03, 0.10, 0.18),
    roce=Threshold(0.08, 0.12, 0.25, 0.40),
    roe=Threshold(0.06, 0.10, 0.22, 0.40),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 5.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-60, -20, 40, 100, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 120_000, 220_000, 400_000),
    charges_perso_ca=Threshold(0.25, 0.32, 0.45, 0.55, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=0.7,
    vocab_secteur="traiteur / organisateur événementiel",
    vocab_peers="traiteurs / agences événementielles comparables",
    key_drivers=("saisonnalité", "acompte client", "logistique mobile", "équipes intermittents"),
)

HOTELLERIE = SectorProfile(
    code="hotellerie",
    name="Hôtellerie",
    naf_prefixes=("55",),
    description="Saisonnalité forte, CAPEX bâtiment, RevPAR, ADR, taux d'occupation.",
    marge_brute=Threshold(0.65, 0.75, 0.85, 0.95),
    marge_ebitda=Threshold(0.15, 0.22, 0.35, 0.48),
    marge_nette=Threshold(0.00, 0.05, 0.15, 0.28),
    roce=Threshold(0.04, 0.08, 0.18, 0.30),
    roe=Threshold(0.05, 0.10, 0.22, 0.40),
    dette_nette_ebitda=Threshold(0, 2.0, 5.0, 8.0, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.0, 6.0, 15.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.55, 0.80),
    bfr_jours_ca=Threshold(-60, -20, 20, 60, higher_is_better=False),
    ca_par_employe=Threshold(60_000, 90_000, 160_000, 280_000),
    charges_perso_ca=Threshold(0.22, 0.28, 0.40, 0.50, higher_is_better=False),
    ev_ebitda_multiple=7.0, ev_ca_multiple=1.5,
    vocab_secteur="hôtel", vocab_peers="hôtels comparables",
    key_drivers=("RevPAR", "ADR", "taux d'occupation", "saisonnalité", "CAPEX rénovation"),
)

# ──────────────────────────────────────────────────────────────────────────────
# TRANSPORT / LOGISTIQUE (4)
# ──────────────────────────────────────────────────────────────────────────────

TRANSPORT_TRM = SectorProfile(
    code="transport_trm",
    name="Transport routier marchandises (TRM)",
    naf_prefixes=("49.41", "52.29"),
    description="CAPEX flotte, carburant variable, CCN roulants, DSO 60j typique.",
    marge_brute=Threshold(0.15, 0.22, 0.32, 0.45),
    marge_ebitda=Threshold(0.05, 0.08, 0.14, 0.22),
    marge_nette=Threshold(0.00, 0.02, 0.06, 0.10),
    roce=Threshold(0.04, 0.07, 0.14, 0.22),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 6.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.40, 0.65),
    bfr_jours_ca=Threshold(15, 30, 60, 100, higher_is_better=False),
    dso_jours=Threshold(45, 60, 80, 110, higher_is_better=False),
    ca_par_employe=Threshold(100_000, 150_000, 250_000, 400_000),
    charges_perso_ca=Threshold(0.25, 0.32, 0.42, 0.50, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.5,
    vocab_secteur="transporteur routier", vocab_peers="TRM comparables",
    key_drivers=("carburant", "CAPEX flotte", "CA/véhicule", "taux de chargement retour"),
)

TRANSPORT_VOYAGEURS = SectorProfile(
    code="transport_voyageurs",
    name="Transport de voyageurs (bus, train, aérien)",
    naf_prefixes=("49.3", "50", "51"),
    description="DSP publiques, CAPEX flotte, contrats collectivités, régulation ART.",
    marge_brute=Threshold(0.15, 0.22, 0.32, 0.45),
    marge_ebitda=Threshold(0.04, 0.07, 0.14, 0.22),
    marge_nette=Threshold(0.00, 0.01, 0.06, 0.10),
    roce=Threshold(0.03, 0.06, 0.12, 0.20),
    roe=Threshold(0.03, 0.06, 0.15, 0.25),
    dette_nette_ebitda=Threshold(0, 2.0, 4.5, 6.5, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.65),
    bfr_jours_ca=Threshold(-30, 0, 45, 90, higher_is_better=False),
    dso_jours=Threshold(30, 50, 80, 120, higher_is_better=False),
    ca_par_employe=Threshold(120_000, 180_000, 300_000, 500_000),
    charges_perso_ca=Threshold(0.25, 0.32, 0.45, 0.55, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.8,
    vocab_secteur="opérateur de transport voyageurs", vocab_peers="opérateurs comparables",
    key_drivers=("DSP publiques", "CAPEX flotte", "taux de remplissage"),
)

TAXI_VTC = SectorProfile(
    code="taxi_vtc",
    name="Taxi / VTC / livraison dernière km",
    naf_prefixes=("49.32", "53.2"),
    description="Plateformes, commissions 15-25%, indépendants en sous-traitance.",
    marge_brute=Threshold(0.60, 0.70, 0.82, 0.92),
    marge_ebitda=Threshold(0.05, 0.08, 0.16, 0.25),
    marge_nette=Threshold(0.00, 0.02, 0.10, 0.18),
    roce=Threshold(0.08, 0.15, 0.30, 0.50),
    roe=Threshold(0.06, 0.12, 0.25, 0.45),
    dette_nette_ebitda=Threshold(-2.0, 0, 2.5, 4.0, higher_is_better=False),
    couverture_interets=Threshold(2.5, 4.0, 10.0, 30.0),
    autonomie_financiere=Threshold(0.20, 0.35, 0.60, 0.85),
    bfr_jours_ca=Threshold(-30, -5, 30, 60, higher_is_better=False),
    ca_par_employe=Threshold(60_000, 90_000, 150_000, 250_000),
    charges_perso_ca=Threshold(0.20, 0.28, 0.45, 0.55, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.9,
    vocab_secteur="flotte VTC/taxis/livraison", vocab_peers="flottes comparables",
    key_drivers=("commission plateforme", "sous-traitance indépendants"),
)

LOGISTIQUE_ENTREPOT = SectorProfile(
    code="logistique_entrepot",
    name="Logistique / entreposage",
    naf_prefixes=("52.1", "52.2"),
    description="CAPEX entrepôt, contrats LT, levier automatisation.",
    marge_brute=Threshold(0.25, 0.35, 0.50, 0.65),
    marge_ebitda=Threshold(0.08, 0.12, 0.22, 0.32),
    marge_nette=Threshold(0.02, 0.05, 0.12, 0.20),
    roce=Threshold(0.05, 0.08, 0.18, 0.30),
    roe=Threshold(0.06, 0.10, 0.22, 0.35),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 5.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.55, 0.80),
    bfr_jours_ca=Threshold(0, 20, 50, 90, higher_is_better=False),
    dso_jours=Threshold(30, 45, 70, 100, higher_is_better=False),
    ca_par_employe=Threshold(100_000, 150_000, 280_000, 450_000),
    charges_perso_ca=Threshold(0.20, 0.28, 0.45, 0.55, higher_is_better=False),
    ev_ebitda_multiple=7.0, ev_ca_multiple=0.9,
    vocab_secteur="entrepôt / plateforme logistique", vocab_peers="logisticiens comparables",
    key_drivers=("CAPEX entrepôt", "contrats LT", "coût m²", "automatisation"),
)

# ──────────────────────────────────────────────────────────────────────────────
# SANTÉ / ENSEIGNEMENT / SOCIAL (5)
# ──────────────────────────────────────────────────────────────────────────────

SANTE_LIBERAL = SectorProfile(
    code="sante_liberal",
    name="Santé libérale (médecins, dentistes, paramédical)",
    naf_prefixes=("86", "87.1"),
    description="Honoraires, URSSAF libéral, CPAM paie 30j, CAPEX équipement médical.",
    marge_brute=Threshold(0.75, 0.85, 0.95, 1.00),
    marge_ebitda=Threshold(0.15, 0.25, 0.40, 0.55),
    marge_nette=Threshold(0.10, 0.15, 0.28, 0.40),
    roce=Threshold(0.10, 0.20, 0.40, 0.70),
    roe=Threshold(0.08, 0.15, 0.30, 0.55),
    dette_nette_ebitda=Threshold(-2.0, 0, 2.0, 3.5, higher_is_better=False),
    couverture_interets=Threshold(3.0, 5.0, 15.0, 50.0),
    autonomie_financiere=Threshold(0.30, 0.45, 0.75, 0.95),
    bfr_jours_ca=Threshold(-15, 5, 30, 60, higher_is_better=False),
    dso_jours=Threshold(10, 20, 45, 70, higher_is_better=False),
    ca_par_employe=Threshold(100_000, 150_000, 280_000, 500_000),
    charges_perso_ca=Threshold(0.15, 0.22, 0.40, 0.55, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=1.0,
    vocab_secteur="cabinet médical", vocab_peers="cabinets comparables",
    key_drivers=("honoraires", "URSSAF libéral", "CAPEX équipement"),
)

EHPAD_SENIORS = SectorProfile(
    code="ehpad_seniors",
    name="EHPAD / résidences services seniors",
    naf_prefixes=("87.1", "87.3"),
    description="Tarification ARS/CD, CCN lourde, CAPEX bâtiment, GIR et taux d'occupation.",
    marge_brute=Threshold(0.70, 0.80, 0.90, 0.97),
    marge_ebitda=Threshold(0.08, 0.15, 0.25, 0.35),
    marge_nette=Threshold(0.02, 0.06, 0.15, 0.25),
    roce=Threshold(0.04, 0.08, 0.16, 0.25),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 2.0, 5.0, 7.0, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.0, 6.0, 15.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-45, -20, 15, 40, higher_is_better=False),
    ca_par_employe=Threshold(45_000, 55_000, 75_000, 110_000),
    charges_perso_ca=Threshold(0.50, 0.55, 0.65, 0.72, higher_is_better=False),
    ev_ebitda_multiple=8.0, ev_ca_multiple=1.5,
    vocab_secteur="EHPAD / résidence seniors", vocab_peers="établissements comparables",
    key_drivers=("taux d'occupation", "GIR moyen", "tarification ARS/CD", "charges personnel"),
)

CRECHE = SectorProfile(
    code="creche",
    name="Crèche / petite enfance",
    naf_prefixes=("88.91",),
    description="PSU CAF, agréments, ratio encadrant/enfant, saisonnalité.",
    marge_brute=Threshold(0.75, 0.85, 0.93, 0.98),
    marge_ebitda=Threshold(0.05, 0.10, 0.18, 0.28),
    marge_nette=Threshold(0.01, 0.03, 0.10, 0.18),
    roce=Threshold(0.05, 0.08, 0.18, 0.30),
    roe=Threshold(0.05, 0.10, 0.22, 0.38),
    dette_nette_ebitda=Threshold(0, 1.5, 3.5, 5.0, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.50, 0.75),
    bfr_jours_ca=Threshold(-30, 0, 20, 50, higher_is_better=False),
    ca_par_employe=Threshold(35_000, 45_000, 65_000, 90_000),
    charges_perso_ca=Threshold(0.55, 0.62, 0.72, 0.80, higher_is_better=False),
    ev_ebitda_multiple=8.0, ev_ca_multiple=1.5,
    vocab_secteur="crèche / structure petite enfance", vocab_peers="crèches comparables",
    key_drivers=("PSU CAF", "taux d'encadrement", "agréments PMI", "saisonnalité"),
)

ENSEIGNEMENT_PRIVE = SectorProfile(
    code="enseignement_prive",
    name="Enseignement privé / formation continue",
    naf_prefixes=("85",),
    description="Saisonnalité forte (année scolaire), subventions État/régions, CA prévisible.",
    marge_brute=Threshold(0.75, 0.85, 0.92, 0.98),
    marge_ebitda=Threshold(0.06, 0.10, 0.20, 0.30),
    marge_nette=Threshold(0.02, 0.04, 0.12, 0.20),
    roce=Threshold(0.05, 0.10, 0.20, 0.35),
    roe=Threshold(0.05, 0.10, 0.22, 0.40),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.5, 4.0, 10.0, 25.0),
    autonomie_financiere=Threshold(0.25, 0.35, 0.60, 0.85),
    bfr_jours_ca=Threshold(-60, -20, 30, 75, higher_is_better=False),
    ca_par_employe=Threshold(50_000, 75_000, 130_000, 200_000),
    charges_perso_ca=Threshold(0.50, 0.58, 0.70, 0.78, higher_is_better=False),
    ev_ebitda_multiple=7.5, ev_ca_multiple=1.3,
    vocab_secteur="établissement d'enseignement / organisme formation",
    vocab_peers="établissements comparables",
    key_drivers=("subventions", "effectifs inscrits", "saisonnalité année scolaire"),
)

ASSOCIATION = SectorProfile(
    code="association",
    name="Associations / économie sociale",
    naf_prefixes=("94", "88.99"),
    description="Subventions dominantes, bénévolat (non comptabilisé), fiscalité spécifique OIG/OSBL.",
    marge_brute=Threshold(0.70, 0.85, 0.95, 1.00),
    marge_ebitda=Threshold(-0.05, 0.00, 0.08, 0.15),
    marge_nette=Threshold(-0.05, -0.02, 0.03, 0.08),
    roce=Threshold(0.00, 0.02, 0.10, 0.20),
    roe=Threshold(0.00, 0.03, 0.12, 0.25),
    dette_nette_ebitda=Threshold(-10.0, -2.0, 1.5, 3.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 3.0, 10.0, 50.0),
    autonomie_financiere=Threshold(0.30, 0.50, 0.80, 0.95),
    bfr_jours_ca=Threshold(-60, -20, 30, 90, higher_is_better=False),
    ca_par_employe=Threshold(30_000, 45_000, 75_000, 120_000),
    charges_perso_ca=Threshold(0.50, 0.60, 0.75, 0.85, higher_is_better=False),
    ev_ebitda_multiple=0,  # N/A : pas de valo marché pour une asso
    ev_ca_multiple=0,
    vocab_secteur="association", vocab_peers="associations comparables",
    key_drivers=("subventions publiques", "dons", "fiscalité OSBL", "bénévolat"),
    weight_rentabilite=0.20, weight_solidite=0.40, weight_efficacite=0.10, weight_croissance=0.15,
    weight_bodacc=0.15,
)

# ──────────────────────────────────────────────────────────────────────────────
# SERVICES PERSONNE / LOISIRS (3)
# ──────────────────────────────────────────────────────────────────────────────

BEAUTE_BIEN_ETRE = SectorProfile(
    code="beaute_bien_etre",
    name="Beauté / bien-être (coiffure, esthétique, spa)",
    naf_prefixes=("96.02",),
    description="Encaissement J+0, loyer/CA critique, produits + services, saisonnalité.",
    marge_brute=Threshold(0.55, 0.70, 0.85, 0.95),
    marge_ebitda=Threshold(0.05, 0.10, 0.20, 0.30),
    marge_nette=Threshold(0.00, 0.03, 0.12, 0.20),
    roce=Threshold(0.08, 0.15, 0.30, 0.55),
    roe=Threshold(0.06, 0.12, 0.25, 0.45),
    dette_nette_ebitda=Threshold(-2.0, 0, 2.0, 3.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 10.0, 30.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.55, 0.80),
    bfr_jours_ca=Threshold(-30, -10, 15, 35, higher_is_better=False),
    dso_jours=Threshold(0, 1, 5, 15, higher_is_better=False),
    ca_par_employe=Threshold(40_000, 55_000, 90_000, 140_000),
    charges_perso_ca=Threshold(0.30, 0.38, 0.50, 0.58, higher_is_better=False),
    ev_ebitda_multiple=4.5, ev_ca_multiple=0.6,
    vocab_secteur="salon de coiffure / institut de beauté",
    vocab_peers="salons comparables",
    key_drivers=("emplacement", "loyer/CA", "mix produits/services", "fidélité clientèle"),
)

SERVICES_PERSONNE = SectorProfile(
    code="services_personne",
    name="Services à la personne (ménage, garde, jardinage)",
    naf_prefixes=("81.2", "88.1"),
    description="Crédit d'impôt 50% client, saisonnalité, CCN ménage, chèque CESU.",
    marge_brute=Threshold(0.20, 0.28, 0.40, 0.55),
    marge_ebitda=Threshold(0.02, 0.05, 0.12, 0.20),
    marge_nette=Threshold(0.00, 0.01, 0.06, 0.12),
    roce=Threshold(0.06, 0.12, 0.25, 0.45),
    roe=Threshold(0.05, 0.10, 0.22, 0.40),
    dette_nette_ebitda=Threshold(-1.0, 0, 2.0, 3.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 10.0, 25.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-15, 5, 30, 60, higher_is_better=False),
    dso_jours=Threshold(5, 15, 40, 75, higher_is_better=False),
    ca_par_employe=Threshold(25_000, 35_000, 55_000, 85_000),
    charges_perso_ca=Threshold(0.60, 0.68, 0.78, 0.85, higher_is_better=False),
    ev_ebitda_multiple=5.0, ev_ca_multiple=0.5,
    vocab_secteur="organisme de services à la personne",
    vocab_peers="OSP comparables",
    key_drivers=("crédit d'impôt client", "saisonnalité", "CCN"),
)

SPORT_LOISIRS = SectorProfile(
    code="sport_loisirs",
    name="Sport / salles de fitness / loisirs",
    naf_prefixes=("93",),
    description="Abonnements récurrents, CAPEX équipements, saisonnalité, concurrence.",
    marge_brute=Threshold(0.55, 0.70, 0.85, 0.95),
    marge_ebitda=Threshold(0.10, 0.18, 0.30, 0.42),
    marge_nette=Threshold(0.02, 0.05, 0.15, 0.25),
    roce=Threshold(0.06, 0.10, 0.22, 0.35),
    roe=Threshold(0.05, 0.10, 0.22, 0.40),
    dette_nette_ebitda=Threshold(0, 1.5, 4.0, 5.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(-60, -30, 0, 30, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 120_000, 220_000, 400_000),
    charges_perso_ca=Threshold(0.25, 0.32, 0.45, 0.55, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=1.2,
    vocab_secteur="salle de sport / structure de loisirs",
    vocab_peers="salles comparables",
    key_drivers=("abonnés/MRR", "churn", "CAPEX équipement", "loyer/m²"),
)

# ──────────────────────────────────────────────────────────────────────────────
# IMMOBILIER (3)
# ──────────────────────────────────────────────────────────────────────────────

IMMO_PROMOTION = SectorProfile(
    code="immo_promotion",
    name="Promotion immobilière",
    naf_prefixes=("41.1",),
    description="BFR opération massif, dette spécifique par opération, cycles 2-4 ans.",
    marge_brute=Threshold(0.08, 0.15, 0.25, 0.40),
    marge_ebitda=Threshold(0.03, 0.08, 0.18, 0.30),
    marge_nette=Threshold(0.00, 0.03, 0.12, 0.22),
    roce=Threshold(0.05, 0.10, 0.25, 0.50),
    roe=Threshold(0.05, 0.12, 0.30, 0.60),
    dette_nette_ebitda=Threshold(0, 2.0, 6.0, 10.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.65),
    bfr_jours_ca=Threshold(30, 90, 270, 540, higher_is_better=False),
    ca_par_employe=Threshold(500_000, 1_000_000, 2_500_000, 5_000_000),
    charges_perso_ca=Threshold(0.02, 0.04, 0.10, 0.15, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=0.5,
    vocab_secteur="promoteur immobilier", vocab_peers="promoteurs comparables",
    key_drivers=("BFR opération", "portage foncier", "pré-commercialisation", "cycle 2-4 ans"),
)

IMMO_FONCIERE = SectorProfile(
    code="immo_fonciere",
    name="Foncière / location immobilière",
    naf_prefixes=("68.2",),
    description="LTV, rendement locatif, ROCE vs coût dette, vacance.",
    marge_brute=Threshold(0.70, 0.80, 0.90, 0.97),
    marge_ebitda=Threshold(0.55, 0.65, 0.80, 0.92),
    marge_nette=Threshold(0.10, 0.20, 0.40, 0.60),
    roce=Threshold(0.03, 0.05, 0.10, 0.18),
    roe=Threshold(0.04, 0.08, 0.15, 0.25),
    dette_nette_ebitda=Threshold(0, 4.0, 9.0, 14.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 5.0, 10.0),
    autonomie_financiere=Threshold(0.25, 0.35, 0.55, 0.75),
    bfr_jours_ca=Threshold(-30, -10, 20, 60, higher_is_better=False),
    ca_par_employe=Threshold(300_000, 600_000, 1_500_000, 3_000_000),
    charges_perso_ca=Threshold(0.02, 0.05, 0.12, 0.20, higher_is_better=False),
    ev_ebitda_multiple=12.0, ev_ca_multiple=8.0,
    vocab_secteur="foncière", vocab_peers="foncières comparables",
    key_drivers=("LTV", "rendement locatif", "vacance", "revalorisation actifs"),
)

IMMO_TRANSACTION = SectorProfile(
    code="immo_transaction",
    name="Transaction / gestion immobilière (agences, syndic)",
    naf_prefixes=("68.3",),
    description="Commission transaction, encaissement mandataire, volume/ticket.",
    marge_brute=Threshold(0.50, 0.65, 0.80, 0.92),
    marge_ebitda=Threshold(0.08, 0.15, 0.25, 0.40),
    marge_nette=Threshold(0.03, 0.08, 0.18, 0.30),
    roce=Threshold(0.10, 0.20, 0.40, 0.70),
    roe=Threshold(0.08, 0.15, 0.30, 0.55),
    dette_nette_ebitda=Threshold(-3.0, -1.0, 1.5, 3.0, higher_is_better=False),
    couverture_interets=Threshold(3.0, 5.0, 15.0, 50.0),
    autonomie_financiere=Threshold(0.20, 0.35, 0.60, 0.85),
    bfr_jours_ca=Threshold(-60, -30, 15, 60, higher_is_better=False),
    dso_jours=Threshold(10, 25, 60, 100, higher_is_better=False),
    ca_par_employe=Threshold(80_000, 120_000, 220_000, 400_000),
    charges_perso_ca=Threshold(0.35, 0.45, 0.60, 0.70, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=1.3,
    vocab_secteur="agence immobilière / syndic", vocab_peers="agences comparables",
    key_drivers=("volume transactions", "commission %", "portefeuille syndic", "cycle marché"),
)

# ──────────────────────────────────────────────────────────────────────────────
# FINANCE / HOLDINGS (1)
# ──────────────────────────────────────────────────────────────────────────────

UTILITY_ENERGIE = SectorProfile(
    code="utility_energie",
    name="Utility (énergie, eau, assainissement, déchets)",
    naf_prefixes=("35", "36", "37", "38", "39"),
    description=(
        "Production/transport/distribution d'électricité et gaz, "
        "captage/traitement/distribution d'eau, collecte et traitement "
        "des eaux usées, gestion des déchets. Capital-intensive, "
        "régulation tarifaire, cash flows cycliques mais relativement "
        "stables, dette LT élevée normale, BFR souvent négatif "
        "(encaissements avant paiements fournisseurs)."
    ),
    # Marges : capital lourd mais pricing régulé, donc marges modérées
    # pour EBITDA (opex vs capex), marge nette faible (amortissements +
    # charges financières importantes).
    marge_brute=Threshold(0.20, 0.35, 0.55, 0.75),
    marge_ebitda=Threshold(0.08, 0.15, 0.28, 0.40),
    marge_nette=Threshold(0.00, 0.03, 0.10, 0.18),
    # ROE/ROCE modestes — base d'actifs énorme + régulation
    roce=Threshold(0.02, 0.05, 0.12, 0.20),
    roe=Threshold(0.00, 0.05, 0.15, 0.25),
    # Levier structurellement élevé (grandes utilities FR : EDF ~4-6x, Engie ~3x)
    dette_nette_ebitda=Threshold(0, 2.0, 4.5, 7.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 2.5, 6.0, 15.0),
    autonomie_financiere=Threshold(0.10, 0.20, 0.40, 0.60),
    # BFR souvent négatif pour les utilities (encaissements mensuels > dettes
    # fournisseurs long) — donc bornes décalées côté négatif
    bfr_jours_ca=Threshold(-120, -30, 20, 60, higher_is_better=False),
    dso_jours=Threshold(30, 45, 75, 110, higher_is_better=False),
    dpo_jours=Threshold(30, 50, 90, 130),
    rotation_stocks=Threshold(5, 10, 25, 60),
    # CA/employé élevé — secteur capital-intensive (peu de personnel relatif)
    ca_par_employe=Threshold(250_000, 400_000, 800_000, 1_500_000),
    charges_perso_ca=Threshold(0.08, 0.15, 0.30, 0.45, higher_is_better=False),
    ev_ebitda_multiple=7.5, ev_ca_multiple=1.8,
    vocab_secteur="utility / réseau d'infrastructure",
    vocab_peers="utilities comparables",
    key_drivers=(
        "RAB / base d'actifs régulée",
        "coût du capital (WACC régulé)",
        "prix de marché de l'énergie",
        "cadre tarifaire régulateur",
        "intensité capitalistique (CAPEX)",
    ),
)

HOLDINGS_FINANCE = SectorProfile(
    code="holdings_finance",
    name="Holdings, courtage assurance, gestion d'actifs",
    naf_prefixes=("64", "65.2", "66", "70.10"),
    description="Dividendes intra-groupe, commissions, dette acquisition (LBO), fiscalité spécifique.",
    marge_brute=Threshold(0.60, 0.75, 0.90, 1.00),
    marge_ebitda=Threshold(0.20, 0.30, 0.50, 0.70),
    marge_nette=Threshold(0.10, 0.20, 0.40, 0.65),
    roce=Threshold(0.05, 0.10, 0.25, 0.50),
    roe=Threshold(0.05, 0.10, 0.25, 0.50),
    dette_nette_ebitda=Threshold(0, 2.0, 5.0, 8.0, higher_is_better=False),
    couverture_interets=Threshold(1.5, 3.0, 8.0, 20.0),
    autonomie_financiere=Threshold(0.20, 0.30, 0.55, 0.85),
    bfr_jours_ca=Threshold(-60, -20, 30, 90, higher_is_better=False),
    ca_par_employe=Threshold(200_000, 400_000, 800_000, 2_000_000),
    charges_perso_ca=Threshold(0.15, 0.22, 0.40, 0.55, higher_is_better=False),
    ev_ebitda_multiple=8.0, ev_ca_multiple=2.0,
    vocab_secteur="holding / courtier", vocab_peers="holdings / courtiers comparables",
    key_drivers=("dividendes reçus", "dette LBO", "commissions", "valorisation participations"),
)

# ──────────────────────────────────────────────────────────────────────────────
# GÉNÉRIQUES FALLBACK
# ──────────────────────────────────────────────────────────────────────────────

GENERIC_COMMERCE = SectorProfile(
    code="generic_commerce",
    name="Commerce (générique)",
    naf_prefixes=("45", "46", "47"),
    description="Profil générique commerce quand aucun sous-secteur précis n'est identifié.",
    marge_brute=Threshold(0.15, 0.25, 0.45, 0.65),
    marge_ebitda=Threshold(0.03, 0.06, 0.12, 0.20),
    marge_nette=Threshold(0.00, 0.02, 0.07, 0.12),
    roce=Threshold(0.06, 0.10, 0.20, 0.35),
    roe=Threshold(0.05, 0.10, 0.20, 0.35),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(0, 20, 60, 100, higher_is_better=False),
    dso_jours=Threshold(20, 40, 70, 100, higher_is_better=False),
    rotation_stocks=Threshold(4, 8, 20, 40),
    ca_par_employe=Threshold(150_000, 250_000, 450_000, 800_000),
    charges_perso_ca=Threshold(0.10, 0.15, 0.28, 0.38, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=0.5,
    vocab_secteur="commerçant", vocab_peers="commerces comparables",
)

GENERIC_SERVICES = SectorProfile(
    code="generic_services",
    name="Services (générique)",
    naf_prefixes=("70", "71", "72", "73", "74", "75", "77", "78", "79", "80", "82"),
    description="Profil générique services quand aucun sous-secteur précis n'est identifié.",
    marge_brute=Threshold(0.40, 0.55, 0.75, 0.90),
    marge_ebitda=Threshold(0.05, 0.10, 0.20, 0.32),
    marge_nette=Threshold(0.02, 0.05, 0.13, 0.22),
    roce=Threshold(0.08, 0.12, 0.25, 0.45),
    roe=Threshold(0.06, 0.12, 0.25, 0.45),
    dette_nette_ebitda=Threshold(-2.0, 0, 2.0, 3.5, higher_is_better=False),
    couverture_interets=Threshold(2.5, 4.0, 10.0, 30.0),
    autonomie_financiere=Threshold(0.20, 0.35, 0.60, 0.85),
    bfr_jours_ca=Threshold(0, 30, 75, 120, higher_is_better=False),
    dso_jours=Threshold(30, 50, 80, 110, higher_is_better=False),
    ca_par_employe=Threshold(70_000, 110_000, 220_000, 400_000),
    charges_perso_ca=Threshold(0.30, 0.42, 0.65, 0.80, higher_is_better=False),
    ev_ebitda_multiple=6.0, ev_ca_multiple=1.0,
    vocab_secteur="prestataire de services", vocab_peers="sociétés de services comparables",
)

GENERIC_INDUSTRY = SectorProfile(
    code="generic_industry",
    name="Industrie (générique)",
    naf_prefixes=("10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
                  "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"),
    description="Profil générique industrie quand aucun sous-secteur précis n'est identifié.",
    marge_brute=Threshold(0.15, 0.25, 0.40, 0.60),
    marge_ebitda=Threshold(0.04, 0.08, 0.18, 0.28),
    marge_nette=Threshold(0.00, 0.03, 0.10, 0.18),
    roce=Threshold(0.05, 0.08, 0.18, 0.30),
    roe=Threshold(0.04, 0.08, 0.18, 0.30),
    dette_nette_ebitda=Threshold(0, 1.0, 3.0, 4.5, higher_is_better=False),
    couverture_interets=Threshold(2.0, 3.5, 8.0, 20.0),
    autonomie_financiere=Threshold(0.15, 0.25, 0.45, 0.70),
    bfr_jours_ca=Threshold(0, 30, 80, 130, higher_is_better=False),
    dso_jours=Threshold(30, 50, 80, 110, higher_is_better=False),
    rotation_stocks=Threshold(3, 5, 12, 20),
    ca_par_employe=Threshold(120_000, 200_000, 400_000, 700_000),
    charges_perso_ca=Threshold(0.15, 0.25, 0.42, 0.55, higher_is_better=False),
    ev_ebitda_multiple=5.5, ev_ca_multiple=0.7,
    vocab_secteur="industriel", vocab_peers="industriels comparables",
)


# ==============================================================================
# Registre global
# ==============================================================================

PROFILES: dict[str, SectorProfile] = {
    p.code: p for p in [
        # Industrie (5)
        INDUSTRY_HEAVY, INDUSTRY_LIGHT, INDUSTRY_PROCESS, INDUSTRY_ASSEMBLY, INDUSTRY_AGRI,
        # BTP + ingénierie (4)
        BTP_HEAVY, BTP_LIGHT, BTP_PUBLIC, ARCHITECTURE_ENG,
        # Commerce (8)
        COMMERCE_WHOLESALE_FOOD, COMMERCE_WHOLESALE_NONFOOD,
        COMMERCE_RETAIL_FOOD, COMMERCE_RETAIL_SPEC, COMMERCE_ECOMMERCE,
        COMMERCE_AUTO, COMMERCE_FUEL, COMMERCE_PHARMA,
        # Services B2B (6)
        CABINET_EXPERTISE, CONSEIL_STRATEGIC, AGENCE_COMM, ESN_SSII, BPO_CALL, INTERIM_RH,
        # Tech / Software (4)
        SAAS_B2B, DEEP_TECH, CLOUD_HOSTING, GAMING_MEDIA,
        # Télécoms / Média (2)
        TELECOM_ISP, EDITION_PRESSE,
        # Hôtellerie / restauration (5)
        RESTAURATION_INDEP, RESTAURATION_CHAINE, DEBITS_BOISSONS, TRAITEUR_EVENT, HOTELLERIE,
        # Transport / logistique (4)
        TRANSPORT_TRM, TRANSPORT_VOYAGEURS, TAXI_VTC, LOGISTIQUE_ENTREPOT,
        # Santé / enseignement / social (5)
        SANTE_LIBERAL, EHPAD_SENIORS, CRECHE, ENSEIGNEMENT_PRIVE, ASSOCIATION,
        # Services personne / loisirs (3)
        BEAUTE_BIEN_ETRE, SERVICES_PERSONNE, SPORT_LOISIRS,
        # Immobilier (3)
        IMMO_PROMOTION, IMMO_FONCIERE, IMMO_TRANSACTION,
        # Finance / Holdings (1)
        HOLDINGS_FINANCE,
        # Utilities / Énergie (1)
        UTILITY_ENERGIE,
        # Génériques
        GENERIC_COMMERCE, GENERIC_SERVICES, GENERIC_INDUSTRY,
    ]
}


def resolve_profile(code_naf: str | None) -> SectorProfile:
    """Matche un code NAF (ex: '69.20Z', '47.73Z', '62.01Z') au profil le plus
    précis. Le matching se fait sur le prefix le plus long.
    Fallback : générique services / commerce / industrie selon section NAF.
    """
    if not code_naf:
        return GENERIC_SERVICES

    # Normalise : "69.20Z" → comparable aux prefixes "69.20" et "69"
    naf_upper = code_naf.upper().strip()

    # Cherche le prefix le plus long qui matche
    best: tuple[int, SectorProfile] | None = None
    for profile in PROFILES.values():
        for prefix in profile.naf_prefixes:
            if naf_upper.startswith(prefix.upper()):
                plen = len(prefix)
                if best is None or plen > best[0]:
                    best = (plen, profile)

    if best is not None:
        return best[1]

    # Fallback section NAF (1er chiffre)
    prefix2 = naf_upper[:2]
    try:
        n = int(prefix2)
    except ValueError:
        return GENERIC_SERVICES

    # 10-33 = industries de transformation. Les 35-39 (utilities) sont
    # désormais captées par UTILITY_ENERGIE via prefix match en amont, donc
    # ce fallback n'est plus déclenché pour les utilities.
    if 10 <= n <= 33:
        return GENERIC_INDUSTRY
    if 45 <= n <= 47:
        return GENERIC_COMMERCE
    return GENERIC_SERVICES


def list_all_profiles() -> list[SectorProfile]:
    """Renvoie la liste de tous les profils enregistrés."""
    return list(PROFILES.values())


def count_profiles() -> int:
    """Renvoie le nombre de profils (hors génériques)."""
    return len([p for p in PROFILES.values() if not p.code.startswith("generic_")])
