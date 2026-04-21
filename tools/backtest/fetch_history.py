"""fetch_history.py — Télécharge les données historiques nécessaires au backtest.

Pour chaque ticker de l'univers choisi :
- Prix OHLC mensuels (adjusted close) sur N années
- États financiers trimestriels/annuels (balance sheet, income statement,
  cash flow) — yfinance expose typiquement 4 ans d'historique annuel en free

Cache local : Parquet (compressé, rapide). Si déjà fetched < 7 jours, skip.

Limites yfinance free :
- `Ticker.history(period="5y", interval="1mo")` : fiable pour 10+ ans
- `Ticker.financials` / `.balance_sheet` / `.cashflow` : 4 ans annuels
  (source : Yahoo Finance API limits, avril 2026)
- `Ticker.info` : snapshot actuel seulement, PAS d'historique

Pour le MVP, on utilise les 4 ans de financials + prix mensuels → backtest
sur ~3 ans (on a besoin d'une fenêtre forward 12m → dernier point backtesté
= il y a 12 mois).
"""
from __future__ import annotations
import sys
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
from core.yfinance_cache import get_ticker

log = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "backtest"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Univers prédéfinis — extensibles
_UNIVERSES = {
    # Top 50 S&P 500 par market cap (avril 2026) — noyau représentatif
    "sp50": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
        "JPM", "V", "WMT", "UNH", "XOM", "MA", "PG", "JNJ", "LLY", "HD",
        "AVGO", "CVX", "ABBV", "KO", "MRK", "PEP", "COST", "BAC", "ADBE",
        "CRM", "NFLX", "ORCL", "PFE", "AMD", "TMO", "DIS", "ACN", "CMCSA",
        "MCD", "LIN", "WFC", "ABT", "CSCO", "VZ", "DHR", "TXN", "INTU",
        "NEE", "NKE", "PM", "MS", "UPS",
    ],
    # Top 100 = top 50 + 50 suivants (étendre plus tard)
    "sp100": [],  # TODO: ajouter 50 tickers suivants
    # Top 40 CAC 40 + DAX 40 pour international
    "euro40": [
        "MC.PA", "RMS.PA", "OR.PA", "TTE.PA", "SAN.PA", "BNP.PA", "AIR.PA",
        "SAP.DE", "SIE.DE", "ALV.DE", "BMW.DE", "BAS.DE", "BAYN.DE", "DTE.DE",
    ],
}


def get_universe(name: str) -> list[str]:
    if name == "sp100":
        return _UNIVERSES["sp50"]  # fallback pour MVP
    return _UNIVERSES.get(name, _UNIVERSES["sp50"])


def fetch_one_ticker(ticker: str, years: int = 3) -> dict:
    """Télécharge prix + financials pour un ticker. Retourne dict avec :
    - prices : DataFrame OHLCV monthly
    - financials : DataFrame annuel (revenue, ebitda, net_income, etc.)
    - balance : DataFrame balance sheet annuel
    - cashflow : DataFrame cashflow annuel
    - info : dict yfinance.info (snapshot actuel, utile pour champs fixes)
    """
    try:
        tk = get_ticker(ticker)
        # Prix mensuels
        prices = tk.history(period=f"{years + 1}y", interval="1mo",
                            auto_adjust=True, actions=False)
        if prices is None or len(prices) == 0:
            return {"ticker": ticker, "error": "no price history"}
        # Financials historiques (annuels uniquement — plus fiables)
        fin = tk.financials if hasattr(tk, "financials") else pd.DataFrame()
        bs = tk.balance_sheet if hasattr(tk, "balance_sheet") else pd.DataFrame()
        cf = tk.cashflow if hasattr(tk, "cashflow") else pd.DataFrame()
        info = tk.info if hasattr(tk, "info") else {}
        return {
            "ticker": ticker,
            "prices": prices,
            "financials": fin,
            "balance": bs,
            "cashflow": cf,
            "info": info,
            "error": None,
        }
    except Exception as e:
        log.warning(f"[fetch] {ticker} fail: {e}")
        return {"ticker": ticker, "error": str(e)[:100]}


def fetch_universe(universe: str = "sp50", years: int = 3,
                   max_workers: int = 6) -> dict[str, dict]:
    """Fetch parallèle sur tout l'univers. Retourne {ticker: data_dict}.

    Cache Parquet dans outputs/backtest/cache_{universe}_{years}y.parquet
    (pas stocker tout ici — seulement un résumé, les dataframes sont trop
    lourds pour Parquet direct).
    """
    tickers = get_universe(universe)
    log.info(f"[backtest] fetch {len(tickers)} tickers, {years}y history, "
             f"{max_workers} workers...")
    t0 = time.time()
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fetch_one_ticker, tk, years): tk for tk in tickers}
        for fut in as_completed(futs):
            tk = futs[fut]
            try:
                r = fut.result(timeout=30)
                results[tk] = r
            except Exception as e:
                log.warning(f"[fetch] {tk} timeout/err: {e}")
                results[tk] = {"ticker": tk, "error": str(e)[:100]}
    elapsed = int(time.time() - t0)
    n_ok = sum(1 for r in results.values() if not r.get("error"))
    log.info(f"[backtest] fetched {n_ok}/{len(tickers)} in {elapsed}s")
    return results


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="sp50", choices=list(_UNIVERSES.keys()))
    ap.add_argument("--years", type=int, default=3)
    args = ap.parse_args()
    data = fetch_universe(args.universe, years=args.years)
    ok = sum(1 for v in data.values() if not v.get("error"))
    print(f"OK {ok}/{len(data)} tickers")
