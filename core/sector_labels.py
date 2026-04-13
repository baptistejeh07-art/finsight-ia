# -*- coding: utf-8 -*-
"""
core/sector_labels.py — Internationalisation des libelles secteurs (FR/EN).

Architecture i18n FinSight (3 couches strictes) :

1. Couche API (yfinance, FMP) : labels anglais standards GICS
   ex: "Technology", "Health Care", "Financial Services"

2. Couche interne (slugs ASCII, dict keys) : majuscules sans espaces
   ex: "TECHNOLOGY", "HEALTHCARE", "FINANCIALS"

3. Couche affichage (UI Streamlit, PPTX, PDF, Excel headers) : francais
   ex: "Technologie", "Sante", "Services Financiers"

Utilisation typique :
    from core.sector_labels import fr_label, slug_from_any, en_label

    # yfinance retourne "Technology" pour AAPL
    display = fr_label("Technology")          # -> "Technologie"

    # User tape "technologie" dans la search bar
    slug = slug_from_any("technologie")       # -> "TECHNOLOGY"

    # Pour appel API yfinance, on a besoin de l'anglais
    en = en_label("TECHNOLOGY")               # -> "Technology"
"""
from __future__ import annotations

# ═════════════════════════════════════════════════════════════════════════════
# MAPPING CANONIQUE — slug interne -> (anglais yfinance, francais affichage)
# ═════════════════════════════════════════════════════════════════════════════

SECTOR_LABELS: dict[str, tuple[str, str]] = {
    # slug              (anglais yfinance,        francais affichage)
    "TECHNOLOGY":       ("Technology",            "Technologie"),
    "HEALTHCARE":       ("Healthcare",            "Sante"),
    # Financial Services split en 3 sous-secteurs metier (profil specifique)
    "BANKS":            ("Financial Services",    "Banques"),
    "INSURANCE":        ("Financial Services",    "Assurance"),
    "FINANCIALS":       ("Financial Services",    "Services Financiers"),
    "CONSUMERCYCLICAL": ("Consumer Cyclical",     "Consommation Cyclique"),
    "CONSUMERDEFENSIVE":("Consumer Defensive",    "Consommation Defensive"),
    "ENERGY":           ("Energy",                "Energie"),
    "INDUSTRIALS":      ("Industrials",           "Industrie"),
    "MATERIALS":        ("Basic Materials",       "Materiaux"),
    "REALESTATE":       ("Real Estate",           "Immobilier"),
    "UTILITIES":        ("Utilities",             "Services Publics"),
    "COMMUNICATION":    ("Communication Services","Telecommunications"),
}

# Variantes alternatives pour la traduction francaise (avec accents UTF-8)
# On utilise la version sans accents dans le mapping principal pour eviter les
# problemes d'encodage Windows cp1252, mais on expose aussi la version
# typographique correcte pour les outputs UTF-8 (PPTX, PDF, app Streamlit).
SECTOR_LABELS_FR_ACCENTED: dict[str, str] = {
    "TECHNOLOGY":       "Technologie",
    "HEALTHCARE":       "Santé",
    "BANKS":            "Banques",
    "INSURANCE":        "Assurance",
    "FINANCIALS":       "Services Financiers",
    "CONSUMERCYCLICAL": "Consommation Cyclique",
    "CONSUMERDEFENSIVE":"Consommation Défensive",
    "ENERGY":           "Énergie",
    "INDUSTRIALS":      "Industrie",
    "MATERIALS":        "Matériaux",
    "REALESTATE":       "Immobilier",
    "UTILITIES":        "Services Publics",
    "COMMUNICATION":    "Télécommunications",
}


# ═════════════════════════════════════════════════════════════════════════════
# ALIAS — toutes les variantes acceptees en input utilisateur
# ═════════════════════════════════════════════════════════════════════════════
# Permet a `slug_from_any()` d'accepter "tech", "Technologie", "TECH", etc.
# La cle est l'input normalise (lower, sans espaces, sans accents).

_ACCENTS_MAP = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _normalize(s: str) -> str:
    """Normalise un input utilisateur : lowercase, sans accents, sans espaces."""
    if not s:
        return ""
    s = s.lower().strip().translate(_ACCENTS_MAP)
    # Supprime espaces, tirets, underscores, "&"
    for ch in (" ", "-", "_", "&", ".", "'"):
        s = s.replace(ch, "")
    return s


