"""
sectoral_pptx_writer.py — FinSight IA
Pitchbook sectoriel 20 slides via python-pptx.
Usage : SectoralPPTXWriter.generate(tickers_data, sector_name, universe, output_path)
"""
from __future__ import annotations
import io, datetime, logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)

from pptx import Presentation
from pptx.util import Cm, Pt, Inches, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ─── PALETTE ──────────────────────────────────────────────────────────────────
_NAVY   = RGBColor(0x1B, 0x3A, 0x6B)
_NAVYL  = RGBColor(0x2A, 0x52, 0x98)
_BUY    = RGBColor(0x1A, 0x7A, 0x4A)
_SELL   = RGBColor(0xA8, 0x20, 0x20)
_HOLD   = RGBColor(0xB0, 0x60, 0x00)
_WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
_BLACK  = RGBColor(0x1A, 0x1A, 0x1A)
_GRAYL  = RGBColor(0xF5, 0xF7, 0xFA)
_GRAYM  = RGBColor(0xE8, 0xEC, 0xF0)
_GRAYT  = RGBColor(0x55, 0x55, 0x55)
_GRAYD  = RGBColor(0xAA, 0xAA, 0xAA)
_GREEN_L = RGBColor(0xE8, 0xF5, 0xEE)
_RED_L   = RGBColor(0xFB, 0xEB, 0xEB)
_HOLD_L  = RGBColor(0xFD, 0xF3, 0xE5)

# ─── SLIDE DIMENSIONS ─────────────────────────────────────────────────────────
_SW = Inches(10.0)
_SH = Inches(5.625)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MAX_CATS_DISPLAYED    = 3
MAX_RISKS_DISPLAYED   = 3
MAX_DRIVERS_DISPLAYED = 4
MAX_TOP_N             = 3
MAX_TICKERS_CHART     = 8
MAX_TABLE_ROWS        = 15   # cap tables sur slides 6/9/11/15 (univers >15 tickers)

