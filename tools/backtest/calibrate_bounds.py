"""calibrate_bounds.py — Calibration des bornes Score FinSight sur quartiles réels.

Problème : `_scale(roic, 0.05, 0.30)` et autres bornes hardcodées ne reflètent
pas la distribution réelle des ratios. Résultat observable : bucket E (<35)
absorbe 73% des tickers sp100 sur 10 ans = distribution écrasée.

Solution : pour chaque (ratio, secteur), calculer les quartiles Q10/Q25/Q50/
Q75/Q90 réellement observés sur un large univers (sp100+euro40+autres).
Ces quartiles servent de bornes à `_scale()` à la place de valeurs arbitraires.

Principe :
  _scale(roic, q10_sector, q90_sector, 8 pts)
  → bucket 10% le plus faible = 0 pt, 10% le plus fort = 8 pts, linéaire au
  milieu. Distribution naturellement étalée.

Output : JSON `outputs/backtest/sector_bounds.json` mappant :
  {
    "Technology": {
      "pe_ratio": {"low": 8, "high": 50, "q25": 18, "q75": 35},
      "roic":     {"low": 0.05, "high": 0.40, "q25": 0.12, "q75": 0.30},
      ...
    },
    "_default": {...},   // moyenne tous secteurs
  }

Compute_score lit ce JSON au démarrage et utilise les quartiles comme bornes.

Usage :
    python -m tools.backtest.calibrate_bounds --universe sp100
"""
from __future__ import annotations
import sys
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd

from core.yfinance_cache import get_ticker
from tools.backtest.fetch_history import get_universe, OUT_DIR

log = logging.getLogger(__name__)


# Ratios à calibrer + bornes "absolues" pour filtrer les outliers
_RATIOS = {
    "pe_ratio":        {"min": 0, "max": 200, "invert": True},   # faible = meilleur
    "ev_ebitda":       {"min": 0, "max": 100, "invert": True},
    "ev_revenue":      {"min": 0, "max": 50,  "invert": True},
    "fcf_yield":       {"min": -0.10, "max": 0.20, "invert": False},
    "roic":            {"min": -0.20, "max": 0.80, "invert": False},  # décimal
    "roe":             {"min": -0.50, "max": 2.0, "invert": False},
    "net_margin":      {"min": -0.50, "max": 0.50, "invert": False},
    "ebitda_margin":   {"min": -0.20, "max": 0.80, "invert": False},
    "gross_margin":    {"min": -0.20, "max": 1.0, "invert": False},
    "revenue_growth":  {"min": -0.50, "max": 1.0, "invert": False},
    "net_debt_ebitda": {"min": -5.0, "max": 15.0, "invert": True},
    "altman_z":        {"min": -5, "max": 15, "invert": False},
    "momentum_52w":    {"min": -1.0, "max": 3.0, "invert": False},
    "payout_ratio":    {"min": 0.0, "max": 2.0, "invert": False},
    "div_yield":       {"min": 0.0, "max": 0.15, "invert": False},
}


def _fetch_snapshot(ticker: str) -> dict | None:
    """Fetch snapshot actuel d'un ticker (info + ratios calculés)."""
    try:
        tk = get_ticker(ticker)
        info = tk.info or {}
        if not info.get("marketCap"):
            return None
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding")
        mcap = info.get("marketCap")
        sector = info.get("sector", "Unknown")

        def _margin(key):
            v = info.get(key)
            if v is None:
                return None
            return float(v) if abs(float(v)) < 2 else float(v) / 100.0

        return {
            "ticker": ticker,
            "sector": sector,
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ev_revenue": info.get("enterpriseToRevenue"),
            "fcf_yield": (info.get("freeCashflow") / mcap) if (info.get("freeCashflow") and mcap) else None,
            "roic": _margin("returnOnEquity"),  # proxy (yfinance ne publie pas ROIC direct)
            "roe": _margin("returnOnEquity"),
            "net_margin": _margin("profitMargins"),
            "ebitda_margin": _margin("ebitdaMargins"),
            "gross_margin": _margin("grossMargins"),
            "revenue_growth": _margin("revenueGrowth"),
            "net_debt_ebitda": (info.get("totalDebt", 0) - info.get("totalCash", 0)) / info.get("ebitda", 1)
                                if info.get("ebitda") and info.get("ebitda") > 0 else None,
            "momentum_52w": _margin("52WeekChange"),
            "payout_ratio": _margin("payoutRatio"),
            "div_yield": _margin("dividendYield"),
        }
    except Exception as e:
        log.debug(f"[calibrate] {ticker} fail: {e}")
        return None


def fetch_universe_snapshots(universe: str = "sp100",
                              max_workers: int = 8) -> list[dict]:
    """Parallel fetch. Retourne liste de snapshots."""
    tickers = get_universe(universe)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_snapshot, tk): tk for tk in tickers}
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results.append(r)
    return results


def compute_quantiles(snapshots: list[dict]) -> dict:
    """Calcule Q10/Q25/Q50/Q75/Q90 par (secteur, ratio)."""
    df = pd.DataFrame(snapshots)
    if len(df) == 0:
        return {}

    # Groupes : par secteur + global
    sectors = df["sector"].dropna().unique().tolist()
    out = {}

    for sector in sectors + ["_default"]:
        sub = df if sector == "_default" else df[df["sector"] == sector]
        if len(sub) < 5:    # pas assez de données par secteur, skip
            continue
        out[sector] = {}
        for ratio, spec in _RATIOS.items():
            vals = sub[ratio].dropna()
            # Outlier filter
            vals = vals[(vals >= spec["min"]) & (vals <= spec["max"])]
            if len(vals) < 3:
                continue
            q = np.quantile(vals.values, [0.10, 0.25, 0.50, 0.75, 0.90])
            out[sector][ratio] = {
                "q10": float(round(q[0], 4)),
                "q25": float(round(q[1], 4)),
                "q50": float(round(q[2], 4)),
                "q75": float(round(q[3], 4)),
                "q90": float(round(q[4], 4)),
                "n": int(len(vals)),
            }

    return out


def run(universe: str = "sp100") -> dict:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log.info(f"[calibrate] fetching {universe} snapshots...")
    snapshots = fetch_universe_snapshots(universe)
    log.info(f"[calibrate] {len(snapshots)} snapshots valides")

    q = compute_quantiles(snapshots)
    out_path = OUT_DIR / "sector_bounds.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(q, f, indent=2, default=str)
    log.info(f"[calibrate] saved {out_path.name} ({len(q)} secteurs)")

    # Récap
    log.info("\n═══ QUARTILES PAR SECTEUR — aperçu ═══")
    for sector, ratios in q.items():
        if sector == "_default":
            continue
        pe = ratios.get("pe_ratio", {})
        roic = ratios.get("roic", {})
        log.info(f"  {sector[:25]:<25} | P/E q25={pe.get('q25')} q75={pe.get('q75')} "
                 f"| ROIC q25={roic.get('q25')} q75={roic.get('q75')} (n={pe.get('n', 0)})")

    return q


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="sp100")
    args = ap.parse_args()
    run(args.universe)
