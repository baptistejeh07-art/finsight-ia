# -*- coding: utf-8 -*-
"""
core/sector_etfs.py — Matrice des ETF sectoriels par zone geographique.

FinSight IA s'appuie sur les ETF sectoriels comme objet d'analyse sectorielle
plutot que sur des baskets de whitelist. Ce module mappe chaque (secteur, zone)
vers le ticker ETF de reference.

Deux familles d'ETF :
- **US (S&P 500)** : SPDR Select Sector (11 ETF, un par secteur GICS)
- **Europe (STOXX 600)** : iShares STOXX Europe 600 Sector UCITS (19 ETF)

Les univers europeens (CAC 40, DAX 40, FTSE 100, AEX, IBEX, MIB...) partagent
tous les ETF STOXX 600 europeens parce qu'il n'existe pas d'ETF sectoriel
restreint a un seul indice national. Un rapport sectoriel pour "Banques DAX 40"
utilise donc le meme ETF EXV1.DE qu'un rapport "Banques CAC 40".

Usage typique :

    from core.sector_etfs import get_etf_for, ZONE_US, ZONE_EUROPE

    etf = get_etf_for("Technology", universe="S&P 500")
    # -> {"ticker": "XLK", "name": "Technology Select Sector SPDR", "zone": "US"}

    etf = get_etf_for("Banks", universe="DAX 40")
    # -> {"ticker": "EXV1.DE", "name": "iShares STOXX Europe 600 Banks", "zone": "EU"}
"""
from __future__ import annotations


# ═════════════════════════════════════════════════════════════════════════════
# ZONES & UNIVERS
# ═════════════════════════════════════════════════════════════════════════════

ZONE_US     = "US"
ZONE_EUROPE = "EU"
ZONE_GLOBAL = "GLOBAL"   # NEW #168 : couverture monde via iShares Global Sector ETF

# Mapping univers (nom humain tel que saisi par l'utilisateur) -> zone ETF
_UNIVERSE_TO_ZONE: dict[str, str] = {
    # US
    "s&p 500":  ZONE_US,
    "sp500":    ZONE_US,
    "sp 500":   ZONE_US,
    "s&p500":   ZONE_US,
    "nasdaq":   ZONE_US,
    "nasdaq 100": ZONE_US,
    "dow jones": ZONE_US,
    "russell 1000": ZONE_US,
    "russell 2000": ZONE_US,
    # Europe (tous les indices nationaux europeens -> STOXX 600 ETF)
    "cac 40":   ZONE_EUROPE,
    "cac40":    ZONE_EUROPE,
    "dax 40":   ZONE_EUROPE,
    "dax40":    ZONE_EUROPE,
    "dax":      ZONE_EUROPE,
    "ftse 100": ZONE_EUROPE,
    "ftse100":  ZONE_EUROPE,
    "aex":      ZONE_EUROPE,
    "aex 25":   ZONE_EUROPE,
    "ibex 35":  ZONE_EUROPE,
    "ibex35":   ZONE_EUROPE,
    "mib":      ZONE_EUROPE,
    "ftse mib": ZONE_EUROPE,
    "smi":      ZONE_EUROPE,
    "bel 20":   ZONE_EUROPE,
    "atx":      ZONE_EUROPE,
    "omx":      ZONE_EUROPE,
    "omx 30":   ZONE_EUROPE,
    "psi 20":   ZONE_EUROPE,
    "stoxx 600": ZONE_EUROPE,
    "euro stoxx 50": ZONE_EUROPE,
    "eurostoxx 50": ZONE_EUROPE,
    # Global / Monde (NEW #168 : MSCI World sector ETF via iShares)
    "global":       ZONE_GLOBAL,
    "monde":        ZONE_GLOBAL,
    "world":        ZONE_GLOBAL,
    "msci world":   ZONE_GLOBAL,
    "msci acwi":    ZONE_GLOBAL,
    "acwi":         ZONE_GLOBAL,
}