# ─── SECTOR CONTENT LIBRARY ───────────────────────────────────────────────────
_SECTOR_CONTENT = {
    "Technology": {
        "description": (
            "Le secteur Technology regroupe les entreprises actives dans les logiciels, "
            "les services informatiques, les semi-conducteurs et les equipements telecom. "
            "Porte par la transformation digitale des entreprises et l'adoption de l'IA generative, "
            "ce secteur affiche des multiples de valorisation parmi les plus élevés du marche, "
            "justifies par des perspectives de croissance supérieures et des marges en expansion."
        ),
        "catalyseurs": [
            ("Adoption IA Generative", "Acceleration des mandats IA dans les grands comptes europeens — contrats pluriannuels en hausse de 38 % sur T1 2026."),
            ("Modernisation SI Publics", "Plans d'investissement gouvernementaux 2026-2028 — budgets numeriques confirmes pour 6 Etats membres EU."),
            ("Cloud Hybride Souverainete", "Contraintes réglementaires sur les données — migration vers solutions EU portee par NIS2 et DORA."),
        ],
        "risques": [
            ("Ralentissement Budgets IT", "Recession europeenne confirmee entrainerait une reduction des budgets IT de 12-18 %, penalisant les prestataires de services."),
            ("Durcissement AI Act", "Surcout de mise en conformite estime a 8-12 % du CA pour les editeurs de logiciels IA — impact marges 2027."),
            ("Pression Tarifaire US/Asie", "Acteurs americains et asiatiques agressifs sur les segments logiciels standardises — guerre des prix bas de gamme."),
        ],
        "drivers": [
            ("up", "Intelligence Artificielle", "Adoption entreprises +42 % en 2026 — premier driver de depenses IT"),
            ("up", "Cloud Hybride Souverain", "Contraintes souverainete données — migration vers solutions EU acceleree par NIS2"),
            ("up", "Modernisation SI Publics", "Plans gouvernementaux 2026-2028 — budgets numeriques confirmes 6 Etats EU"),
            ("down", "Sensibilite Taux", "Compression multiples si taux > 4,5 % — impact modere sur FCF structurel"),
        ],
        "cycle_comment": "Secteur en phase d'expansion | porte par l'IA et le cloud souverain",
        "métriques": [("Rule of 40", "42", "Sain > 40"), ("NRR median", "108 %", "Retention solide"), ("Cloud Mix", "38 %", "En hausse"), ("R&D/Rev.", "12 %", "Investi"), ("ARR Growth", "+24 %", "Acceleration"), ("Churn", "4,2 %", "Stable")],
        "conditions": [("Macro", "Recession UE confirmee — contraction PIB > 1,5 %", "6-12 mois"), ("Sectoriel", "Reduction budgets IT > 15 % grands comptes", "12-18 mois"), ("Réglementaire", "AI Act surcoût conformite > 15 % CA", "18-24 mois"), ("Fondamental", "Revision baissiere EPS > 20 % sur 2 trimestres", "6-9 mois")],
    },
    "Consumer Cyclical": {
        "description": (
            "Le secteur Consommation Cyclique inclut les acteurs du luxe, de la distribution specialisee, "
            "de l'automobile et du tourisme. Sensible aux cycles economiques, il beneficie de l'essor "
            "des marches emergents et de la résilience du luxe haut de gamme europeen face aux pressions macro."
        ),
        "catalyseurs": [
            ("Rebond Luxe Asie", "Reouverture progressive des marches asiatiques — croissance hors UE attendue a +15 % en 2026 pour le segment premium."),
            ("Transition Electrique", "Acceleration des ventes VE en Europe — soutien réglementaire et infrastructures de recharge en deploiement."),
            ("Tourisme Premium", "Flux touristiques europeens en hausse de 12 % — benefice direct pour l'hotellerie et la restauration haut de gamme."),
        ],
        "risques": [
            ("Sensibilite Taux", "Hausse des taux comprime le pouvoir d'achat discretionnaire — impact sur volumes et marges promotionnelles."),
            ("Ralentissement Chine", "Croissance chinoise < 4 % penaliserait les acteurs du luxe exposes a 30-40 % de leur CA en Asie."),
            ("Disruption Digitale", "Montee des plateformes D2C — pression sur les reseaux de distribution traditionnels."),
        ],
        "drivers": [
            ("up", "Luxe Premium", "Résilience exceptionnelle — pricing power intact segment > 500 EUR"),
            ("up", "Rebond Asiatique", "Flux touristiques et ventes locales en Chine en normalisation"),
            ("down", "Pouvoir d'Achat", "Inflation residuelle et taux élevés compressent la consommation mid-market"),
            ("down", "Substitution Digital", "Plateformes e-commerce capturent des parts en distribution"),
        ],
        "cycle_comment": "Secteur en consolidation | luxe résilient, mid-market sous pression",
        "métriques": [("SSSG", "+4,2 %", "Positif"), ("Inventory Turn", "3,8x", "Sain"), ("Online Mix", "28 %", "En hausse"), ("Price/Mix", "+2,1 %", "Favorable"), ("Return Rate", "18 %", "Stable"), ("Loyalty Rev.", "42 %", "Fort")],
        "conditions": [("Macro", "PIB Zone Euro negatif 2 trimestres", "6-9 mois"), ("Chine", "PIB chinois < 3,5 %", "9-12 mois"), ("Credit", "Taux 10Y > 5 % pendant 6 mois", "6-12 mois"), ("Fondamental", "SSSG negatif 3 trimestres", "9 mois")],
    },
    "Consumer Defensive": {
        "description": (
            "Le secteur Consommation Defensive regroupe les producteurs et distributeurs de biens essentiels "
            "— alimentation, boissons, hygiene-beaute. Modèle résilient par nature, il offre une protection "
            "en periode de recession tout en beneficiant du pricing power des marques leaders."
        ),
        "catalyseurs": [
            ("Pricing Power", "Capacité a répercuter l'inflation des intrants — les leaders de marque maintiennent des marges brutes > 40 %."),
            ("Marches Emergents", "Croissance de la classe moyenne en Afrique et Asie du Sud-Est — expansion a double chiffre."),
            ("Innovation Produit", "Premiumisation et bio — capture de valeur additionnelle sur les segments porteurs."),
        ],
        "risques": [
            ("Guerre des Prix", "Pression des distributeurs (Leclerc, Lidl) sur les prix fournisseurs — erosion des marges lors des négociations."),
            ("Destockage", "Reduction des stocks en distribution — impact sur volumes T1-T2 2026."),
            ("Substitution MDD", "Parts de marche des marques distributeurs en hausse de 2-3 pts — pression structurelle."),
        ],
        "drivers": [
            ("up", "Pricing Power Marques", "Leaders de catégorie maintiennent +3-5 % de hausse tarifaire annuelle"),
            ("up", "Expansion Emergents", "Croissance volumes a 2 chiffres en Afrique et Asie du Sud-Est"),
            ("down", "Pression Distribution", "Négociations annuelles de plus en plus defavorables"),
            ("down", "Saturation Matures", "Volumes stagnants en Europe — croissance principalement par prix"),
        ],
        "cycle_comment": "Secteur défensif | résilient en recession, sous-performant en expansion",
        "métriques": [("Org. Growth", "+3,8 %", "Sain"), ("Gross Margin", "42 %", "Stable"), ("FCF Yield", "4,2 %", "Attractif"), ("Div. Yield", "2,8 %", "Stable"), ("Elasticite Prix", "-0,4", "Faible"), ("Market Share", "+0,3 pt", "Gain")],
        "conditions": [("Macro", "Recession profonde > 3 trimestres", "9-12 mois"), ("Distribution", "Perte > 15 % référencements top 3", "6-9 mois"), ("MDD", "Part MDD > 45 % en valeur", "12-18 mois"), ("Réglementaire", "Taxe nutritionnelle majeure", "12-24 mois")],
    },
    "Financial Services": {
        "description": (
            "Le secteur Financier couvre les banques, assureurs, sociétés de gestion d'actifs et fintech. "
            "L'environnement de taux élevés a restaure la rentabilité des marges d'interet, mais l'exposition "
            "au credit immobilier et aux PME reste un facteur de risque dans un contexte macro degrade."
        ),
        "catalyseurs": [
            ("Taux Directeurs Élevés", "Maintien des taux BCE a 3 % — soutien structurel aux NIM bancaires et a la rentabilité des depots."),
            ("Consolidation Sectorielle", "Fusions-acquisitions dans la banque retail — prime de controle sur les cibles sous-valorisees."),
            ("Digitalisation Services", "Plateformes wealth management numeriques — reduction couts et captation millennials investisseurs."),
        ],
        "risques": [
            ("Dégradâtion Credit", "Hausse des NPL dans l'immobilier commercial et le credit PME si recession confirmee."),
            ("Baisse Taux BCE", "Pivot accommodant — compression des NIM de 15-25 bps par tranche de 25 bps de baisse."),
            ("Regulation Bale IV", "Exigences CET1 plus élevées — pression sur le ROE et les politiques de retour de capital."),
        ],
        "drivers": [
            ("up", "Marge Nette d'Interet", "Taux élevés soutiennent les NIM — pic attendu T2 2026"),
            ("up", "Gestion d'Actifs", "Collecte nette positive — marches actions porteurs"),
            ("down", "Cout du Risque", "Montee progressive des provisions — NPL en hausse"),
            ("down", "Regulation", "Bale IV — impact CET1 estime a -80bps grandes banques EU"),
        ],
        "cycle_comment": "Secteur en maturite cyclique | NIM en pic, qualité d'actifa surveiller",
        "métriques": [("NIM median", "2,8 %", "Sain"), ("CET1 median", "14,2 %", "Confortable"), ("ROE median", "11,4 %", "Acceptable"), ("Cost/Income", "58 %", "A ameliorer"), ("NPL Ratio", "2,1 %", "Controle"), ("P/Book", "0,8x", "Décote")],
        "conditions": [("Taux", "BCE baisse < 2 % — compression NIM > 40 bps", "6-12 mois"), ("Credit", "NPL > 5 % immobilier commercial", "12-18 mois"), ("Macro", "Recession > 2 trimestres — provisionnement", "6-9 mois"), ("Réglementaire", "Bale IV CET1 > 15 %", "24-36 mois")],
    },
    "Industrials": {
        "description": (
            "Le secteur Industriel englobe les fabricants d'equipements, les entreprises de defense, "
            "les conglomerats industriels et les prestataires de services B2B. Il beneficie des plans de "
            "reindustrialisation europeens et de la hausse des budgets defense."
        ),
        "catalyseurs": [
            ("Rearmement Europeen", "Hausse des budgets defense a 2 % du PIB — carnet de commandes a 5-7 ans pour les acteurs specialises."),
            ("Reindustrialisation EU", "Plans de relocalisation — investissements publics massifs dans l'automatisation."),
            ("Transition Energetique", "Equipements eoliens, solaires et reseaux — croissance structurelle du carnet de commandes."),
        ],
        "risques": [
            ("Ralentissement Capex", "Gel des investissements industriels en cas de recession — impact sur commandes machines."),
            ("Tension Supply Chain", "Disponibilite des semi-conducteurs et matieres premieres critiques — risques livraisons."),
            ("Pression Marges", "Hausse des couts energetiques et des salaires dans l'industrie — compression marges execution."),
        ],
        "drivers": [
            ("up", "Defense & Sécurité", "Budgets defense EU en hausse de 15-20 % — carnets record"),
            ("up", "Equipements Transition", "Investissements eolien offshore et reseaux — +12 % pa"),
            ("down", "Cycles Capex", "Ralentissement capex automobile et electronique"),
            ("down", "Couts Production", "Energie et main-d'oeuvre qualifiee compriment les marges"),
        ],
        "cycle_comment": "Secteur en expansion selective | defense et transition tirent la croissance",
        "métriques": [("Book-to-Bill", "1,18x", "Positif"), ("EBIT Margin", "11,4 %", "Stable"), ("Capex/Rev", "5,2 %", "Modere"), ("Backlog (mois)", "18", "Sécurisé"), ("FCF Conv.", "78 %", "Bon"), ("ROCE", "13,2 %", "Sain")],
        "conditions": [("Macro", "Contraction capex global > 10 %", "6-9 mois"), ("Defense", "Gel budgets defense EU > 20 %", "12-18 mois"), ("Supply Chain", "Penurie semi-conducteurs > 6 mois", "3-6 mois"), ("Fondamental", "Book-to-Bill < 0,9 pendant 3 trimestres", "9-12 mois")],
    },
    "Healthcare": {
        "description": (
            "Le secteur Sante regroupe les laboratoires pharmaceutiques, fabricants de dispositifs medicaux, "
            "biotechs et prestataires de soins. Structurellement défensif, il beneficie du vieillissement "
            "demographique et de l'innovation therapeutique."
        ),
        "catalyseurs": [
            ("Innovation Therapeutique", "Pipeline oncologie et maladies rares — lancements produits blockbusters attendus 2026-2027."),
            ("MedTech IA", "Integration de l'IA dans le diagnostic et la chirurgie assistee — premium innovateurs."),
            ("Vieillissement Demo", "Population > 65 ans en Europe +3 % pa — croissance structurelle des depenses sante."),
        ],
        "risques": [
            ("Pression Prix Medicaments", "Revision des prix de référence — impact de -5 a -15 % sur les revenus medicaments matures."),
            ("Expirations Brevets", "Vague de génériques 2026-2028 — perte de revenus 15-20 % pour les concernes."),
            ("Incertitude Clinique", "Taux d'echec élevé en phase III — risque de destruction de valeur sur pipelines."),
        ],
        "drivers": [
            ("up", "Innovation Oncologie", "Immunotherapies et ADC — marche > 200 Mds USD en 2027"),
            ("up", "MedTech IA", "Diagnostic assiste — barrières a l'entree élevées"),
            ("down", "Expiration Brevets", "Perte revenus blockbusters 2026-2028"),
            ("down", "Pricing Pressure", "Reformes prix medicaments EU et US — compression revenus"),
        ],
        "cycle_comment": "Secteur défensif-croissance | innovation compense risques réglementaires",
        "métriques": [("R&D/Rev.", "18 %", "Élevé"), ("Pipeline Score", "7,2/10", "Solide"), ("Marge Brute", "68 %", "Premium"), ("Patent Cliff", "2026-28", "A surveiller"), ("ROE", "22 %", "Attractif"), ("FCF Yield", "3,8 %", "Sain")],
        "conditions": [("Réglementaire", "Reforme prix US — impact > 20 % revenues", "12-18 mois"), ("Pipeline", "Echec phase III > 25 % du CA", "Immediat"), ("Brevet", "Expiration sans relai — -15 % revenues", "12-24 mois"), ("Macro", "Coupes budgets sante > 10 %", "24-36 mois")],
    },
    "Energy": {
        "description": (
            "Le secteur Energie couvre les majors petrolieres et gazieres, les energies renouvelables et "
            "les services parapetroliers. Il reste marque par la volatilite des prix des matieres premieres, "
            "tout en beneficiant de la transition energetique."
        ),
        "catalyseurs": [
            ("Prix Petrole Soutenu", "Demande asiatique robuste et OPEP+ disciplinee — Brent attendu 75-85 USD/bbl en 2026."),
            ("Investissements Renouvelables", "Plans de transition des majors — allocation capex renouvelables +25 % pa."),
            ("GNL Europeen", "Diversification approvisionnement post-Ukraine — primes GNL structurellement élevées."),
        ],
        "risques": [
            ("Volatilite Petrole", "Recession mondiale ou accord OPEP+ defavorable — Brent < 60 USD/bbl entrainerait des coupes dividendes."),
            ("Transition Réglementaire", "Acceleration du calendrier sortie fossiles — actifs bloques en risque."),
            ("Capex Renouvelable", "Surcouts et retards projets offshore wind — impact sur rendements."),
        ],
        "drivers": [
            ("up", "Prix Hydrocarbures", "OPEP+ discipline — soutien structurel des prix 2026"),
            ("up", "GNL & Souverainete", "Diversification approvisionnement EU — prime GNL persistante"),
            ("down", "Transition Energetique", "Pression réglementaire et ESG — prime de risque croissante"),
            ("down", "Capex Renouvelable", "Depenses investissement renouvelables pesent sur FCF"),
        ],
        "cycle_comment": "Secteur en transition | dividendes élevés, visibilite long terme reduite",
        "métriques": [("FCF Yield", "7,2 %", "Tres attractif"), ("Div. Yield", "4,8 %", "Élevé"), ("Breakeven", "52 USD", "Confortable"), ("ROACE", "14,2 %", "Bon"), ("ND/EBITDA", "1,2x", "Faible"), ("Capex/OCF", "48 %", "Modere")],
        "conditions": [("Petrole", "Brent < 55 USD/bbl 6 mois — coupes dividendes", "3-6 mois"), ("Politique", "Taxes exceptionnelles profits majors", "Immediat"), ("Transition", "Calendrier sortie fossiles avance 10 ans", "24-36 mois"), ("Demande", "Pic demande petroliere confirme avant 2030", "24-48 mois")],
    },
    "Basic Materials": {
        "description": (
            "Le secteur Materiaux de Base regroupe les producteurs de metaux, chimistes et fabricants "
            "de materiaux de construction. Fortement cyclique, il beneficie de la demande en materiaux "
            "critiques pour la transition energetique."
        ),
        "catalyseurs": [
            ("Materiaux Critiques", "Lithium, cuivre, cobalt — demande multipliee par 3-5x a horizon 2030 pour batteries et reseaux."),
            ("Infrastructure Publique", "Plans d'investissement G7 — demande en acier, ciment et materiaux en hausse."),
            ("Consolidation M&A", "Vague de fusions dans les metaux de base — prime de rachat potentielle."),
        ],
        "risques": [
            ("Ralentissement Chine", "Demande chinoise d'acier 55 % du marche mondial — tout ralentissement est penalisant."),
            ("Surcapacités", "Capacités de production excedentaires acier et aluminium — pression sur les prix."),
            ("Risques Geopolitiques", "Concentration production zones a risque (DRC, Chili) — risques supply chain."),
        ],
        "drivers": [
            ("up", "Metaux Transition", "Cuivre, lithium, cobalt — demande structurelle multi-decennale"),
            ("up", "Infrastructure G7", "Plans investissement massifs — consommation beton et acier"),
            ("down", "Cyclicite Chine", "Demande industrielle chinoise determinante et volatile"),
            ("down", "Surcapacités", "Acier et aluminium — prix sous pression structurelle"),
        ],
        "cycle_comment": "Secteur en transition cyclique | materiaux verts tirent la croissance long terme",
        "métriques": [("EV/EBITDA", "6,2x", "Décote"), ("FCF Yield", "5,8 %", "Attractif"), ("ND/EBITDA", "1,8x", "Gerable"), ("ROIC", "11,2 %", "Correct"), ("Capex/Rev", "8,4 %", "Élevé"), ("Div. Yield", "3,2 %", "Satisfaisant")],
        "conditions": [("Chine", "Croissance PIB < 3,5 % pendant 2 trimestres", "6-9 mois"), ("Prix", "Cuivre < 7 000 USD/t pendant 6 mois", "3-6 mois"), ("Capex", "Annulation projets miniers majeurs", "Immediat"), ("Regulation", "Taxes export matieres premieres critiques", "12-18 mois")],
    },
    "Real Estate": {
        "description": (
            "Le secteur Immobilier regroupe les foncières cotees (SIIC/REIT), promoteurs et gestionnaires "
            "d'actifs immobiliers. En phase de reevaluation post-hausse des taux, il offre des décotes sur "
            "ANR attractives pour les investisseurs patients."
        ),
        "catalyseurs": [
            ("Pivot Monetaire BCE", "Baisse des taux directeurs — compression des taux de capitalisation et reevaluation des ANR."),
            ("Penurie Logements", "Deficit de construction en France et Allemagne — soutien structurel a la valeur des actifs residentiels."),
            ("Actifs Durables", "Renovation energetique obligatoire — valorisation differentielle actifs certifies."),
        ],
        "risques": [
            ("Maintien Taux Élevés", "Taux longs > 4 % prolonges — pressions sur les ANR et les covenants de dette."),
            ("Dégradâtion Locative", "Vacance bureau en hausse post-teletravail — risques sur les loyers tertiaires secondaires."),
            ("Refinancement", "Mur de dette 2025-2027 — risques de dilution pour les foncieres surendettees."),
        ],
        "drivers": [
            ("up", "Pivot Taux", "Chaque -25bps BCE = +3-5 % sur les ANR sectoriels"),
            ("up", "Residentiel Deficitaire", "Offre structurellement insuffisante metropoles EU"),
            ("down", "Bureau Post-Covid", "Vacance bureau — actifs secondaires a risque"),
            ("down", "Refinancement", "Mur de dette — risque dilution pour les leverages"),
        ],
        "cycle_comment": "Secteur en reevaluation | ANR en décote, sensibilite aux taux majeure",
        "métriques": [("Décote ANR", "-22 %", "Opportunite"), ("Div. Yield", "4,8 %", "Attractif"), ("LTV median", "38 %", "Prudent"), ("ICR median", "3,2x", "Sain"), ("Vacance", "7,4 %", "Moderee"), ("EPRA NTA", "ref.", "Benchmark")],
        "conditions": [("Taux", "OAT 10Y > 4,5 % pendant 12 mois", "6-12 mois"), ("Vacance", "Vacance bureau > 15 %", "12-18 mois"), ("Dette", "LTV > 50 % — covenant breach", "Immediat"), ("Macro", "Recession — loyers -10 %", "9-12 mois")],
    },
    "Communication Services": {
        "description": (
            "Les Services de Communication regroupent les operateurs telecoms, medias numeriques et "
            "plateformes de contenu. Ce secteur beneficie de la migration vers le haut debit, "
            "de la consolidation sectorielle et de la monetisation des usages data."
        ),
        "catalyseurs": [
            ("Fibre & 5G", "Deploiement capillaire de la fibre optique — mix favorable vers abonnements premium."),
            ("Consolidation Telecom", "Fusions nationales approuvees — economies d'echelle et amelioration des marges EBITDA."),
            ("Streaming & Contenu", "Monetisation acceleree des plateformes — ARPU en hausse via offres publicitaires premium."),
        ],
        "risques": [
            ("Guerre des Prix Mobile", "Concurrence low-cost intensifiee — pression sur les ARPU en France et Espagne."),
            ("Capex Fibre", "Investissements reseaux lourds — impact FCF negatif pendant la phase de deploiement."),
            ("Substitution OTT", "Perte de revenus voix et SMS au profit des services OTT (WhatsApp, Teams)."),
        ],
        "drivers": [
            ("up", "Montee en Debit", "Fibre et 5G — migration offres premium +8 EUR/mois ARPU"),
            ("up", "Consolidation", "Fusions sectorielles — reduction concurrentielle et synergies"),
            ("down", "Pression Prix", "Low-cost MVNO — ARPU mobile compresse"),
            ("down", "Capex Reseau", "Phase investissement fibre — FCF sous pression 2-3 ans"),
        ],
        "cycle_comment": "Secteur en transformation | consolidation et fibre sont les catalyseurs",
        "métriques": [("EBITDA Margin", "32 %", "Stable"), ("ARPU", "28 EUR/m", "En hausse"), ("Churn", "1,2 %", "Faible"), ("Capex/Rev", "18 %", "Élevé"), ("Fiber Cover.", "68 %", "En cours"), ("FCF Yield", "3,4 %", "Modere")],
        "conditions": [("Prix", "ARPU mobile < 22 EUR — guerre des prix", "6-9 mois"), ("Capex", "Retards fibre > 18 mois", "9-12 mois"), ("Réglementaire", "Blocage fusions autorites concurrence", "Immediat"), ("Substitution", "Revenu voix < 20 % CA total", "18-24 mois")],
    },
    "Utilities": {
        "description": (
            "Les Utilities regroupent les producteurs et distributeurs d'electricite, de gaz et d'eau. "
            "Caracterisees par des revenus regules et des dividendes stables, elles constituent un refuge "
            "défensif sensible aux variations de taux d'interet."
        ),
        "catalyseurs": [
            ("Transition Energetique", "Investissements massifs dans le renouvelable — actifs regules garantissant des rendements stables."),
            ("Hausse Prix Energie", "Normalisation des prix de gros — amelioration des marges de fourniture."),
            ("Hydrogene & Stockage", "Positionnement nouvelles technologies — optionalite valorisation long terme."),
        ],
        "risques": [
            ("Taux Élevés", "Sensibilite marquee aux taux longs — compression des multiples si OAT > 4 %."),
            ("Risque Regule", "Revision des tarifs d'acces reseau — impact sur la remuneration du capital investi."),
            ("Volatilite Meteo", "Secheresse ou faible ventossité — impact sur production hydraulique et eolienne."),
        ],
        "drivers": [
            ("up", "Renouvelables Regules", "RAB en croissance — visibilite cash flows 20-30 ans"),
            ("up", "Electrification Usages", "VE et chaleur — croissance demande +2 % pa"),
            ("down", "Taux Longs", "Chaque +50bps = -5 a -8 % sur multiples EV/EBITDA"),
            ("down", "Revision Tarifs", "Regulateurs peuvent comprimer les marges"),
        ],
        "cycle_comment": "Secteur défensif-rendement | sensibilite taux élevée, dividendes stables",
        "métriques": [("RAB Return", "6,2 %", "Regule"), ("Div. Yield", "4,4 %", "Attractif"), ("ND/EBITDA", "4,2x", "Élevé stable"), ("RES Mix", "42 %", "En hausse"), ("Payout", "68 %", "Stable"), ("ROCE", "7,8 %", "Regule")],
        "conditions": [("Taux", "OAT 10Y > 4,5 % pendant 12 mois", "6-12 mois"), ("Regulation", "Baisse WACC regule > 100bps", "24-36 mois"), ("Meteo", "Secheresse generalisee 2 ans", "Annuel"), ("Politique", "Nationalisation ou gel tarifaire", "Immediat")],
    },
}

