# =============================================================================
# FinSight IA — Comparables Source
# data/sources/comparables_source.py
#
# Identification des 5 peers + collecte donnees via yfinance.
# Donnees collectees par peer :
#   - Company name, ticker
#   - Share Price ($), Enterprise Value ($M)
#   - Revenue LTM ($M), EBITDA LTM ($M)
#   - EPS LTM ($)
#   (EV/EBITDA, EV/Revenue, P/E = formules Excel — non injectees)
# =============================================================================

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional
from core.yfinance_cache import get_ticker

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Peers par ticker (priorite) — liste des concurrents directs
# ---------------------------------------------------------------------------

PEERS_BY_TICKER: dict[str, list[str]] = {
    # --- Technology ---
    "AAPL":    ["MSFT", "GOOG", "META", "SONY", "SMSNG.KS"],
    "MSFT":    ["AAPL", "GOOG", "ORCL", "SAP.DE", "CRM"],
    "GOOG":    ["META", "MSFT", "AMZN", "BIDU", "SNAP"],
    "META":    ["GOOG", "SNAP", "PINS", "TWTR", "MSFT"],
    "NVDA":    ["AMD", "INTC", "QCOM", "ASML.AS", "TSM"],
    "AMD":     ["NVDA", "INTC", "QCOM", "MU", "MRVL"],
    "INTC":    ["AMD", "NVDA", "QCOM", "MU", "TSM"],
    "ASML.AS": ["NVDA", "AMD", "LRCX", "AMAT", "KLAC"],
    "SAP.DE":  ["ORCL", "MSFT", "CRM", "NOW", "WDAY"],
    "CAP.PA":  ["SAP.DE", "ATOS.PA", "SOFTW.AS", "CGI.TO", "ACN"],
    "STM.PA":  ["NVDA", "AMD", "NXPI", "IFX.DE", "ON"],
    # --- Healthcare ---
    "JNJ":     ["PFE", "ABBV", "MRK", "BMY", "LLY"],
    "PFE":     ["JNJ", "MRK", "ABBV", "AZN", "RHHBY"],
    "LLY":     ["NVO", "ABBV", "JNJ", "PFE", "BMY"],
    "ABBV":    ["JNJ", "PFE", "MRK", "AMGN", "REGN"],
    "SAN.PA":  ["ROG.SW", "NOVN.SW", "AZN", "NVO", "GSK"],
    "ROG.SW":  ["NOVN.SW", "SAN.PA", "AZN", "ABBV", "PFE"],
    "NOVO-B.CO": ["LLY", "SAN.PA", "PFE", "AZN", "ROG.SW"],
    # --- Financials ---
    "JPM":     ["BAC", "WFC", "GS", "MS", "C"],
    "BAC":     ["JPM", "WFC", "C", "USB", "GS"],
    "GS":      ["MS", "JPM", "BAC", "BLK", "BX"],
    "BNP.PA":  ["ACA.PA", "GLE.PA", "DBK.DE", "ING.AS", "BBVA.MC"],
    "ACA.PA":  ["BNP.PA", "GLE.PA", "DBK.DE", "HSBA.L", "ISP.MI"],
    "DBK.DE":  ["CBK.DE", "BNP.PA", "ACA.PA", "HSBA.L", "UBS.SW"],
    "HSBA.L":  ["LLOY.L", "BNP.PA", "ACA.PA", "STAN.L", "BARC.L"],
    # --- Consumer / Luxury ---
    "MC.PA":   ["KER.PA", "OR.PA", "RI.PA", "CFR.SW", "RMS.PA"],
    "KER.PA":  ["MC.PA", "CFR.SW", "RMS.PA", "BURBY", "TAPESTRY"],
    "RMS.PA":  ["MC.PA", "KER.PA", "CFR.SW", "BURBY", "TAPESTRY"],
    "CFR.SW":  ["MC.PA", "RMS.PA", "KER.PA", "BURBY", "TAPESTRY"],
    "OR.PA":   ["EL", "COTY", "UL", "IPAR", "REVLON"],
    "AMZN":    ["BABA", "JD", "WMT", "TGT", "EBAY"],
    "TSLA":    ["GM", "F", "STLA.MI", "BMW.DE", "VOW3.DE"],
    "BMW.DE":  ["VOW3.DE", "MBG.DE", "STLA.MI", "TSLA", "GM"],
    "VOW3.DE": ["BMW.DE", "MBG.DE", "STLA.MI", "TSLA", "GM"],
    "MBG.DE":  ["BMW.DE", "VOW3.DE", "STLA.MI", "TSLA", "GM"],
    "NKE":     ["ADDYY", "UAA", "PUMA.DE", "SKX", "VFC"],
    "ADS.DE":  ["NKE", "PUMA.DE", "UAA", "SKX", "VFC"],
    "PUMA.DE": ["NKE", "ADS.DE", "UAA", "SKX", "VFC"],
    "MCD":     ["QSR", "YUM", "SBUX", "DPZ", "CMG"],
    # --- Energy ---
    "XOM":     ["CVX", "TTE.PA", "SHEL.L", "BP.L", "ENI.MI"],
    "CVX":     ["XOM", "TTE.PA", "SHEL.L", "BP.L", "COP"],
    "TTE.PA":  ["XOM", "SHEL.L", "BP.L", "ENI.MI", "REP.MC"],
    "SHEL.L":  ["BP.L", "TTE.PA", "XOM", "ENI.MI", "REP.MC"],
    "BP.L":    ["SHEL.L", "TTE.PA", "XOM", "ENI.MI", "REP.MC"],
    "ENI.MI":  ["TTE.PA", "SHEL.L", "BP.L", "REP.MC", "OMV.VI"],
    "ENGI.PA": ["IBE.MC", "EDF.PA", "E.ON.DE", "RWE.DE", "VIE.PA"],
    "EDF.PA":  ["ENGI.PA", "IBE.MC", "E.ON.DE", "RWE.DE", "VIE.PA"],
    # --- Industrials ---
    "CAT":     ["DE", "CMI", "PCAR", "CNH", "AGCO"],
    "HON":     ["GE", "MMM", "EMR", "ITW", "PH"],
    "GE":      ["HON", "SIE.DE", "ABB.ST", "ETN", "PH"],
    "AIR.PA":  ["BA", "LMT", "RTX", "GD", "NOC"],
    "SAF.PA":  ["AIR.PA", "MTU.DE", "GE", "RTX", "HON"],
    "SIE.DE":  ["ABB.ST", "HON", "GE", "PHG.AS", "ROK"],
    "DSY.PA":  ["SAP.DE", "DASSAULT", "MSFT", "ADSK", "PTC"],
    "HO.PA":   ["THALES.PA", "BAE.L", "LMT", "GD", "RTX"],
    "AI.PA":   ["LIN", "APD", "ECL", "AKZA.AS", "SHW"],
    # --- Telecom ---
    "ORA.PA":  ["DTE.DE", "BT-A.L", "TEF.MC", "TIT.MI", "TELIA.ST"],
    "DTE.DE":  ["ORA.PA", "BT-A.L", "TEF.MC", "TELIA.ST", "TIT.MI"],
    "VZ":      ["T", "TMUS", "DISH", "LUMN", "ATUS"],
    "T":       ["VZ", "TMUS", "DISH", "CHTR", "CMCSA"],
    # --- Real Estate ---
    "AMT":     ["CCI", "SBAC", "DLR", "EQIX", "VICI"],
    "PLD":     ["DRE", "EGP", "STAG", "FR", "REXR"],
    "URW.PA":  ["SPG", "MAC", "CBL", "KIM", "REG"],
    # --- Consumer Defensive EU ---
    "BN.PA":   ["NESN.SW", "UL", "KHC", "GIS", "CPB"],
    "NESN.SW": ["BN.PA", "UL", "KHC", "GIS", "CPB"],
}