def universe_to_zone(universe: str | None) -> str:
    """Determine la zone ETF (US/EU) a partir du nom d'univers.

    Fallback : US (puisque SPDR couvre le spectre GICS standard et est dispo
    via yfinance partout dans le monde).
    """
    if not universe:
        return ZONE_US
    key = str(universe).strip().lower()
    return _UNIVERSE_TO_ZONE.get(key, ZONE_US)


# ═════════════════════════════════════════════════════════════════════════════
# MATRICE US — SPDR Select Sector (Nasdaq, S&P 500)
# ═════════════════════════════════════════════════════════════════════════════
# Les 11 ETF SPDR couvrent les 11 secteurs GICS classiques.
# Source : https://www.sectorspdr.com/ (publique, issuer ssga.com)

_US_SPDR: dict[str, dict] = {
    # slug interne        : {ticker, name}
    "TECHNOLOGY":       {"ticker": "XLK",  "name": "Technology Select Sector SPDR Fund"},
    "HEALTHCARE":       {"ticker": "XLV",  "name": "Health Care Select Sector SPDR Fund"},
    "FINANCIALS":       {"ticker": "XLF",  "name": "Financial Select Sector SPDR Fund"},
    "BANKS":            {"ticker": "XLF",  "name": "Financial Select Sector SPDR Fund (sous-secteur Banks)"},
    "INSURANCE":        {"ticker": "XLF",  "name": "Financial Select Sector SPDR Fund (sous-secteur Insurance)"},
    "CONSUMERCYCLICAL": {"ticker": "XLY",  "name": "Consumer Discretionary Select Sector SPDR Fund"},
    "CONSUMERDEFENSIVE":{"ticker": "XLP",  "name": "Consumer Staples Select Sector SPDR Fund"},
    "ENERGY":           {"ticker": "XLE",  "name": "Energy Select Sector SPDR Fund"},
    "INDUSTRIALS":      {"ticker": "XLI",  "name": "Industrial Select Sector SPDR Fund"},
    "MATERIALS":        {"ticker": "XLB",  "name": "Materials Select Sector SPDR Fund"},
    "REALESTATE":       {"ticker": "XLRE", "name": "Real Estate Select Sector SPDR Fund"},
    "UTILITIES":        {"ticker": "XLU",  "name": "Utilities Select Sector SPDR Fund"},
    "COMMUNICATION":    {"ticker": "XLC",  "name": "Communication Services Select Sector SPDR Fund"},
}


# ═════════════════════════════════════════════════════════════════════════════
# MATRICE EUROPE — iShares STOXX Europe 600 Sector UCITS (XETRA)
# ═════════════════════════════════════════════════════════════════════════════
# 19 ETF iShares sur Xetra, UCITS, tous avec suffixe .DE pour yfinance.
# Source : www.ishares.com (confirme via WebFetch 2026-04-14).
#
# Note : la classification STOXX 600 a 19 supersecteurs, mais plusieurs
# correspondent au meme secteur GICS (Telecom+Media -> Communication,
# Basic Resources+Chemicals -> Materials, Food+Personal Goods -> Cons Def).
# On selectionne un ETF principal par slug GICS pour la coherence avec l'US.