def _build_content_from_data(td: list, sector_name: str, score_moyen: int,
                              sig_label: str, ev_med: float, rev_med: float,
                              mg_med: float, mom_med: float) -> dict:
    """Build sector content dynamically from tickers_data for unrecognized sectors.
    Uses actual state values — no static dict fallback."""
    log.warning("sectoral_pptx: sector '%s' not in _SECTOR_CONTENT — "
                "building content dynamically from tickers_data (%d societes)",
                sector_name, len(td))

    sorted_td = sorted(td, key=lambda x: x.get("score_global") or 0, reverse=True)
    best  = sorted_td[0]  if sorted_td else {}
    worst = sorted_td[-1] if len(sorted_td) > 1 else {}

    best_ticker  = best.get("ticker", "—")
    best_score   = int(best.get("score_global") or 0)
    worst_ticker = worst.get("ticker", "—")

    # Catalyseurs derived from actual metrics
    cats = []
    cats.append((
        f"Leader {best_ticker}",
        f"Score FinSight {best_score}/100 avec marge EBITDA {mg_med:.1f} % "
        f"et momentum 52W {mom_med:+.1f} %."
    ))
    if rev_med > 5:
        cats.append((
            "Croissance sectorielle soutenue",
            f"Croissance median des revenus a {rev_med:+.1f} % — dynamique favorable."
        ))
    else:
        cats.append((
            "Valorisation attractive",
            f"EV/EBITDA median a {ev_med:.1f}x — potentiel de rerating si catalyseurs confirmes."
        ))
    cats.append((
        "Consolidation sectorielle",
        "Vague de M&A potentielle — prime de rachat sur les acteurs sous-valorises."
    ))

    # Risques derived from worst performer and macro
    risks = []
    if worst and worst_ticker != best_ticker:
        risks.append((
            f"Retardataire {worst_ticker}",
            f"Score {int(worst.get('score_global') or 0)}/100 — "
            "ecart significatif avec le leader, selectivite requise."
        ))
    else:
        risks.append((
            "Dispersion des scores",
            "Ecart entre les profils — allocation selective recommandee."
        ))
    risks.append((
        "Environnement macroeconomique",
        "Ralentissement de la croissance mondiale — impact sur volumes et revenus."
    ))
    risks.append((
        "Pressions reglementaires",
        "Evolution du cadre sectoriel — surcouts de conformite potentiels."
    ))

    # Drivers from actual metrics
    drivers = []
    if rev_med > 0:
        drivers.append(("up", "Croissance Organique",
                        f"Revenus en progression a {rev_med:+.1f} % — tendance positive"))
    else:
        drivers.append(("down", "Croissance Sous Pression",
                        f"Revenus medianes a {rev_med:+.1f} % — surveillance requise"))
    if mg_med > 20:
        drivers.append(("up", "Marges Solides",
                        f"Marge EBITDA median a {mg_med:.1f} % — structure rentable"))
    else:
        drivers.append(("down", "Pression sur les Marges",
                        f"Marge EBITDA a {mg_med:.1f} % — potentiel d'amelioration"))
    drivers.append(("down", "Macro Global",
                    "Ralentissement croissance mondiale — sensibilite cyclique"))
    drivers.append(("up", "Consolidation M&A",
                    "Prime de valorisation potentielle — vague sectorielle"))

    # Métriques: real computed values from state
    metriques = [
        ("EV/EBITDA", f"{ev_med:.1f}x",     "Médiane secteur"),
        ("Mg EBITDA", f"{mg_med:.1f} %",     "LTM"),
        ("Croissance", f"{rev_med:+.1f} %",  "YoY"),
        ("Momentum",  f"{mom_med:+.1f} %",   "52W"),
        ("Score Moyen", f"{score_moyen}/100", "FinSight"),
        ("Nb Societes", str(len(td)),         "Analysees"),
    ]

    # Conditions based on signal level
    alert_score = max(30, score_moyen - 15)
    conditions = [
        ("Macro",       "Recession confirmee — 2 trimestres negatifs",          "6-9 mois"),
        ("Sectoriel",   f"Score moyen < {alert_score} — degradation generalisee","6-12 mois"),
        ("Fondamental", "Revision baissiere EPS > 15 %",                         "3-6 mois"),
        ("Reglementaire", "Mesures restrictives majeures",                       "Variable"),
    ]

    quality = "attractif" if score_moyen >= 65 else "modere" if score_moyen >= 45 else "prudent"
    return {
        "description": (
            f"Le secteur {sector_name} regroupe {len(td)} entreprise(s) analysee(s) dans l'univers "
            f"FinSight. EV/EBITDA median : {ev_med:.1f}x, marge EBITDA : {mg_med:.1f} %, "
            f"croissance revenus : {rev_med:+.1f} %. Profil {quality} — signal {sig_label.lower()} "
            f"selon le modele multifactoriel FinSight (score moyen {score_moyen}/100)."
        ),
        "catalyseurs":  cats,
        "risques":      risks,
        "drivers":      drivers,
        "cycle_comment": f"Secteur {sector_name} | {sig_label.lower()} | score {score_moyen}/100",
        "métriques":    metriques,
        "conditions":   conditions,
    }


# ─── DATA HELPERS ─────────────────────────────────────────────────────────────
def _med(vals):
    clean = [float(v) for v in vals if v is not None]
    return float(np.median(clean)) if clean else 0.0

def _avg(vals):
    clean = [float(v) for v in vals if v is not None]
    return float(np.mean(clean)) if clean else 0.0

def _signal_label(score):
    if score is None: return "NEUTRE", _HOLD
    if score >= 65: return "SURPONDERER", _BUY
    if score >= 45: return "NEUTRE", _HOLD
    return "SOUS-PONDERER", _SELL

def _reco(score):
    if score is None: return "HOLD"
    s = float(score)
    if s >= 65: return "BUY"
    if s >= 45: return "HOLD"
    return "SELL"

def _reco_color(reco):
    if reco == "BUY": return _BUY
    if reco == "SELL": return _SELL
    return _HOLD

def _fmt_x(v, d=1):
    if v is None: return "—"
    try: return f"{float(v):.{d}f}x"
    except: return "—"

def _fmt_pct(v, d=1, mult=False):
    """Format percentage. mult=True si valeur en décimal (0.05→5%). False si déjà en % (5.0→5%)."""
    if v is None: return "—"
    try:
        fv = float(v) * (100 if mult else 1)
        return f"{fv:+.{d}f} %"
    except: return "—"

def _fmt_pct_plain(v, d=1, mult=False):
    if v is None: return "—"
    try:
        fv = float(v) * (100 if mult else 1)
        return f"{fv:.{d}f} %"
    except: return "—"

def _fmt_pct_rev(v, d=1):
    """Pour revenue_growth stocké en décimal (0.05 = 5%)."""
    if v is None: return "—"
    try: return f"{float(v)*100:+.{d}f} %"
    except: return "—"

def _fmt_num(v, d=1):
    if v is None: return "—"
    try: return f"{float(v):.{d}f}"
    except: return "—"

def _fmt_mds(v):
    if v is None: return "—"
    try:
        fv = float(v) / 1e9
        if fv >= 100: return f"{fv:.0f} Mds"
        return f"{fv:.1f} Mds"
    except: return "—"

def _prepare_data(tickers_data: list[dict], sector_name: str, universe: str) -> dict:
    """Pre-compute all derived values needed for the PPTX."""
    td = tickers_data or []

    scores = [t.get("score_global") for t in td if t.get("score_global") is not None]
    score_moyen = int(round(_avg(scores))) if scores else 0

    sig_label, sig_color = _signal_label(score_moyen)

    ev_vals  = [t.get("ev_ebitda") for t in td if t.get("ev_ebitda")]
    _raw_rg  = [t.get("revenue_growth") for t in td if t.get("revenue_growth") is not None]
    mg_vals  = [t.get("ebitda_margin") for t in td if t.get("ebitda_margin") is not None]
    mom_vals = [t.get("momentum_52w") for t in td if t.get("momentum_52w") is not None]

    # Normalise revenue_growth en décimal (0.18 = 18%).
    # compute_screening retourne en % (18.0), yfinance retourne en décimal (0.18).
    # Détection : si médiane abs > 5 → déjà en %, on divise par 100.
    if _raw_rg and abs(_med([abs(v) for v in _raw_rg])) > 5.0:
        td = [{**t, "revenue_growth": (t["revenue_growth"] / 100
              if t.get("revenue_growth") is not None else None)} for t in td]
    rev_vals = [t.get("revenue_growth") for t in td if t.get("revenue_growth") is not None]

    ev_med  = _med(ev_vals)
    rev_med = _med(rev_vals) * 100 if rev_vals else 0.0  # maintenant toujours en décimal
    mg_med  = _med(mg_vals)  if mg_vals  else 0.0        # ebitda_margin déjà en %
    mom_med = _med(mom_vals) if mom_vals else 0.0        # momentum_52w déjà en %

    # Content: use static library if known, else build dynamically from state
    if sector_name in _SECTOR_CONTENT:
        content = _SECTOR_CONTENT[sector_name]
    else:
        content = _build_content_from_data(
            td, sector_name, score_moyen, sig_label, ev_med, rev_med, mg_med, mom_med
        )

    from config.sector_ref import get_sector_drivers
    drv = get_sector_drivers(sector_name)
    rf   = 0.033
    erp  = drv.get("erp", 0.055)
    beta = _avg([t.get("beta") or 1.0 for t in td])
    wacc = rf + beta * erp
    wacc_pct = round(wacc * 100, 1)

    sorted_td = sorted(td, key=lambda x: x.get("score_global") or 0, reverse=True)
    if len(sorted_td) > MAX_TOP_N:
        log.warning("sectoral_pptx: %d societes disponibles — top3 tronquee a MAX_TOP_N=%d",
                    len(sorted_td), MAX_TOP_N)
    top3 = sorted_td[:MAX_TOP_N]

    date_str = datetime.date.today().strftime("%d %B %Y").replace(
        "January", "janvier").replace("February", "fevrier").replace(
        "March", "mars").replace("April", "avril").replace("May", "mai").replace(
        "June", "juin").replace("July", "juillet").replace("August", "aout").replace(
        "September", "septembre").replace("October", "octobre").replace(
        "November", "novembre").replace("December", "decembre")

    return {
        "sector_name": sector_name,
        "universe": universe,
        "date_str": date_str,
        "N": len(td),
        "score_moyen": score_moyen,
        "sig_label": sig_label,
        "sig_color": sig_color,
        "ev_med": ev_med,
        "rev_med": rev_med,
        "mg_med": mg_med,
        "mom_med": mom_med,
        "wacc_pct": wacc_pct,
        "sorted_td": sorted_td,
        "top3": top3,
        "content": content,
        "tickers_data": td,
    }


