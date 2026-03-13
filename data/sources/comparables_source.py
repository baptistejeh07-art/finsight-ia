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
    "MC.PA":   ["KER.PA", "OR.PA", "RI.PA", "CFR.SW", "BURBY"],
    "KER.PA":  ["MC.PA", "CFR.SW", "PRDSY", "BURBY", "TAPESTRY"],
    "OR.PA":   ["LVMUY", "COTY", "PRGO", "EL", "UL"],
    "AMZN":    ["BABA", "JD", "WMT", "TGT", "EBAY"],
    "TSLA":    ["GM", "F", "STLA.MI", "BMW.DE", "VOW3.DE"],
    "NKE":     ["ADDYY", "UAA", "PUMA.DE", "SKX", "VFC"],
    "MCD":     ["QSR", "YUM", "SBUX", "DPZ", "CMG"],
    # --- Energy ---
    "XOM":     ["CVX", "TTE.PA", "SHEL.L", "BP.L", "ENI.MI"],
    "CVX":     ["XOM", "TTE.PA", "SHEL.L", "BP.L", "COP"],
    "TTE.PA":  ["XOM", "SHEL.L", "BP.L", "ENI.MI", "REP.MC"],
    "BP.L":    ["SHEL.L", "TTE.PA", "XOM", "ENI.MI", "REP.MC"],
    # --- Industrials ---
    "CAT":     ["DE", "CMI", "PCAR", "CNH", "AGCO"],
    "HON":     ["GE", "MMM", "EMR", "ITW", "PH"],
    "GE":      ["HON", "SIE.DE", "ABB.ST", "ETN", "PH"],
    "AIR.PA":  ["BA", "LMT", "RTX", "GD", "NOC"],
    "SIE.DE":  ["ABB.ST", "HON", "GE", "PHG.AS", "ROK"],
    # --- Telecom ---
    "ORA.PA":  ["DTE.DE", "BT-A.L", "TEF.MC", "TIT.MI", "TELIA.ST"],
    "DTE.DE":  ["ORA.PA", "BT-A.L", "TEF.MC", "TELIA.ST", "TIT.MI"],
    "VZ":      ["T", "TMUS", "DISH", "LUMN", "ATUS"],
    "T":       ["VZ", "TMUS", "DISH", "CHTR", "CMCSA"],
    # --- Real Estate ---
    "AMT":     ["CCI", "SBAC", "DLR", "EQIX", "VICI"],
    "PLD":     ["DRE", "EGP", "STAG", "FR", "REXR"],
}

# Fallback : peers par secteur yfinance generiques
PEERS_BY_SECTOR: dict[str, list[str]] = {
    "Technology":             ["MSFT", "AAPL", "GOOG", "NVDA", "META"],
    "Healthcare":             ["JNJ", "PFE", "ABBV", "MRK", "LLY"],
    "Financial Services":     ["JPM", "BAC", "GS", "MS", "BLK"],
    "Financials":             ["JPM", "BAC", "GS", "MS", "BLK"],
    "Consumer Cyclical":      ["AMZN", "TSLA", "MCD", "NKE", "BKNG"],
    "Consumer Defensive":     ["WMT", "PG", "KO", "PEP", "COST"],
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
    share_price:  Optional[float] = None   # USD/sh
    ev:           Optional[float] = None   # $M
    revenue_ltm:  Optional[float] = None   # $M
    ebitda_ltm:   Optional[float] = None   # $M
    eps_ltm:      Optional[float] = None   # USD/sh
    ebitda_growth_ntm: Optional[float] = None  # % (souvent indispo en free tier)
    fetch_ok:     bool = False


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
    """Collecte les donnees d'un seul peer via yfinance."""
    try:
        import yfinance as yf
        info = yf.Ticker(peer_ticker).info

        name  = info.get("longName") or info.get("shortName") or peer_ticker
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        ev_raw    = info.get("enterpriseValue")
        rev_raw   = info.get("totalRevenue")
        ebitda_raw = info.get("ebitda")
        eps       = info.get("trailingEps")

        def _m(v):
            """Convertit en millions, arrondi."""
            if v is None:
                return None
            return round(v / 1_000_000, 2)

        return PeerData(
            ticker=peer_ticker,
            name=name,
            share_price=round(float(price), 2) if price else None,
            ev=_m(ev_raw),
            revenue_ltm=_m(rev_raw),
            ebitda_ltm=_m(ebitda_raw),
            eps_ltm=round(float(eps), 2) if eps else None,
            fetch_ok=True,
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