# Fallback : peers par secteur yfinance generiques
PEERS_BY_SECTOR: dict[str, list[str]] = {
    "Technology":             ["MSFT", "AAPL", "GOOG", "NVDA", "META"],
    "Healthcare":             ["JNJ", "PFE", "ABBV", "MRK", "LLY"],
    "Financial Services":     ["JPM", "BAC", "GS", "MS", "BLK"],
    "Financials":             ["JPM", "BAC", "GS", "MS", "BLK"],
    "Consumer Cyclical":      ["MC.PA", "KER.PA", "NKE", "AMZN", "MCD"],
    "Consumer Defensive":     ["WMT", "PG", "KO", "NESN.SW", "BN.PA"],
    "Energy":                 ["XOM", "CVX", "COP", "EOG", "SLB"],
    "Industrials":            ["GE", "HON", "CAT", "DE", "MMM"],
    "Communication Services": ["GOOG", "META", "VZ", "T", "NFLX"],
    "Real Estate":            ["AMT", "PLD", "EQIX", "CCI", "VICI"],
    "Basic Materials":        ["LIN", "APD", "ECL", "SHW", "FCX"],
    "Utilities":              ["NEE", "DUK", "SO", "D", "AEP"],
}


# ---------------------------------------------------------------------------
# Dataclass resultat
# ---------------------------------------------------------------------------