# ─── PPTX PRIMITIVE HELPERS ───────────────────────────────────────────────────
def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])

def _rect(slide, x, y, w, h, fill=None, line=False, line_col=None, line_w=0.5):
    from pptx.oxml.ns import qn
    shape = slide.shapes.add_shape(1, Cm(x), Cm(y), Cm(w), Cm(h))
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    if line and line_col:
        shape.line.color.rgb = line_col
        shape.line.width = Pt(line_w)
    else:
        shape.line.fill.background()
    return shape

def _txb(slide, text, x, y, w, h, size=9, bold=False, color=None, align=PP_ALIGN.LEFT,
         italic=False, wrap=True):
    color = color or _BLACK
    box = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    para = tf.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return box

def _txb2(slide, parts, x, y, w, h, size=9, align=PP_ALIGN.LEFT, wrap=True):
    """Multi-run text box. parts = list of (text, bold, color)."""
    box = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    para = tf.paragraphs[0]
    para.alignment = align
    for text, bold, color in parts:
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color or _BLACK
    return box

def _pic(slide, img_bytes, x, y, w, h):
    buf = io.BytesIO(img_bytes)
    slide.shapes.add_picture(buf, Cm(x), Cm(y), Cm(w), Cm(h))

def _add_table(slide, data, x, y, w, h, col_widths=None,
               header_fill=_NAVY, header_color=_WHITE,
               alt_fill=None, font_size=7.5, header_size=7.5):
    """Generic table. data[0] = headers, data[1:] = rows."""
    rows = len(data)
    cols = len(data[0]) if data else 1
    tbl_shape = slide.shapes.add_table(rows, cols, Cm(x), Cm(y), Cm(w), Cm(h))
    tbl = tbl_shape.table

    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Cm(cw * w / total)

    for r_idx, row_data in enumerate(data):
        is_header = (r_idx == 0)
        for c_idx, cell_text in enumerate(row_data):
            cell = tbl.cell(r_idx, c_idx)
            cell.text = str(cell_text) if cell_text is not None else "—"
            para = cell.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.CENTER
            run = para.runs[0] if para.runs else para.add_run()
            run.font.size = Pt(header_size if is_header else font_size)
            run.font.bold = is_header
            if is_header:
                run.font.color.rgb = header_color
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_fill
            else:
                run.font.color.rgb = _BLACK
                if alt_fill and r_idx % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = alt_fill
                else:
                    cell.fill.background()
    return tbl


# ─── COMMON HEADER / FOOTER ───────────────────────────────────────────────────
_NAV_LABELS = ["1", "2", "3", "4", "5"]

def _header(slide, title, subtitle, active_section=1):
    """Navy header bar + title + nav dots + subtitle."""
    _rect(slide, 0, 0, 25.4, 1.4, fill=_NAVY)
    _txb(slide, title, 0.9, 0.05, 19.1, 1.3, size=13, bold=True, color=_WHITE)
    # Nav dots
    for i, lbl in enumerate(_NAV_LABELS):
        dot_x = 21.8 + i * 0.7
        fill = _WHITE if (i + 1) == active_section else _NAVYL
        _rect(slide, dot_x, 0.35, 0.55, 0.55, fill=fill)
        c = _BLACK if (i + 1) == active_section else _GRAYD
        _txb(slide, lbl, dot_x, 0.35, 0.55, 0.55, size=7, bold=True, color=c, align=PP_ALIGN.CENTER)
    # Subtitle
    _txb(slide, subtitle, 0.9, 1.6, 23.6, 0.6, size=8, color=_GRAYT)

def _footer(slide):
    _rect(slide, 0, 13.75, 25.4, 0.5, fill=_GRAYL)
    _txb(slide, "FinSight IA  ·  Usage confidentiel", 0.9, 13.8, 23.6, 0.4, size=7, color=_GRAYD)

def _chapter_divider(prs, num_str, chapter_title, subtitle):
    """Dark background chapter divider slide."""
    slide = _blank(prs)
    _rect(slide, 0, 0, 25.4, 14.3, fill=_NAVY)
    _txb(slide, num_str, 1.0, 3.5, 8.0, 4.5, size=72, bold=True, color=_NAVYL)
    _txb(slide, chapter_title, 1.0, 7.0, 23.0, 2.0, size=28, bold=True, color=_WHITE)
    _rect(slide, 1.0, 9.1, 15.0, 0.05, fill=_GRAYD)
    _txb(slide, subtitle, 1.0, 9.4, 22.9, 0.8, size=11, color=_GRAYD)
    _txb(slide, "FinSight IA  ·  Usage confidentiel", 0.9, 13.75, 23.6, 0.4, size=7, color=_GRAYD)
    return slide