# Construction automatique des alias (anglais + francais + variantes)
_RAW_ALIASES: dict[str, list[str]] = {
    "TECHNOLOGY": [
        "technology", "tech", "it", "technologie", "informationtechnology",
    ],
    "HEALTHCARE": [
        "healthcare", "health", "health care", "sante", "santé",
        "medical", "medicament", "pharma", "pharmaceuticals",
    ],
    "FINANCIALS": [
        "financials", "financial", "financialservices", "finance",
        "services financiers",
    ],
    "BANKS": [
        "banques", "banque", "banks", "banking", "bank", "bancor",
        "bancorp", "bnp", "credit agricole",
    ],
    "INSURANCE": [
        "assurance", "assurances", "insurance", "insurer", "insurers",
        "reassurance", "réassurance", "reinsurance",
    ],
    "CONSUMERCYCLICAL": [
        "consumercyclical", "consumer cyclical", "consumer", "discretionary",
        "consumerdiscretionary", "consommation cyclique", "cyclique",
    ],
    "CONSUMERDEFENSIVE": [
        "consumerdefensive", "consumer defensive", "staples", "consumerstaples",
        "consommation defensive", "consommation défensive", "defensive", "défensif",
    ],
    "ENERGY": [
        "energy", "energie", "énergie", "oil", "oilgas", "petrole", "pétrole",
    ],
    "INDUSTRIALS": [
        "industrials", "industrial", "industrie", "industries",
    ],
    "MATERIALS": [
        "materials", "basic materials", "basicmaterials", "materiaux", "matériaux",
        "matieres premieres", "matières premières",
    ],
    "REALESTATE": [
        "realestate", "real estate", "immobilier", "reit", "reits", "foncieres", "foncières",
    ],
    "UTILITIES": [
        "utilities", "utility", "services publics", "publicservices",
    ],
    "COMMUNICATION": [
        "communication", "communications", "communicationservices",
        "communication services", "telecom", "telecommunications", "télécommunications",
        "telco", "telcos", "media", "médias",
    ],
}

# Index inverse pre-calcule pour lookup O(1)
_ALIAS_TO_SLUG: dict[str, str] = {}
for _slug, _aliases in _RAW_ALIASES.items():
    for _a in _aliases:
        _ALIAS_TO_SLUG[_normalize(_a)] = _slug
    # Le slug lui-meme est aussi une cle
    _ALIAS_TO_SLUG[_normalize(_slug)] = _slug


# ═════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ═════════════════════════════════════════════════════════════════════════════

def fr_label(any_label: str, accented: bool = True) -> str:
    """Retourne le libelle francais a afficher pour un secteur.

    Accepte n'importe quelle variante (anglais yfinance, slug interne, alias FR).
    Si non reconnu, retourne l'input tel quel.

    Args:
        any_label: input quelconque ("Technology", "TECHNOLOGY", "tech", etc.)
        accented: si True (defaut), retourne version avec accents UTF-8
                  ("Technologie", "Énergie"). Si False, version ASCII.
    """
    if not any_label:
        return ""
    slug = slug_from_any(any_label)
    if slug is None:
        return any_label  # passthrough si non reconnu
    if accented:
        return SECTOR_LABELS_FR_ACCENTED.get(slug, SECTOR_LABELS[slug][1])
    return SECTOR_LABELS[slug][1]


def en_label(any_label: str) -> str:
    """Retourne le libelle anglais yfinance pour un secteur.

    Utile pour les appels API ou les filtrages sur des donnees yfinance brutes.
    Accepte slug, francais ou anglais en input.
    """
    if not any_label:
        return ""
    slug = slug_from_any(any_label)
    if slug is None:
        return any_label
    return SECTOR_LABELS[slug][0]


def slug_from_any(any_label: str) -> str | None:
    """Resolve un input utilisateur (FR/EN/slug/alias) vers le slug canonique.

    Retourne None si non reconnu.
    """
    if not any_label:
        return None
    return _ALIAS_TO_SLUG.get(_normalize(any_label))


def is_known_sector(any_label: str) -> bool:
    """True si l'input est reconnu comme un secteur GICS supporte."""
    return slug_from_any(any_label) is not None


def all_slugs() -> list[str]:
    """Liste des 11 slugs GICS supportes."""
    return list(SECTOR_LABELS.keys())


def all_fr_labels(accented: bool = True) -> list[str]:
    """Liste des libelles francais (pour dropdowns Streamlit, etc.)."""
    if accented:
        return [SECTOR_LABELS_FR_ACCENTED[s] for s in SECTOR_LABELS]
    return [SECTOR_LABELS[s][1] for s in SECTOR_LABELS]


# ═════════════════════════════════════════════════════════════════════════════
# SOUS-SECTEURS — slugs qui derivent d'un secteur ombrelle (FINANCIALS...)
# ═════════════════════════════════════════════════════════════════════════════
# Permet de traiter BANKS/INSURANCE comme des analyses dediees :
# - Fetch le pool du secteur ombrelle (Financial Services)
# - Filtre par whitelist de tickers propres au sous-secteur
# - Applique le profil metier correspondant (BANK, INSURANCE...) au lieu de STANDARD

_SUB_SECTOR_UMBRELLA: dict[str, str] = {
    "BANKS":     "FINANCIALS",
    "INSURANCE": "FINANCIALS",
}

# Slug -> profil metier (core/sector_profiles.py) force pour ce sous-secteur
_SUB_SECTOR_PROFILE: dict[str, str] = {
    "BANKS":     "BANK",
    "INSURANCE": "INSURANCE",
}


def is_sub_sector(slug: str) -> bool:
    """True si le slug est un sous-secteur (BANKS/INSURANCE) qui derive d'un ombrelle."""
    return slug in _SUB_SECTOR_UMBRELLA


def umbrella_slug(slug: str) -> str:
    """Retourne le slug ombrelle pour un sous-secteur (BANKS -> FINANCIALS),
    ou le slug lui-meme si ce n'est pas un sous-secteur."""
    return _SUB_SECTOR_UMBRELLA.get(slug, slug)


def forced_profile(slug: str) -> str | None:
    """Retourne le profil metier force (BANK/INSURANCE) pour un sous-secteur,
    ou None si slug standard (profil detecte automatiquement)."""
    return _SUB_SECTOR_PROFILE.get(slug)