@dataclass
class PeerData:
    ticker:       str
    name:         str
    # Montants monétaires convertis dans la devise cible (EUR par défaut via
    # core.currency.convert()). Refonte #182 Baptiste : avant ce fix, ces
    # champs étaient dans la devise native du peer (USD pour NVDA, GBp pour
    # BRBY.L, CHF pour NESN.SW...), ce qui faisait un tableau COMPARABLES
    # avec 3-5 devises mélangées sans conversion.
    share_price:  Optional[float] = None   # devise cible (EUR défaut)
    ev:           Optional[float] = None   # M€ (devise cible)
    revenue_ltm:  Optional[float] = None   # M€
    ebitda_ltm:   Optional[float] = None   # M€
    eps_ltm:      Optional[float] = None   # devise cible/sh
    ebitda_growth_ntm: Optional[float] = None  # % (ratio sans devise, pas converti)
    fetch_ok:     bool = False
    # Métadonnées FX (pour debug/audit)
    native_currency: Optional[str] = None   # devise d'origine du peer
    target_currency: Optional[str] = None   # devise cible après conversion


# ---------------------------------------------------------------------------
# Identification des peers
# ---------------------------------------------------------------------------

def get_peers(ticker: str, sector: str = "", industry: str = "") -> list[str]:
    """
    Retourne 5 tickers peers.
    Priorite : PEERS_BY_TICKER > PEERS_BY_SECTOR > fallback SP500.
    """
    upper = ticker.upper()

    # 1. Lookup direct par ticker
    peers = PEERS_BY_TICKER.get(upper, [])
    if peers:
        log.info(f"[Comparables] Peers {upper} (dict ticker) : {peers[:5]}")
        return peers[:5]

    # 2. Lookup par secteur yfinance
    for key in [sector, industry]:
        if key and key in PEERS_BY_SECTOR:
            fallback = [p for p in PEERS_BY_SECTOR[key] if p.upper() != upper][:5]
            log.info(f"[Comparables] Peers {upper} (secteur '{key}') : {fallback}")
            return fallback

    # 3. Fallback generique tech
    log.warning(f"[Comparables] Aucun peer trouve pour {upper} — fallback SP500 tech")
    return ["MSFT", "AAPL", "GOOG", "AMZN", "META"]


# ---------------------------------------------------------------------------
# Collecte donnees yfinance par peer
# ---------------------------------------------------------------------------