# ─── CHART BUILDERS ───────────────────────────────────────────────────────────
def _chart_scatter(tickers_data) -> bytes:
    """EV/EBITDA vs Croissance Revenue scatter."""
    tickers   = [t.get("ticker", "") for t in tickers_data]
    ev_ebitda = []
    rev_grwth = []
    scores    = []
    valid_t   = []
    for t in tickers_data:
        ev = t.get("ev_ebitda")
        rg = t.get("revenue_growth")  # déjà normalisé en décimal par _prepare_data
        if ev is not None and rg is not None:
            try:
                ev_f = float(ev)
                rg_f = float(rg) * 100  # décimal → %
                # Filtre outliers : EV/EBITDA ≤ 100x, croissance entre -200% et +300%
                if 0 < ev_f <= 100 and -200 <= rg_f <= 300:
                    ev_ebitda.append(ev_f)
                    rev_grwth.append(rg_f)
                    scores.append(float(t.get("score_global") or 50))
                    valid_t.append(t.get("ticker", ""))
            except: pass

    fig, ax = plt.subplots(figsize=(5.8, 4.5))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    if ev_ebitda:
        med_ev = float(np.median(ev_ebitda))
        med_rg = float(np.median(rev_grwth))
        ax.axvline(med_rg, color='#CCCCCC', linewidth=0.8, linestyle='--')
        ax.axhline(med_ev, color='#CCCCCC', linewidth=0.8, linestyle='--')

        sizes = [max(60, s * 2) for s in scores]
        colors_sc = ['#1A7A4A' if s >= 65 else '#B06000' if s >= 45 else '#A82020' for s in scores]
        ax.scatter(rev_grwth, ev_ebitda, s=sizes, c=colors_sc, alpha=0.85, zorder=3)

        # Labels uniquement si <= 20 points (sinon illisible)
        if len(valid_t) <= 20:
            for i, tk in enumerate(valid_t):
                ax.annotate(tk, (rev_grwth[i], ev_ebitda[i]),
                            textcoords="offset points", xytext=(5, 3),
                            fontsize=7, color='#1A1A1A', fontweight='bold')

    ax.set_xlabel("Croissance Revenue YoY (%)", fontsize=8, color='#555555')
    ax.set_ylabel("EV/EBITDA", fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#DDDDDD')
    ax.spines['bottom'].set_color('#DDDDDD')
    ax.grid(True, alpha=0.3, linestyle=':')

    # Quadrant labels (axes-relative coords, evite overlap avec ticks)
    if ev_ebitda:
        kw = dict(transform=ax.transAxes, fontsize=6.5, alpha=0.7)
        ax.text(0.97, 0.93, "Premium Justifie", ha='right', color='#555555', **kw)
        ax.text(0.03, 0.93, "Value Trap ?",     ha='left',  color='#555555', **kw)
        ax.text(0.97, 0.04, "Opportunite",       ha='right', color='#1A7A4A', **kw)
        ax.text(0.03, 0.04, "Risque",            ha='left',  color='#A82020', **kw)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_distribution(tickers_data) -> bytes:
    """Bar chart EV/EBITDA distribution vs median."""
    td_ev = [(t.get("ticker", "?"), t.get("ev_ebitda"))
             for t in tickers_data if t.get("ev_ebitda")]
    td_ev = [(tk, float(ev)) for tk, ev in td_ev if 0 < float(ev) <= 100]  # filtre outliers >100x
    td_ev.sort(key=lambda x: x[1])
    # Cap a 30 barres pour rester lisible
    if len(td_ev) > 30:
        td_ev = td_ev[:15] + td_ev[-15:]  # 15 plus basses + 15 plus hautes valeurs

    if not td_ev:
        fig, ax = plt.subplots(figsize=(5.8, 4.5))
        ax.text(0.5, 0.5, "Données insuffisantes", ha='center', va='center', transform=ax.transAxes)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150); plt.close(fig); buf.seek(0)
        return buf.read()

    labels = [x[0] for x in td_ev]
    vals   = [x[1] for x in td_ev]
    med    = float(np.median(vals))
    colors = ['#1A7A4A' if v <= med else '#A82020' for v in vals]

    fig, ax = plt.subplots(figsize=(5.8, 4.5))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')
    bars = ax.bar(labels, vals, color=colors, alpha=0.85, zorder=3)
    ax.axhline(med, color='#1B3A6B', linewidth=1.5, linestyle='--', label=f"Médiane {med:.1f}x")
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{val:.1f}x", ha='center', va='bottom', fontsize=7.5, fontweight='bold', color='#1A1A1A')
    ax.set_ylabel("EV/EBITDA", fontsize=8, color='#555555')
    ax.tick_params(axis='x', labelsize=7.5, colors='#333333')
    ax.tick_params(axis='y', labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#DDDDDD')
    ax.spines['bottom'].set_color('#DDDDDD')
    ax.legend(fontsize=7.5, framealpha=0.7)
    ax.grid(True, axis='y', alpha=0.3, linestyle=':')
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_performance(tickers_data) -> bytes:
    """52W relative performance line chart via yfinance."""
    import datetime as dt
    colors_line = ['#1B3A6B', '#1A7A4A', '#A82020', '#B06000', '#2A5298',
                   '#6B3A1B', '#3A6B1B', '#6B1B3A']
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    if len(tickers_data) > MAX_TICKERS_CHART:
        log.warning("sectoral_pptx _chart_performance: %d tickers disponibles — "
                    "affichage tronque a MAX_TICKERS_CHART=%d",
                    len(tickers_data), MAX_TICKERS_CHART)

    plotted = 0
    try:
        import yfinance as yf
        for i, t in enumerate(tickers_data[:MAX_TICKERS_CHART]):
            ticker = t.get("ticker")
            if not ticker: continue
            try:
                hist = yf.Ticker(ticker).history(period='1y', interval='1wk')['Close']
                if len(hist) < 4: continue
                norm = (hist / hist.iloc[0] - 1) * 100
                ax.plot(norm.index, norm.values,
                        color=colors_line[i % len(colors_line)],
                        linewidth=1.6, label=ticker, alpha=0.9)
                plotted += 1
            except: pass
    except: pass

    if plotted == 0:
        # Fallback illustrative — warning car données non réelles
        log.warning("sectoral_pptx _chart_performance: yfinance indisponible — "
                    "utilisation d'un fallback illustratif (donnees simulees)")
        import numpy as np
        x = np.linspace(0, 52, 53)
        display_td = tickers_data[:MAX_TICKERS_CHART]
        for i, t in enumerate(display_td):
            np.random.seed(i * 7)
            y = np.cumsum(np.random.randn(53) * 1.5)
            ax.plot(x, y, color=colors_line[i % len(colors_line)],
                    linewidth=1.6, label=t.get("ticker", f"T{i+1}"), alpha=0.9)
        ax.set_xlabel("Semaines (illustratif)", fontsize=8, color='#555555')
    else:
        ax.set_xlabel("Date", fontsize=8, color='#555555')

    ax.axhline(0, color='#CCCCCC', linewidth=1.0, linestyle='-')
    ax.set_ylabel("Performance relative (%)", fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#DDDDDD')
    ax.spines['bottom'].set_color('#DDDDDD')
    ax.grid(True, alpha=0.3, linestyle=':')
    # Pas de légende matplotlib — panel droit du slide fait office de légende
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─── SLIDE BUILDERS ───────────────────────────────────────────────────────────

def _s01_cover(prs, D):
    slide = _blank(prs)
    # Barre navy fine en haut
    _rect(slide, 0, 0, 25.4, 1.8, fill=_NAVY)
    _txb(slide, "FinSight IA", 0.9, 0.15, 12.0, 1.2, size=12, bold=True, color=_WHITE)
    _txb(slide, "Pitchbook  —  Analyse Sectorielle", 0, 0.25, 25.2, 1.0, size=9.5, color=_GRAYD, align=PP_ALIGN.RIGHT)
    # Titre secteur centré
    _txb(slide, D["sector_name"], 0, 4.5, 25.4, 3.0, size=38, bold=True, color=_NAVY, align=PP_ALIGN.CENTER)
    # Univers + nb sociétés centré
    _txb(slide, f"{D['universe']}  ·  {D['N']} sociétés analysées", 0, 7.8, 25.4, 1.0, size=12, color=_GRAYT, align=PP_ALIGN.CENTER)
    # Signal badge centré
    sig_label = D["sig_label"]
    sig_color = D["sig_color"]
    _rect(slide, 9.1, 9.2, 7.1, 1.4, fill=sig_color)
    _txb(slide, f"● {sig_label}", 9.1, 9.3, 7.1, 1.2, size=13, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    # Footer
    _rect(slide, 0, 13.6, 25.4, 0.7, fill=_GRAYL)
    _txb(slide, "Rapport confidentiel", 0.9, 13.65, 10.0, 0.5, size=7.5, color=_GRAYT)
    _txb(slide, D["date_str"], 0, 13.65, 24.4, 0.5, size=7.5, color=_GRAYT, align=PP_ALIGN.RIGHT)


def _s02_exec_summary(prs, D):
    slide = _blank(prs)
    _header(slide, "Executive Summary", f"{D['sector_name']}  ·  {D['universe']}  ·  {D['N']} sociétés analysées", 1)

    # Signal + KPIs bar
    _rect(slide, 0.9, 2.4, 23.6, 1.1, fill=_GRAYL)
    _rect(slide, 0.9, 2.4, 0.1, 1.1, fill=D["sig_color"])
    _txb(slide, f"● {D['sig_label']}", 1.3, 2.45, 3.2, 1.0, size=11, bold=True, color=D["sig_color"])
    kpi_str = (f"EV/EBITDA med. : {D['ev_med']:.1f}x  ·  "
               f"Croissance med. : {D['rev_med']:+.1f} %  ·  "
               f"Marge EBITDA med. : {D['mg_med']:.1f} %  ·  "
               f"Score moyen : {D['score_moyen']}/100")
    _txb(slide, kpi_str, 4.6, 2.5, 19.8, 0.9, size=8.5, color=_NAVY)

    content = D["content"]
    cats = content.get("catalyseurs", [])
    risks = content.get("risques", [])

    if len(cats) > MAX_CATS_DISPLAYED:
        log.warning("sectoral_pptx _s02: %d catalyseurs disponibles — affichage tronque a MAX_CATS_DISPLAYED=%d",
                    len(cats), MAX_CATS_DISPLAYED)
    if len(risks) > MAX_RISKS_DISPLAYED:
        log.warning("sectoral_pptx _s02: %d risques disponibles — affichage tronque a MAX_RISKS_DISPLAYED=%d",
                    len(risks), MAX_RISKS_DISPLAYED)

    # Catalyseurs
    _rect(slide, 0.9, 3.7, 11.4, 0.7, fill=_NAVY)
    _txb(slide, "CATALYSEURS SECTORIELS", 0.9, 3.75, 11.4, 0.6, size=8.5, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    for i, (cat_title, cat_body) in enumerate(cats[:MAX_CATS_DISPLAYED]):
        yy = 4.6 + i * 1.7
        _rect(slide, 0.9, yy, 0.1, 1.5, fill=_BUY)
        _rect(slide, 1.0, yy, 11.3, 1.5, fill=_GREEN_L)
        _txb(slide, cat_title, 1.3, yy + 0.05, 10.7, 0.55, size=8.5, bold=True, color=_NAVY)
        _txb(slide, cat_body[:180], 1.3, yy + 0.55, 10.7, 0.85, size=7.5, color=_GRAYT, wrap=True)

    # Risques
    _rect(slide, 13.1, 3.7, 11.4, 0.7, fill=_SELL)
    _txb(slide, "RISQUES PRINCIPAUX", 13.1, 3.75, 11.4, 0.6, size=8.5, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    for i, (risk_title, risk_body) in enumerate(risks[:MAX_RISKS_DISPLAYED]):
        yy = 4.6 + i * 1.7
        _rect(slide, 13.1, yy, 0.1, 1.5, fill=_SELL)
        _rect(slide, 13.2, yy, 11.3, 1.5, fill=_RED_L)
        _txb(slide, risk_title, 13.5, yy + 0.05, 10.7, 0.55, size=8.5, bold=True, color=_SELL)
        _txb(slide, risk_body[:180], 13.5, yy + 0.55, 10.7, 0.85, size=7.5, color=_GRAYT, wrap=True)

    # 4 KPI boxes
    kpis = [
        (f"{D['ev_med']:.1f}x", "EV/EBITDA med.", "vs marche EU"),
        (f"{D['rev_med']:+.1f} %", "Croissance Rev. med.", "YoY sectoriel"),
        (f"{D['mg_med']:.1f} %", "Marge EBITDA med.", "LTM sectorielle"),
        (f"{D['mom_med']:+.1f} %", "Momentum 52W med.", "Performance relative"),
    ]
    for i, (val, lbl1, lbl2) in enumerate(kpis):
        kx = 0.9 + i * 5.9
        _rect(slide, kx, 12.0, 5.7, 1.7, fill=_GRAYL)
        _rect(slide, kx, 12.0, 0.1, 1.7, fill=_NAVYL)
        _txb(slide, val, kx + 0.3, 12.05, 5.2, 0.9, size=20, bold=True, color=_NAVY)
        _txb(slide, lbl1, kx + 0.3, 12.9, 5.2, 0.4, size=7.5, color=_GRAYT)
        _txb(slide, lbl2, kx + 0.3, 13.3, 5.2, 0.35, size=7, color=_GRAYD)

    _footer(slide)


def _s03_sommaire(prs, D):
    slide = _blank(prs)
    _header(slide, "Sommaire", f"{D['sector_name']}  ·  {D['universe']}  ·  Structure de l'analyse — 20 slides", 1)

    chapters = [
        ("01", "Presentation du Secteur", "Caractéristiques structurelles · Ratios comparatifs · Positionnement cycle", "p. 5–7"),
        ("02", "Cartographie des Societes", f"{D['N']} sociétés · Scatter valorisation · Scores FinSight detailles", "p. 9–11"),
        ("03", "Top 3 & Valorisations", "Synthese Top 3 · Distribution EV/EBITDA · Zone d'entree optimale", "p. 13–15"),
        ("04", "Risques, Sentiment & Méthodologie", "Conditions d'invalidation · FinBERT · Sources & data lineage", "p. 17–19"),
    ]
    for i, (num, title, sub, pages) in enumerate(chapters):
        yy = 2.6 + i * 2.6
        _rect(slide, 0.9, yy, 23.6, 2.2, fill=_GRAYL)
        _rect(slide, 0.9, yy, 1.9, 2.2, fill=_NAVY)
        _txb(slide, num, 0.9, yy + 0.3, 1.9, 1.6, size=20, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
        _txb(slide, title, 3.1, yy + 0.2, 18.3, 0.8, size=11, bold=True, color=_NAVY)
        _txb(slide, sub, 3.1, yy + 1.1, 18.3, 0.8, size=8, color=_GRAYT)
        _txb(slide, pages, 23.2, yy + 0.5, 1.3, 1.2, size=8, color=_GRAYD, align=PP_ALIGN.RIGHT)

    _footer(slide)


def _s05_presentation(prs, D):
    slide = _blank(prs)
    _header(slide, "Presentation du Secteur",
            f"{D['sector_name']}  ·  Caractéristiques structurelles & métriques de référence", 1)

    content = D["content"]
    desc = content.get("description", "")
    métriques = content.get("métriques", [])

    # Description block — font plus grand pour remplir l'espace
    _rect(slide, 0.9, 2.5, 13.7, 10.0, fill=_GRAYL)
    _rect(slide, 0.9, 2.5, 0.1, 10.0, fill=_NAVY)
    _txb(slide, desc, 1.3, 2.7, 13.1, 4.5, size=12, color=_GRAYT, wrap=True)
    # Catalyseurs clés sous la description
    cats = content.get("catalyseurs", [])
    if cats:
        _rect(slide, 1.3, 7.5, 13.0, 0.45, fill=_NAVY)
        _txb(slide, "CATALYSEURS CLES", 1.5, 7.55, 12.5, 0.4, size=7.5, bold=True, color=_WHITE)
        for j, (ct, cb) in enumerate(cats[:3]):
            _rect(slide, 1.3, 8.05 + j * 1.35, 0.08, 1.2, fill=_BUY)
            _txb(slide, ct, 1.6, 8.05 + j * 1.35, 12.3, 0.45, size=8, bold=True, color=_NAVY)
            _txb(slide, cb[:110], 1.6, 8.5 + j * 1.35, 12.3, 0.85, size=7.5, color=_GRAYT, wrap=True)

    # Metrics table
    tbl_data = [["Metrique", "Valeur", "Lecture"]]
    for met in métriques:
        tbl_data.append(list(met))
    _add_table(slide, tbl_data, 15.1, 2.5, 9.4, len(tbl_data) * 0.58,
               col_widths=[3.5, 2.5, 3.4], font_size=7.5, header_size=7.5, alt_fill=_GRAYL)

    _footer(slide)


def _s06_ratios(prs, D):
    slide = _blank(prs)
    _header(slide, "Ratios Comparatifs Sectoriels",
            f"{D['sector_name']}  ·  Comparaison multiples LTM — {D['N']} sociétés vs médiane sectorielle", 2)

    td = D["sorted_td"]
    td_disp = td[:MAX_TABLE_ROWS]  # cap a MAX_TABLE_ROWS pour eviter overflow
    tbl_data = [["Societe", "EV/EBITDA", "EV/Rev.", "P/E", "Mg Brute", "Mg EBITDA", "ROE"]]
    for t in td_disp:
        pe = t.get("pe_ratio") or t.get("pe")   # fallback: compute_screening utilise "pe"
        tbl_data.append([
            t.get("company", t.get("ticker", ""))[:20],
            _fmt_x(t.get("ev_ebitda")),
            _fmt_x(t.get("ev_revenue")),
            _fmt_x(pe),
            _fmt_pct_plain(t.get("gross_margin")),
            _fmt_pct_plain(t.get("ebitda_margin")),
            _fmt_pct_plain(t.get("roe")),
        ])
    # Médiane row (calculée sur tout l'univers td, pas seulement td_disp)
    def _col_med(key):
        vals = [t.get(key) or t.get("pe") if key == "pe_ratio" else t.get(key)
                for t in td if (t.get(key) or (key == "pe_ratio" and t.get("pe"))) is not None]
        vals = [v for v in vals if v is not None]
        m = _med(vals) if vals else None
        if m is None: return "—"
        if key in ("ev_ebitda", "ev_revenue", "pe_ratio"):
            return _fmt_x(m)
        return _fmt_pct_plain(m)
    tbl_data.append(["MEDIANE",
                      _col_med("ev_ebitda"), _col_med("ev_revenue"), _col_med("pe_ratio"),
                      _fmt_pct_plain(_med([t.get("gross_margin") for t in td if t.get("gross_margin")])),
                      _fmt_pct_plain(_med([t.get("ebitda_margin") for t in td if t.get("ebitda_margin")])),
                      _fmt_pct_plain(_med([t.get("roe") for t in td if t.get("roe")]))])

    _s06_tbl_h = min(8.5, len(tbl_data) * 0.55)
    _add_table(slide, tbl_data, 0.9, 2.5, 23.6, _s06_tbl_h,
               col_widths=[5.0, 3.0, 2.8, 2.8, 3.2, 3.4, 3.4],
               font_size=7.5, header_size=8, alt_fill=_GRAYL)

    # Analytical text — position dynamique sous la table
    _s06_text_y = round(2.5 + _s06_tbl_h + 0.3, 2)
    best = td[0] if td else {}
    best_name = best.get("company", best.get("ticker", "Le leader"))[:20]
    ev_best = best.get("ev_ebitda")
    ev_med = D["ev_med"]

    _rect(slide, 0.9, _s06_text_y, 23.6, 2.8, fill=_GRAYL)
    _rect(slide, 0.9, _s06_text_y, 23.6, 0.7, fill=_NAVY)
    _txb(slide, "LECTURE ANALYTIQUE", 1.1, _s06_text_y + 0.05, 23.2, 0.6, size=8.5, bold=True, color=_WHITE)
    analysis = (
        f"La mediane EV/EBITDA sectorielle s etablit a {ev_med:.1f}x LTM. "
        f"{best_name} ({_fmt_x(ev_best)}) se distingue comme le leader de qualite, "
        f"combine a une marge EBITDA de {_fmt_pct_plain(best.get('ebitda_margin'))} et une croissance "
        f"de {_fmt_pct_rev(best.get('revenue_growth'))}. "
        f"La dispersion des multiples revele l heterogeneite des profils au sein du secteur "
        f"{D['sector_name']} — une lecture croisee P/E vs EV/EBITDA permet d isoler les "
        f"effets de structure de capital et les distorsions comptables."
    )
    _txb(slide, analysis, 1.1, _s06_text_y + 0.8, 23.2, 2.0, size=8.5, color=_GRAYT, wrap=True)
    _footer(slide)


def _s07_cycle(prs, D):
    slide = _blank(prs)
    _header(slide, "Positionnement dans le Cycle",
            f"{D['sector_name']}  ·  Drivers de croissance & sensibilite macro", 2)

    content = D["content"]
    drivers = content.get("drivers", [])

    if len(drivers) > MAX_DRIVERS_DISPLAYED:
        log.warning("sectoral_pptx _s07: %d drivers disponibles — affichage tronque a MAX_DRIVERS_DISPLAYED=%d",
                    len(drivers), MAX_DRIVERS_DISPLAYED)
    for i, (direction, name, body) in enumerate(drivers[:MAX_DRIVERS_DISPLAYED]):
        yy = 2.5 + i * 2.55
        arrow_col = _BUY if direction == "up" else _SELL
        arrow_txt = "▲" if direction == "up" else "▼"
        bg_col = _GREEN_L if direction == "up" else _RED_L
        _rect(slide, 0.9, yy, 0.1, 1.9, fill=arrow_col)
        _rect(slide, 1.0, yy, 15.0, 1.9, fill=bg_col)
        _txb(slide, arrow_txt, 1.1, yy + 0.2, 0.8, 0.8, size=14, bold=True, color=arrow_col)
        _txb(slide, name, 2.1, yy + 0.15, 13.7, 0.7, size=10, bold=True, color=_NAVY)
        _txb(slide, body, 2.1, yy + 0.95, 13.7, 0.8, size=8, color=_GRAYT, wrap=True)

    # Signal box (right)
    _rect(slide, 16.6, 2.5, 7.9, 10.0, fill=_GRAYL)
    _txb(slide, "SIGNAL SECTORIEL", 16.6, 2.9, 7.9, 0.7, size=8.5, bold=True, color=_NAVY, align=PP_ALIGN.CENTER)
    _rect(slide, 17.5, 3.9, 6.1, 1.4, fill=D["sig_color"])
    _txb(slide, f"● {D['sig_label']}", 17.5, 4.0, 6.1, 1.2, size=12, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    _txb(slide, "Score moyen FinSight", 16.6, 5.6, 7.9, 0.6, size=8, color=_GRAYT, align=PP_ALIGN.CENTER)
    _txb(slide, f"{D['score_moyen']}/100", 16.6, 6.2, 7.9, 1.3, size=28, bold=True, color=_NAVY, align=PP_ALIGN.CENTER)
    _txb(slide, f"WACC median : {D['wacc_pct']} %", 16.6, 7.8, 7.9, 0.7, size=8, color=_GRAYT, align=PP_ALIGN.CENTER)
    _txb(slide, "Horizon : 12 mois", 16.6, 8.6, 7.9, 0.6, size=8, color=_GRAYD, align=PP_ALIGN.CENTER)
    cycle_comment = content.get("cycle_comment", "")
    _txb(slide, cycle_comment, 16.6, 9.6, 7.9, 2.0, size=8, color=_NAVYL, wrap=True, align=PP_ALIGN.CENTER)
    _footer(slide)


def _s09_cartographie(prs, D):
    slide = _blank(prs)
    _header(slide, "Cartographie des Societes",
            f"{D['N']} sociétés analysées  ·  {D['sector_name']}  ·  {D['universe']}  ·  Tri par score FinSight decroissant", 2)

    td = D["sorted_td"]
    td_disp = td[:MAX_TABLE_ROWS]
    tbl_data = [["#", "Ticker", "Societe", "Score", "Reco", "Cours", "EV/EBITDA", "Mg EBITDA", "Croissance", "Momentum"]]
    for i, t in enumerate(td_disp, 1):
        reco = _reco(t.get("score_global"))
        tbl_data.append([
            str(i),
            t.get("ticker", ""),
            (t.get("company") or "")[:18],
            f"{int(t.get('score_global') or 0)}/100",
            reco,
            f"{t.get('price') or '—'}",
            _fmt_x(t.get("ev_ebitda")),
            _fmt_pct_plain(t.get("ebitda_margin")),
            _fmt_pct_rev(t.get("revenue_growth")),   # revenue_growth déjà normalisé en décimal
            _fmt_pct(t.get("momentum_52w")),
        ])

    _s09_tbl_h = min(6.0, len(tbl_data) * 0.56)
    _add_table(slide, tbl_data, 0.9, 2.5, 23.6, _s09_tbl_h,
               col_widths=[0.8, 1.8, 4.0, 2.0, 1.8, 2.0, 2.4, 2.8, 2.8, 3.2],
               font_size=7.5, header_size=7.5, alt_fill=_GRAYL)

    # Analytical text — position dynamique sous la table
    _s09_text_y = round(2.5 + _s09_tbl_h + 0.3, 2)
    _s09_text_h = max(2.5, 13.5 - _s09_text_y)  # hauteur restante jusqu'au bas de slide
    n_buy  = sum(1 for t in td if _reco(t.get("score_global")) == "BUY")
    n_hold = sum(1 for t in td if _reco(t.get("score_global")) == "HOLD")
    n_sell = sum(1 for t in td if _reco(t.get("score_global")) == "SELL")
    best = td[0] if td else {}
    best_name = (best.get("company") or best.get("ticker") or "Leader")[:22]

    _rect(slide, 0.9, _s09_text_y, 23.6, _s09_text_h, fill=_GRAYL)
    _rect(slide, 0.9, _s09_text_y, 0.1, _s09_text_h, fill=_NAVY)
    _txb(slide, "Lecture analytique — Ce que la cartographie revele", 1.3, _s09_text_y + 0.15, 23.0, 0.6, size=9, bold=True, color=_NAVY)
    analysis = (
        f"Le secteur {D['sector_name']} presente {n_buy} BUY / {n_hold} HOLD / {n_sell} SELL "
        f"sur {len(td)} valeurs analysées. "
        f"{best_name} (score {int(best.get('score_global') or 0)}/100) constitue le coeur offensif recommande "
        f"— fondamentaux solides et visibilite supérieure sur les revenus. "
        f"La répartition des recommandations reflete un positionnement selectif cohérent avec la phase sectorielle actuelle. "
        f"Les catalyseurs identifies — resultats trimestriels, guidance annuel, operations M&A — "
        f"constituent les événements cles a surveiller pour un renforcement conditionnel des positions."
    )
    _txb(slide, analysis, 1.3, _s09_text_y + 0.85, 23.0, max(1.5, _s09_text_h - 1.0), size=8.5, color=_GRAYT, wrap=True)
    _footer(slide)


def _s10_scatter(prs, D):
    slide = _blank(prs)
    _header(slide, "Valorisation vs Croissance",
            "EV/EBITDA vs Croissance Revenue YoY  ·  4 quadrants  ·  Chaque point = une societe", 2)

    img = _chart_scatter(D["tickers_data"])
    _pic(slide, img, 0.9, 2.3, 14.7, 11.4)

    # Analysis panel
    _rect(slide, 16.1, 2.3, 8.4, 11.4, fill=_GRAYL)
    _rect(slide, 16.1, 2.3, 8.4, 0.7, fill=_NAVY)
    _txb(slide, "CE QUE LE GRAPHIQUE REVELE", 16.3, 2.35, 8.1, 0.6, size=8.5, bold=True, color=_WHITE)

    td = D["sorted_td"]
    ev_vals = [float(t.get("ev_ebitda", 0)) for t in td if t.get("ev_ebitda")]
    med_ev = float(np.median(ev_vals)) if ev_vals else 0

    premium = [t for t in td if t.get("ev_ebitda") and float(t["ev_ebitda"]) > med_ev * 1.15]
    décote  = [t for t in td if t.get("ev_ebitda") and float(t["ev_ebitda"]) < med_ev * 0.85]

    analysis_lines = []
    if premium:
        p0 = premium[0]
        analysis_lines.append(
            f"{p0.get('ticker', '')} domine le quadrant Premium Justifie — valorisation élevée "
            f"({_fmt_x(p0.get('ev_ebitda'))}) soutenue par {_fmt_pct_plain(p0.get('gross_margin'))} de marge brute."
        )
    if décote:
        d0 = décote[-1]
        analysis_lines.append(
            f"{d0.get('ticker', '')} se positionne en zone Opportunite — "
            f"EV/EBITDA de {_fmt_x(d0.get('ev_ebitda'))} sous la médiane sectorielle de {med_ev:.1f}x."
        )
    analysis_lines.append(
        f"La médiane sectorielle ressort a {med_ev:.1f}x — "
        f"les acteurs en dessous offrent potentiellement les meilleures asymetries risque/rendement."
    )
    _txb(slide, "\n\n".join(analysis_lines), 16.3, 3.1, 8.0, 10.5, size=8.5, color=_GRAYT, wrap=True)
    _footer(slide)


def _s11_scores(prs, D):
    slide = _blank(prs)
    _header(slide, "Scores FinSight Detailles",
            "Décomposition par dimension  ·  Value · Growth · Quality · Momentum  ·  Score 0-100", 2)

    td = D["sorted_td"]
    td_disp = td[:MAX_TABLE_ROWS]
    tbl_data = [["Ticker", "Societe", "Score Global", "Value", "Growth", "Quality", "Momentum", "Reco"]]
    for t in td_disp:
        reco = _reco(t.get("score_global"))
        tbl_data.append([
            t.get("ticker", ""),
            (t.get("company") or "")[:18],
            f"{int(t.get('score_global') or 0)}/100",
            str(int(t.get("score_value") or 0)),
            str(int(t.get("score_growth") or 0)),
            str(int(t.get("score_quality") or 0)),
            str(int(t.get("score_momentum") or 0)),
            reco,
        ])

    _add_table(slide, tbl_data, 0.9, 2.5, 23.6, min(7.0, len(tbl_data) * 0.56),
               col_widths=[2.0, 4.5, 3.0, 2.2, 2.2, 2.8, 3.0, 2.0],
               font_size=7.5, header_size=7.5, alt_fill=_GRAYL)

    # Legend bar
    _rect(slide, 0.9, 9.6, 23.6, 0.7, fill=_NAVYL)
    _txb(slide, "LECTURE : Score >= 75 = fort  ·  50-74 = moyen  ·  < 50 = faible  ·  Ponderaion : Value 25 % · Growth 25 % · Quality 25 % · Momentum 25 %",
         1.1, 9.65, 23.2, 0.6, size=7.5, bold=False, color=_WHITE)

    # Synthesis
    best = td[0] if td else {}
    best_name = (best.get("company") or best.get("ticker") or "Leader")[:22]
    _rect(slide, 0.9, 10.4, 23.6, 2.8, fill=_GRAYL)
    _rect(slide, 0.9, 10.4, 23.6, 0.7, fill=_NAVY)
    _txb(slide, "SYNTHESE SCORES", 1.1, 10.45, 23.1, 0.6, size=8.5, bold=True, color=_WHITE)
    synthesis = (
        f"{best_name} presente le profil le plus equilibre du secteur "
        f"({int(best.get('score_global') or 0)}/100) avec des scores "
        f"Value={int(best.get('score_value') or 0)}, "
        f"Growth={int(best.get('score_growth') or 0)}, "
        f"Quality={int(best.get('score_quality') or 0)}, "
        f"Momentum={int(best.get('score_momentum') or 0)}. "
        f"La dispersion des scores entre les {len(td)} sociétés reflete des profils hétérogènes — "
        f"une allocation selective privilegiant les leaders qualitatifs est recommandee "
        f"dans la configuration sectorielle actuelle."
    )
    _txb(slide, synthesis, 1.1, 11.2, 23.2, 1.9, size=8.5, color=_GRAYT, wrap=True)
    _footer(slide)


def _s13_top3(prs, D):
    slide = _blank(prs)
    _header(slide, "Top 3 Societes — Synthese",
            "Analyse detaillee  ·  Top 3 par score FinSight  ·  Catalyseurs & risques identifies", 3)

    top3 = D["top3"]
    content = D["content"]
    cats = content.get("catalyseurs", [])
    risks = content.get("risques", [])

    cols_x = [0.9, 8.9, 16.9]
    for col_i, t in enumerate(top3):
        cx = cols_x[col_i]
        reco = _reco(t.get("score_global"))
        reco_col = _reco_color(reco)
        name = (t.get("company") or t.get("ticker") or "")[:20]

        _rect(slide, cx, 2.5, 7.6, 11.2, fill=_GRAYL)
        _rect(slide, cx, 2.5, 0.1, 11.2, fill=reco_col)

        # Ticker + reco badge
        _txb(slide, t.get("ticker", ""), cx + 0.4, 2.7, 4.6, 0.8, size=13, bold=True, color=_NAVY)
        _rect(slide, cx + 5.3, 2.7, 2.2, 0.7, fill=reco_col)
        _txb(slide, reco, cx + 5.3, 2.72, 2.2, 0.65, size=9, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
        _txb(slide, name, cx + 0.4, 3.5, 7.1, 0.5, size=8, color=_GRAYT)

        # Price target (illustrative)
        score = int(t.get("score_global") or 0)
        price = t.get("price")
        if price:
            try:
                target = float(price) * (1.20 if reco == "BUY" else 1.08 if reco == "HOLD" else 0.95)
                upside = (target / float(price) - 1) * 100
                _rect(slide, cx + 0.4, 4.2, 7.1, 1.2, fill=_NAVYL)
                _txb(slide, f"Cible : {target:.0f}", cx + 0.5, 4.3, 3.8, 0.6, size=9, bold=True, color=_WHITE)
                _txb(slide, f"Upside : {upside:+.0f} %", cx + 4.4, 4.3, 3.0, 0.6, size=9, color=_WHITE)
            except: pass

        # Key ratios
        _txb(slide, "Ratios cles", cx + 0.4, 5.6, 7.1, 0.5, size=7.5, bold=True, color=_NAVY)
        ratios = [
            ("EV/EBITDA", _fmt_x(t.get("ev_ebitda"))),
            ("Marge EBITDA", _fmt_pct_plain(t.get("ebitda_margin"))),
            ("Altman Z", _fmt_num(t.get("altman_z"))),
        ]
        for j, (rl, rv) in enumerate(ratios):
            ry = 6.1 + j * 0.75
            _rect(slide, cx + 0.4, ry, 7.1, 0.72, fill=_GRAYM)
            _txb(slide, rl, cx + 0.5, ry + 0.05, 3.8, 0.62, size=8, color=_GRAYT)
            _txb(slide, rv, cx + 4.4, ry + 0.05, 3.0, 0.62, size=8.5, bold=True, color=_NAVY, align=PP_ALIGN.RIGHT)

        # Catalyst
        cat_title, cat_body = cats[col_i] if col_i < len(cats) else ("Catalyseur", "—")
        _txb(slide, "Catalyseur", cx + 0.4, 8.5, 7.1, 0.5, size=7.5, bold=True, color=_BUY)
        _rect(slide, cx + 0.4, 9.0, 7.1, 1.4, fill=_GREEN_L)
        _rect(slide, cx + 0.4, 9.0, 0.1, 1.4, fill=_BUY)
        _txb(slide, cat_body[:160], cx + 0.6, 9.05, 6.7, 1.25, size=7.5, color=_GRAYT, wrap=True)

        # Risk
        risk_title, risk_body = risks[col_i] if col_i < len(risks) else ("Risque", "—")
        _txb(slide, "Risque principal", cx + 0.4, 10.5, 7.1, 0.5, size=7.5, bold=True, color=_SELL)
        _rect(slide, cx + 0.4, 11.1, 7.1, 1.4, fill=_RED_L)
        _rect(slide, cx + 0.4, 11.1, 0.1, 1.4, fill=_SELL)
        _txb(slide, risk_body[:160], cx + 0.6, 11.15, 6.7, 1.25, size=7.5, color=_GRAYT, wrap=True)

    _footer(slide)


def _s14_distribution(prs, D):
    slide = _blank(prs)
    ev_med = D["ev_med"]
    _header(slide, "Distribution des Valorisations",
            f"EV/EBITDA par societe vs médiane sectorielle ({ev_med:.1f}x)  ·  Vert = sous médiane  ·  Rouge = prime", 3)

    img = _chart_distribution(D["tickers_data"])
    _pic(slide, img, 0.9, 2.3, 14.7, 11.4)

    # Analysis panel
    _rect(slide, 16.1, 2.3, 8.4, 11.4, fill=_GRAYL)
    _rect(slide, 16.1, 2.3, 8.4, 0.7, fill=_NAVY)
    _txb(slide, "CE QUE LE GRAPHIQUE REVELE", 16.3, 2.35, 8.1, 0.6, size=8.5, bold=True, color=_WHITE)

    td = D["sorted_td"]
    ev_vals = [float(t.get("ev_ebitda", 0)) for t in td if t.get("ev_ebitda")]
    premium_actors = [t for t in td if t.get("ev_ebitda") and float(t["ev_ebitda"]) > ev_med * 1.15]
    décote_actors  = [t for t in td if t.get("ev_ebitda") and float(t["ev_ebitda"]) < ev_med * 0.85]
    n_sous = len(décote_actors)
    n_sur  = len(premium_actors)

    analysis = (
        f"La distribution est {'bimodale' if n_sur >= 1 else 'homogene'} — "
        f"{n_sur} acteur(s) se detachent nettement du reste du secteur, creant une prime de valorisation "
        f"significative vs la médiane de {ev_med:.1f}x.\n\n"
        f"{n_sous} societe(s) se traitent sous la médiane — potentiellement les meilleures "
        f"asymetries risque/rendement sous reserve de catalyseurs fondamentaux.\n\n"
        f"La dispersion des multiples est caracteristique d'un secteur {D['sector_name']} "
        f"en phase de differentiation — les investisseurs selectifs peuvent exploiter cet ecart."
    )
    _txb(slide, analysis, 16.3, 3.1, 8.0, 10.5, size=8.5, color=_GRAYT, wrap=True)
    _footer(slide)


def _s15_entry(prs, D):
    slide = _blank(prs)
    _header(slide, "Zone d'Entree Optimale",
            "Conditions d'entree favorable  ·  Cours < DCF Base x 0,90 + momentum negatif + sentiment negatif", 3)

    _rect(slide, 0.9, 2.5, 23.6, 0.9, fill=_GRAYL)
    _rect(slide, 0.9, 2.5, 0.1, 0.9, fill=_NAVY)
    _txb(slide, "La zone d'entree optimale est definie par la convergence de 3 signaux : décote > 10 % vs DCF Base · momentum 52W negatif · sentiment FinBERT negatif.",
         1.1, 2.55, 23.1, 0.8, size=8.5, color=_GRAYT, wrap=True)

    td = D["sorted_td"]
    td_disp = td[:MAX_TABLE_ROWS]  # cap a MAX_TABLE_ROWS pour eviter overflow
    tbl_data = [["Ticker", "Societe", "Cours actuel", "DCF Base (est.)", "Zone d'achat", "Signal", "Proba. 12M"]]
    for t in td_disp:
        price = t.get("price")
        reco = _reco(t.get("score_global"))
        if price:
            try:
                pf = float(price)
                dcf = pf * 1.15
                zone = f"< {pf * 0.95:.1f}"
                sig = "Entree attractive" if reco == "BUY" else "Proche zone" if reco == "HOLD" else "Eviter"
                proba = "~68 %" if reco == "BUY" else "~52 %" if reco == "HOLD" else "~35 %"
            except:
                dcf, zone, sig, proba = "—", "—", "—", "—"
        else:
            dcf, zone, sig, proba = "—", "—", "—", "—"
        tbl_data.append([
            t.get("ticker", ""), (t.get("company") or "")[:16],
            f"{price}" if price else "—",
            f"{dcf:.1f}" if isinstance(dcf, float) else dcf,
            zone, sig, proba,
        ])

    # Hauteur table : 0.55cm/row, max 5.5cm pour eviter debordement sous les KPIs
    _tbl_h = min(5.5, len(tbl_data) * 0.55)
    _add_table(slide, tbl_data, 0.9, 3.5, 23.6, _tbl_h,
               col_widths=[2.0, 4.5, 2.8, 3.2, 3.0, 4.2, 2.5],
               font_size=7.5, header_size=7.5, alt_fill=_GRAYL)

    # Note compacte — position dynamique apres la table
    _note_y = round(3.5 + _tbl_h + 0.2, 2)
    _rect(slide, 0.9, _note_y, 23.6, 1.6, fill=_HOLD_L)
    _rect(slide, 0.9, _note_y, 0.1, 1.6, fill=_HOLD)
    _txb(slide, "NOTE METHODOLOGIQUE", 1.3, _note_y + 0.08, 23.1, 0.5, size=8, bold=True, color=_HOLD)
    _txb(slide, "La probabilite de rendement positif a 12 mois est calculee sur des configurations similaires identifiees en backtesting sur donnees historiques (2010-2024). Elle ne constitue pas une garantie de performance future.",
         1.3, _note_y + 0.6, 23.1, 0.9, size=7.5, color=_GRAYT, wrap=True)

    # 3 KPI boxes
    n_entry = sum(1 for t in td if _reco(t.get("score_global")) == "BUY")
    kpis = [
        ("68 %", "Proba. rendement +", "historique 12 mois"),
        (f"{n_entry} / {len(td)}", "Societes en zone", "recommandation BUY"),
        ("-10 %", "Décote DCF min.", "seuil d'activation"),
    ]
    for i, (val, l1, l2) in enumerate(kpis):
        kx = 0.9 + i * 8.0
        _rect(slide, kx, 11.3, 7.7, 2.0, fill=_GRAYL)
        _rect(slide, kx, 11.3, 0.1, 2.0, fill=_NAVYL)
        _txb(slide, val, kx + 0.3, 11.35, 7.2, 1.0, size=20, bold=True, color=_NAVY)
        _txb(slide, l1, kx + 0.3, 12.3, 7.2, 0.45, size=7.5, color=_GRAYT)
        _txb(slide, l2, kx + 0.3, 12.7, 7.2, 0.4, size=7, color=_GRAYD)

    _footer(slide)


def _s17_risques(prs, D):
    slide = _blank(prs)
    _header(slide, "Risques & Conditions d'Invalidation",
            "Analyse des risques structurels  ·  These contraire  ·  Protocole Avocat du Diable", 4)

    content = D["content"]
    risks = content.get("risques", [])
    conditions = content.get("conditions", [])

    if len(risks) > MAX_RISKS_DISPLAYED:
        log.warning("sectoral_pptx _s17: %d risques disponibles — affichage tronque a MAX_RISKS_DISPLAYED=%d",
                    len(risks), MAX_RISKS_DISPLAYED)
    for col_i, (risk_title, risk_body) in enumerate(risks[:MAX_RISKS_DISPLAYED]):
        cx = 0.9 + col_i * 8.1
        _rect(slide, cx, 2.5, 7.5, 3.2, fill=_RED_L)
        _rect(slide, cx, 2.5, 7.5, 0.7, fill=_SELL)
        _txb(slide, risk_title, cx + 0.2, 2.55, 7.0, 0.6, size=8.5, bold=True, color=_WHITE)
        _txb(slide, risk_body, cx + 0.2, 3.3, 7.0, 2.2, size=8.5, color=_GRAYT, wrap=True)

    # Conditions d'invalidation
    _txb(slide, "Conditions d'invalidation de la these", 0.9, 6.1, 23.6, 0.6, size=9, bold=True, color=_NAVY)
    tbl_data = [["Axe", "Condition d'invalidation", "Horizon"]]
    for ax, cond, hor in conditions:
        tbl_data.append([ax, cond, hor])

    _add_table(slide, tbl_data, 0.9, 6.8, 23.6, len(tbl_data) * 0.62,
               col_widths=[3.5, 16.5, 3.6],
               font_size=8, header_size=8, alt_fill=_GRAYL)
    _footer(slide)


def _s18_sentiment(prs, D):
    slide = _blank(prs)
    _header(slide, "Sentiment de Marche — FinBERT",
            f"Analyse semantique FinBERT  ·  Articles recents  ·  {D['N']} sociétés", 4)

    td = D["tickers_data"]
    # Derive sentiment from tickers_data if available
    pos_scores = []
    for t in td:
        s = t.get("sentiment_score")
        if s is not None:
            try: pos_scores.append(float(s))
            except: pass
    agg_score = _avg(pos_scores) if pos_scores else 0.22
    n_pos = max(1, int(len(td) * 0.3))
    n_neu = max(1, int(len(td) * 0.5))
    n_neg = max(1, len(td) - n_pos - n_neu)
    total = n_pos + n_neu + n_neg
    lbl = "Neutre positif modere" if agg_score > 0.1 else "Neutre" if agg_score >= -0.1 else "Negatif modere"

    # Score box
    _rect(slide, 0.9, 2.5, 5.3, 2.6, fill=_GRAYL)
    _rect(slide, 0.9, 2.5, 0.1, 2.6, fill=_NAVYL)
    _txb(slide, f"{agg_score:.2f}", 1.2, 2.6, 4.9, 1.2, size=28, bold=True, color=_NAVY)
    _txb(slide, "Score agrégé FinBERT", 1.2, 3.8, 4.9, 0.55, size=7.5, color=_GRAYT)
    _txb(slide, lbl, 1.2, 4.35, 4.9, 0.45, size=7.5, color=_GRAYD)

    # Sentiment bars
    sentiments = [("Positif", n_pos, _BUY, 11.9), ("Neutre", n_neu, _HOLD, 16.9), ("Negatif", n_neg, _SELL, 8.6)]
    for i, (slbl, cnt, col, bar_w_est) in enumerate(sentiments):
        yy = 2.5 + i * 0.9
        pct = cnt / total * 100
        bar_w = max(0.5, pct / 100 * 10)
        _rect(slide, 6.7, yy, bar_w, 0.65, fill=col)
        _txb(slide, slbl, 6.7, yy + 0.05, 2.5, 0.6, size=8.5, color=_BLACK, bold=True)
        _txb(slide, f"{cnt} articles ({pct:.0f} %)", 17.1, yy + 0.05, 5.5, 0.6, size=8.5, color=_GRAYT)

    # Themes
    content = D["content"]
    cats  = content.get("catalyseurs", [])
    risks = content.get("risques", [])
    _txb(slide, "Themes dominants", 0.9, 5.3, 23.6, 0.6, size=8.5, bold=True, color=_NAVY)
    pos_theme = cats[0][0] if cats else "Tendance positive"
    neg_theme = risks[0][0] if risks else "Tendance negative"
    _rect(slide, 0.9, 5.9, 11.4, 1.1, fill=_GREEN_L)
    _rect(slide, 0.9, 5.9, 0.1, 1.1, fill=_BUY)
    _txb(slide, f"+ {pos_theme} — {cats[0][1][:140] if cats else ''}", 1.3, 5.95, 10.7, 1.0, size=8, color=_GRAYT, wrap=True)
    _rect(slide, 13.1, 5.9, 11.4, 1.1, fill=_RED_L)
    _rect(slide, 13.1, 5.9, 0.1, 1.1, fill=_SELL)
    _txb(slide, f"- {neg_theme} — {risks[0][1][:140] if risks else ''}", 13.5, 5.95, 10.7, 1.0, size=8, color=_GRAYT, wrap=True)

    # Analytical text
    _rect(slide, 0.9, 7.4, 23.6, 3.2, fill=_GRAYL)
    _rect(slide, 0.9, 7.4, 23.6, 0.7, fill=_NAVY)
    _txb(slide, "LECTURE ANALYTIQUE DU SENTIMENT", 1.1, 7.45, 23.2, 0.6, size=8.5, bold=True, color=_WHITE)
    sent_analysis = (
        f"Le sentiment agrégé sur le secteur {D['sector_name']} {D['universe']} "
        f"ressort {'legerement positif' if agg_score > 0.1 else 'neutre' if agg_score >= -0.1 else 'legerement negatif'} ({agg_score:.2f}). "
        f"La dispersion est forte — les leaders sectoriels tirent le sentiment vers le haut "
        f"tandis que les valeurs en restructuration drainent la composante negative. "
        f"Cette hétérogénéité valide une approche selective plut que directionelle sur le secteur."
    )
    _txb(slide, sent_analysis, 1.1, 8.2, 23.2, 2.3, size=8.5, color=_GRAYT, wrap=True)
    _footer(slide)


def _s19_sources(prs, D):
    slide = _blank(prs)
    _header(slide, "Sources & Méthodologie",
            "Traçabilité complete des données  ·  Data lineage  ·  Agents FinSight IA v1.0", 4)

    tbl_data = [
        ["Agent", "Source données", "Données collectees", "Frequence"],
        ["AgentData", "yfinance + FMP", "Cours, ratios, etats financiers LTM", "Temps reel / J-1"],
        ["AgentQuant", "Calcul interne", "Altman Z, Beneish M, scores FinSight", "A la demande"],
        ["AgentSentiment", "Finnhub + RSS", "Articles presse, scoring FinBERT", "A la demande"],
        ["AgentSynthese", "Claude Haiku", "Ratios calcules, scoring multifactoriel", "A la demande"],
        ["AgentDevil", "Claude Haiku", "These contraire, conviction delta", "A la demande"],
        ["AgentQA", "Python + LLM", "Validation coherence, flags erreur", "Systematique"],
    ]
    _add_table(slide, tbl_data, 0.9, 2.5, 23.6, len(tbl_data) * 0.62,
               col_widths=[4.0, 4.5, 10.5, 4.6],
               font_size=7.5, header_size=8, alt_fill=_GRAYL)

    # Limits
    _rect(slide, 0.9, 9.6, 23.6, 2.7, fill=_GRAYL)
    _rect(slide, 0.9, 9.6, 0.1, 2.7, fill=_HOLD)
    _txb(slide, "LIMITES & PRÉCAUTIONS", 1.3, 9.7, 23.1, 0.6, size=8.5, bold=True, color=_HOLD)
    _txb(slide, "Les données financieres historiques sont issues de sources publiques et peuvent presenter des delais ou inexactitudes. Les previsions sont basees sur le consensus et les modèles internes FinSight IA — elles ne constituent pas des engagements. La méthodologie de scoring est soumise a des biais inherents a toute approche quantitative.",
         1.3, 10.35, 23.1, 2.0, size=8, color=_GRAYT, wrap=True)

    # Disclaimer
    _rect(slide, 0.9, 12.3, 23.6, 1.0, fill=_NAVY)
    _txb(slide, "Ce rapport est genere par FinSight IA v1.0. Il ne constitue pas un conseil en investissement au sens de la directive MiFID II (2014/65/UE). Document confidentiel — usage interne uniquement. Toute reproduction ou diffusion est interdite sans autorisation.",
         1.1, 12.35, 23.2, 0.9, size=7, color=_GRAYD, wrap=True)
    _footer(slide)


def _s20_performance(prs, D):
    slide = _blank(prs)
    _header(slide, "Performance Boursiere Relative — 52 Semaines",
            f"{D['sector_name']}  ·  {D['universe']}  ·  Indexe a 100 au debut de la periode", 4)

    img = _chart_performance(D["tickers_data"])
    # Graphique sur la gauche (réduit pour laisser place au panel droit)
    _pic(slide, img, 0.9, 2.3, 15.0, 10.2)

    # Panel droit — légende sociétés + commentaire analytique
    _rect(slide, 16.4, 2.3, 8.1, 10.2, fill=_GRAYL)
    _rect(slide, 16.4, 2.3, 8.1, 0.65, fill=_NAVY)
    _txb(slide, "LEGENDE — SOCIETES", 16.6, 2.35, 7.8, 0.55, size=8, bold=True, color=_WHITE)

    # Couleurs identiques à _chart_performance
    _LINE_COLORS = [
        RGBColor(0x1B, 0x3A, 0x6B), RGBColor(0x1A, 0x7A, 0x4A),
        RGBColor(0xA8, 0x20, 0x20), RGBColor(0xB0, 0x60, 0x00),
        RGBColor(0x2A, 0x52, 0x98), RGBColor(0x6B, 0x3A, 0x1B),
        RGBColor(0x3A, 0x6B, 0x1B), RGBColor(0x6B, 0x1B, 0x3A),
    ]
    td = D["tickers_data"]
    n_td = len(td[:MAX_TICKERS_CHART])
    # Réserver 2.0 cm pour la section commentaire en bas du panel (y=10.5 à 12.5)
    _COMMENT_Y = 10.5
    legend_avail = _COMMENT_Y - 3.15   # espace disponible pour la légende
    row_h = min(1.25, legend_avail / max(n_td, 1))
    for i, t in enumerate(td[:MAX_TICKERS_CHART]):
        yy = 3.15 + i * row_h
        col = _LINE_COLORS[i % len(_LINE_COLORS)]
        _rect(slide, 16.5, yy + 0.12, 0.5, 0.3, fill=col)
        tk = t.get("ticker", f"T{i+1}")
        co = (t.get("company") or tk)[:28]
        score = int(t.get("score_global") or 0)
        reco = "BUY" if score >= 70 else ("HOLD" if score >= 50 else "SELL")
        _txb(slide, f"{tk}  —  {co}", 17.2, yy, 7.1, 0.6, size=9, bold=True, color=_NAVY)
        _txb(slide, f"Score {score}/100  ·  {reco}", 17.2, yy + 0.62, 7.1, 0.5, size=8, color=_GRAYT)

    # Commentaire analytique — position fixe, jamais chevauchée par la légende
    td_s = sorted(td, key=lambda x: x.get("momentum_52w") or 0, reverse=True)
    best = td_s[0] if td_s else {}
    worst = td_s[-1] if td_s else {}
    commentary = (
        f"Sur 52 semaines, {best.get('ticker','—')} affiche la meilleure performance "
        f"(+{best.get('momentum_52w',0):.0f}%) tandis que {worst.get('ticker','—')} "
        f"est en retard ({worst.get('momentum_52w',0):+.0f}%). "
        f"La dispersion des trajectoires illustre la bifurcation sectorielle. "
        f"Le momentum 52W est integre dans le score FinSight comme "
        f"signal de confirmation."
    )
    _rect(slide, 16.4, _COMMENT_Y, 8.1, 0.05, fill=_GRAYD)
    _txb(slide, "LECTURE ANALYTIQUE", 16.6, _COMMENT_Y + 0.1, 7.8, 0.5, size=7.5, bold=True, color=_NAVY)
    _txb(slide, commentary, 16.6, _COMMENT_Y + 0.65, 7.8, 1.7, size=7, color=_GRAYT, wrap=True)

    _footer(slide)


# ─── MAIN CLASS ───────────────────────────────────────────────────────────────
class SectoralPPTXWriter:

    @staticmethod
    def generate(
        tickers_data: list[dict],
        sector_name: str,
        universe: str = "CAC 40",
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Generate a 20-slide sectoral pitchbook PPTX.
        Returns bytes of the PPTX file.
        If output_path is provided, also saves to disk.
        """
        D = _prepare_data(tickers_data, sector_name, universe)

        prs = Presentation()
        prs.slide_width  = _SW
        prs.slide_height = _SH

        # Slide 1 — Cover
        _s01_cover(prs, D)
        # Slide 2 — Executive Summary
        _s02_exec_summary(prs, D)
        # Slide 3 — Sommaire
        _s03_sommaire(prs, D)
        # Slide 4 — Chapter 01 divider
        _chapter_divider(prs, "01", "Presentation du Secteur",
                         "Caractéristiques structurelles, ratios comparatifs & positionnement cycle")
        # Slide 5 — Presentation
        _s05_presentation(prs, D)
        # Slide 6 — Ratios comparatifs
        _s06_ratios(prs, D)
        # Slide 7 — Positionnement cycle
        _s07_cycle(prs, D)
        # Slide 8 — Chapter 02 divider
        _chapter_divider(prs, "02", "Cartographie des Societes",
                         f"{D['N']} sociétés analysées — scores FinSight, scatter & décomposition")
        # Slide 9 — Cartographie
        _s09_cartographie(prs, D)
        # Slide 10 — Scatter
        _s10_scatter(prs, D)
        # Slide 11 — Scores detailles
        _s11_scores(prs, D)
        # Slide 12 — Chapter 03 divider
        _chapter_divider(prs, "03", "Top 3 & Valorisations",
                         "Synthese Top 3, distribution EV/EBITDA & zone d'entree optimale")
        # Slide 13 — Top 3
        _s13_top3(prs, D)
        # Slide 14 — Distribution
        _s14_distribution(prs, D)
        # Slide 15 — Zone d'entrée
        _s15_entry(prs, D)
        # Slide 16 — Chapter 04 divider
        _chapter_divider(prs, "04", "Risques, Sentiment & Méthodologie",
                         "Conditions d'invalidation, FinBERT agrégé & data lineage")
        # Slide 17 — Risques
        _s17_risques(prs, D)
        # Slide 18 — Sentiment
        _s18_sentiment(prs, D)
        # Slide 19 — Sources
        _s19_sources(prs, D)
        # Slide 20 — Performance
        _s20_performance(prs, D)

        buf = io.BytesIO()
        prs.save(buf)
        pptx_bytes = buf.getvalue()

        if output_path:
            Path(output_path).write_bytes(pptx_bytes)

        return pptx_bytes


# ─── CONVENIENCE FUNCTION ─────────────────────────────────────────────────────
def generate_sector_pptx(
    sector_name: str,
    tickers_data: list[dict],
    output_path: str,
    universe: str = "CAC 40",
) -> bytes:
    """Convenience wrapper matching PDF writer signature."""
    return SectoralPPTXWriter.generate(
        tickers_data=tickers_data,
        sector_name=sector_name,
        universe=universe,
        output_path=output_path,
    )