_EU_ISHARES: dict[str, dict] = {
    "TECHNOLOGY":       {"ticker": "EXV3.DE", "name": "iShares STOXX Europe 600 Technology UCITS ETF"},
    "HEALTHCARE":       {"ticker": "EXV4.DE", "name": "iShares STOXX Europe 600 Health Care UCITS ETF"},
    # Financials famille : 3 ETF distincts (Banks, Insurance, Financial Services)
    "FINANCIALS":       {"ticker": "EXH2.DE", "name": "iShares STOXX Europe 600 Financial Services UCITS ETF"},
    "BANKS":            {"ticker": "EXV1.DE", "name": "iShares STOXX Europe 600 Banks UCITS ETF"},
    "INSURANCE":        {"ticker": "EXH5.DE", "name": "iShares STOXX Europe 600 Insurance UCITS ETF"},
    # Consumer Cyclical : Retail est le plus large des sous-segments UCITS
    "CONSUMERCYCLICAL": {"ticker": "EXH8.DE", "name": "iShares STOXX Europe 600 Retail UCITS ETF"},
    # Consumer Defensive : Food & Beverage est le plus large
    "CONSUMERDEFENSIVE":{"ticker": "EXH3.DE", "name": "iShares STOXX Europe 600 Food & Beverage UCITS ETF"},
    "ENERGY":           {"ticker": "EXH1.DE", "name": "iShares STOXX Europe 600 Oil & Gas UCITS ETF"},
    "INDUSTRIALS":      {"ticker": "EXH4.DE", "name": "iShares STOXX Europe 600 Industrial Goods & Services UCITS ETF"},
    # Materials : Basic Resources (mining) est plus representatif que Chemicals
    "MATERIALS":        {"ticker": "EXV6.DE", "name": "iShares STOXX Europe 600 Basic Resources UCITS ETF"},
    "REALESTATE":       {"ticker": "EXI5.DE", "name": "iShares STOXX Europe 600 Real Estate UCITS ETF"},
    "UTILITIES":        {"ticker": "EXH9.DE", "name": "iShares STOXX Europe 600 Utilities UCITS ETF"},
    # Communication : Telecommunications (plus gros que Media en EU)
    "COMMUNICATION":    {"ticker": "EXV2.DE", "name": "iShares STOXX Europe 600 Telecommunications UCITS ETF"},
}


# ETF europeens secondaires (composition sectorielle complementaire)
# Utilises pour les rapports qui veulent decomposer un secteur ombrelle
_EU_ISHARES_SECONDARY: dict[str, dict] = {
    "CHEMICALS":        {"ticker": "EXV7.DE", "name": "iShares STOXX Europe 600 Chemicals UCITS ETF"},
    "AUTOMOBILES":      {"ticker": "EXV5.DE", "name": "iShares STOXX Europe 600 Automobiles & Parts UCITS ETF"},
    "CONSTRUCTION":     {"ticker": "EXV8.DE", "name": "iShares STOXX Europe 600 Construction & Materials UCITS ETF"},
    "TRAVEL":           {"ticker": "EXV9.DE", "name": "iShares STOXX Europe 600 Travel & Leisure UCITS ETF"},
    "MEDIA":            {"ticker": "EXH6.DE", "name": "iShares STOXX Europe 600 Media UCITS ETF"},
    "PERSONALGOODS":    {"ticker": "EXH7.DE", "name": "iShares STOXX Europe 600 Personal & Household Goods UCITS ETF"},
}


# ═════════════════════════════════════════════════════════════════════════════
# MATRICE GLOBAL / MONDE — iShares Global Sector ETF (NYSE, USD)
# ═════════════════════════════════════════════════════════════════════════════
# NEW #168 : Baptiste a demandé une analyse monde (sans ETF régional dédié).
# Option 2 retenue : MSCI World sector index répliqué via iShares Global sector
# ETF. Ces ETF couvrent ~80% de la capi monde par secteur GICS.
#
# Source : https://www.ishares.com/us/strategies/global-sectors (publique)
# Tickers confirmés dispo via yfinance (tous NYSE/NASDAQ, USD).
#
# Couverture : 10 secteurs GICS principaux. Pas de granularité sur Banks/
# Insurance (utiliser IXG pour Financials ombrelle). Pas de CommServ global
# spécifique (utiliser panier XLC + EXV2 ou fallback IXP).