def _fetch_one(peer_ticker: str) -> PeerData:
    """Collecte les donnees d'un seul peer via yfinance.

    Refonte #182 : tous les montants monétaires (share_price, ev, revenue,
    ebitda, eps) sont convertis dans la devise cible via core.currency.convert()
    — EUR par défaut. La devise native du peer est extraite de `info.currency`
    ou `info.financialCurrency` (priorité à la devise financière de reporting).
    """
    try:
        import yfinance as yf
        from core.currency import convert, get_target_currency

        info = get_ticker(peer_ticker).info or {}

        name  = info.get("longName") or info.get("shortName") or peer_ticker
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        ev_raw    = info.get("enterpriseValue")
        rev_raw   = info.get("totalRevenue")
        ebitda_raw = info.get("ebitda")
        eps       = info.get("trailingEps")

        # Devise native du peer : pour les prix/EPS on utilise `currency`
        # (devise de cotation), pour les totaux IS on préfère
        # `financialCurrency` (devise de reporting comptable, peut différer
        # pour les sociétés cross-listées).
        price_ccy = info.get("currency") or "USD"
        fin_ccy   = info.get("financialCurrency") or price_ccy or "USD"

        target_ccy = get_target_currency()

        def _m(v):
            """Convertit en millions, arrondi."""
            if v is None:
                return None
            return v / 1_000_000

        # Conversion : share_price + eps utilisent price_ccy (cotation)
        # IS totaux utilisent fin_ccy (reporting)
        price_conv  = convert(price, price_ccy, target_ccy) if price is not None else None
        eps_conv    = convert(eps,   price_ccy, target_ccy) if eps   is not None else None
        ev_conv     = convert(_m(ev_raw),     fin_ccy, target_ccy)
        rev_conv    = convert(_m(rev_raw),    fin_ccy, target_ccy)
        ebitda_conv = convert(_m(ebitda_raw), fin_ccy, target_ccy)

        if (price_ccy != target_ccy) or (fin_ccy != target_ccy):
            log.info(
                f"[Comparables] {peer_ticker} converted "
                f"price {price_ccy}→{target_ccy}, is {fin_ccy}→{target_ccy}"
            )

        return PeerData(
            ticker=peer_ticker,
            name=name,
            share_price=round(float(price_conv), 2) if price_conv is not None else None,
            ev=round(float(ev_conv), 2) if ev_conv is not None else None,
            revenue_ltm=round(float(rev_conv), 2) if rev_conv is not None else None,
            ebitda_ltm=round(float(ebitda_conv), 2) if ebitda_conv is not None else None,
            eps_ltm=round(float(eps_conv), 2) if eps_conv is not None else None,
            fetch_ok=True,
            native_currency=fin_ccy,
            target_currency=target_ccy,
        )
    except Exception as e:
        log.warning(f"[Comparables] Erreur fetch {peer_ticker}: {e}")
        return PeerData(ticker=peer_ticker, name=peer_ticker, fetch_ok=False)


def collect_comparables(
    ticker: str,
    sector: str = "",
    industry: str = "",
    max_workers: int = 5,
) -> list[PeerData]:
    """
    Identifie les 5 peers et collecte leurs donnees en parallele.
    Retourne toujours une liste de 5 PeerData (meme si certains ont fetch_ok=False).
    """
    peers = get_peers(ticker, sector, industry)

    results: dict[str, PeerData] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_one, p): p for p in peers}
        for f in as_completed(futures):
            peer = futures[f]
            try:
                results[peer] = f.result()
            except Exception as e:
                log.error(f"[Comparables] Future error {peer}: {e}")
                results[peer] = PeerData(ticker=peer, name=peer, fetch_ok=False)

    # Conserver l'ordre original des peers
    ordered = [results.get(p, PeerData(ticker=p, name=p)) for p in peers]
    ok = sum(1 for p in ordered if p.fetch_ok)
    log.info(f"[Comparables] {ok}/{len(ordered)} peers collectes avec succes")
    return ordered