_GLOBAL_ISHARES: dict[str, dict] = {
    "TECHNOLOGY":       {"ticker": "IXN",  "name": "iShares Global Tech ETF"},
    "HEALTHCARE":       {"ticker": "IXJ",  "name": "iShares Global Healthcare ETF"},
    # Financials monde : IXG couvre Banks + Insurance + Financial Services
    "FINANCIALS":       {"ticker": "IXG",  "name": "iShares Global Financials ETF"},
    "BANKS":            {"ticker": "IXG",  "name": "iShares Global Financials ETF (Banks subset)"},
    "INSURANCE":        {"ticker": "IXG",  "name": "iShares Global Financials ETF (Insurance subset)"},
    # Consumer Discretionary monde : RXI
    "CONSUMERCYCLICAL": {"ticker": "RXI",  "name": "iShares Global Consumer Discretionary ETF"},
    # Consumer Staples monde : KXI
    "CONSUMERDEFENSIVE":{"ticker": "KXI",  "name": "iShares Global Consumer Staples ETF"},
    "ENERGY":           {"ticker": "IXC",  "name": "iShares Global Energy ETF"},
    "INDUSTRIALS":      {"ticker": "EXI",  "name": "iShares Global Industrials ETF"},
    "MATERIALS":        {"ticker": "MXI",  "name": "iShares Global Materials ETF"},
    # Real Estate monde : REET (global REIT)
    "REALESTATE":       {"ticker": "REET", "name": "iShares Global REIT ETF"},
    "UTILITIES":        {"ticker": "JXI",  "name": "iShares Global Utilities ETF"},
    # Communication monde : IXP (Global Telecom historique, plus large que XLC seul)
    "COMMUNICATION":    {"ticker": "IXP",  "name": "iShares Global Comm Services ETF"},
}


# ═════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ═════════════════════════════════════════════════════════════════════════════

def get_etf_for(sector: str, universe: str | None = None,
                zone: str | None = None) -> dict | None:
    """Retourne l'ETF sectoriel de reference pour un (secteur, univers).

    Args:
        sector : nom du secteur (anglais yfinance, FR, slug, alias)
        universe : nom d'indice ("S&P 500", "DAX 40", "CAC 40", "Global"...)
        zone : override explicite de la zone (US/EU/GLOBAL), si fourni ignore universe

    Returns:
        Dict {"ticker", "name", "zone", "slug"} ou None si non reconnu.
    """
    try:
        from core.sector_labels import slug_from_any
    except ImportError:
        return None
    slug = slug_from_any(sector)
    if slug is None:
        return None
    _zone = zone or universe_to_zone(universe)
    if _zone == ZONE_US:
        _matrix = _US_SPDR
    elif _zone == ZONE_EUROPE:
        _matrix = _EU_ISHARES
    elif _zone == ZONE_GLOBAL:
        _matrix = _GLOBAL_ISHARES
    else:
        _matrix = _US_SPDR  # fallback
    entry = _matrix.get(slug)
    if entry is None:
        return None
    return {
        "ticker": entry["ticker"],
        "name":   entry["name"],
        "zone":   _zone,
        "slug":   slug,
    }


def get_all_etfs_for_zone(zone: str) -> list[dict]:
    """Retourne la liste complete des ETF pour une zone donnee (US, EU ou GLOBAL).

    Utile pour construire les listings sectoriels complets (11 ETF US, 13 EU
    mappes aux slugs GICS + 6 EU secondaires, 13 Global mappes).
    """
    if zone == ZONE_US:
        _src = _US_SPDR
    elif zone == ZONE_GLOBAL:
        _src = _GLOBAL_ISHARES
    else:
        _src = _EU_ISHARES
    return [
        {"ticker": v["ticker"], "name": v["name"], "slug": k, "zone": zone}
        for k, v in _src.items()
    ]


def etf_exists(ticker: str) -> bool:
    """True si le ticker est connu dans l'une des matrices (US, EU ou GLOBAL)."""
    all_tickers = {v["ticker"] for v in _US_SPDR.values()}
    all_tickers |= {v["ticker"] for v in _EU_ISHARES.values()}
    all_tickers |= {v["ticker"] for v in _EU_ISHARES_SECONDARY.values()}
    all_tickers |= {v["ticker"] for v in _GLOBAL_ISHARES.values()}
    return ticker in all_tickers


def zone_label_fr(zone: str) -> str:
    """Retourne le libelle francais de la zone pour affichage."""
    if zone == ZONE_US:
        return "Etats-Unis"
    if zone == ZONE_GLOBAL:
        return "Monde"
    return "Europe"


def etf_issuer(zone: str) -> str:
    """Retourne le nom de l'issuer pour une zone donnee."""
    if zone == ZONE_US:
        return "State Street Global Advisors (SPDR)"
    # EU et GLOBAL sont tous les deux iShares / BlackRock
    return "BlackRock (iShares)"
