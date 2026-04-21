"""run_backtest.py — Pipeline complet backtest FinSight Score MVP.

1. Fetch univers (fetch_history)
2. Score historique mensuel pour chaque ticker (score_history)
3. Pour chaque (ticker, date_t) : mesurer perf forward 12m
4. Agréger par bucket de score (≥80, 65-79, 50-64, 35-49, <35)
5. Comparer à benchmark (SPY = S&P 500)

Output :
  outputs/backtest/backtest_{universe}_{years}y_{date}.parquet  (data brute)
  outputs/backtest/backtest_summary_{date}.json                 (rollup buckets)

Usage :
    python -m tools.backtest.run_backtest --universe sp50 --years 3
"""
from __future__ import annotations
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import numpy as np

from tools.backtest.fetch_history import fetch_universe, fetch_one_ticker, OUT_DIR
from tools.backtest.score_history import build_universe_history

log = logging.getLogger(__name__)


def _bucket_label(score: float) -> str:
    """Mapping score → bucket label."""
    if score >= 80:
        return "A (≥80)"
    if score >= 65:
        return "B (65-79)"
    if score >= 50:
        return "C (50-64)"
    if score >= 35:
        return "D (35-49)"
    return "E (<35)"


def compute_forward_returns(
    scores_df: pd.DataFrame,
    universe_data: dict[str, dict],
    horizon_months: int = 12,
) -> pd.DataFrame:
    """Pour chaque (ticker, date) dans scores_df, calcule la perf forward
    sur horizon_months. Ajoute colonnes `fwd_return`, `fwd_date`.
    """
    results = []
    for tk, group in scores_df.groupby("ticker"):
        prices = universe_data.get(tk, {}).get("prices")
        if prices is None or len(prices) == 0:
            continue
        p = prices.copy()
        if hasattr(p.index, "tz") and p.index.tz is not None:
            p.index = p.index.tz_localize(None)
        p_sorted = p.sort_index()

        for _, row in group.iterrows():
            dt = row["date"]
            fwd_dt = dt + pd.DateOffset(months=horizon_months)
            # Prix à t (déjà dans score_history) et à t+horizon
            # Prend le close le plus proche <= fwd_dt
            valid_fwd = p_sorted[p_sorted.index <= fwd_dt]
            if len(valid_fwd) == 0:
                continue
            last_fwd_date = valid_fwd.index[-1]
            # S'assurer que le prix forward est postérieur à dt
            if last_fwd_date <= dt:
                continue
            price_fwd = float(valid_fwd["Close"].iloc[-1])
            if row["price"] and row["price"] > 0:
                fwd_return = (price_fwd / row["price"]) - 1
                results.append({
                    **row.to_dict(),
                    "fwd_date": last_fwd_date,
                    "fwd_price": price_fwd,
                    "fwd_return": fwd_return,
                    "fwd_months_actual": (last_fwd_date - dt).days / 30.5,
                })
    return pd.DataFrame(results)


def compute_benchmark_returns(
    monthly_dates: list[pd.Timestamp],
    benchmark: str = "SPY",
    horizon_months: int = 12,
) -> dict[pd.Timestamp, float]:
    """Retourne {date_t: perf forward 12m du benchmark}."""
    spy = fetch_one_ticker(benchmark, years=max(3, (horizon_months // 12) + 2))
    if spy.get("error"):
        log.warning(f"[benchmark] {benchmark} fetch fail")
        return {}
    prices = spy["prices"]
    if hasattr(prices.index, "tz") and prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)
    p = prices.sort_index()

    out = {}
    for dt in monthly_dates:
        valid = p[p.index <= dt]
        if len(valid) == 0:
            continue
        p_t = float(valid["Close"].iloc[-1])
        fwd_dt = dt + pd.DateOffset(months=horizon_months)
        valid_fwd = p[p.index <= fwd_dt]
        if len(valid_fwd) == 0 or valid_fwd.index[-1] <= dt:
            continue
        p_fwd = float(valid_fwd["Close"].iloc[-1])
        if p_t > 0:
            out[dt] = (p_fwd / p_t) - 1
    return out


def bucket_analysis(
    returns_df: pd.DataFrame,
    benchmark_returns: dict[pd.Timestamp, float],
) -> dict:
    """Agrège perf par bucket de score. Retourne dict avec metrics globaux
    + par bucket.
    """
    if len(returns_df) == 0:
        return {"error": "no data"}

    returns_df["bucket"] = returns_df["score"].apply(_bucket_label)
    # Excess return vs benchmark
    returns_df["benchmark_return"] = returns_df["date"].map(benchmark_returns)
    returns_df["excess_return"] = returns_df["fwd_return"] - returns_df["benchmark_return"].fillna(0)

    summary = {
        "version": "v1.2",
        "n_observations": len(returns_df),
        "n_tickers": returns_df["ticker"].nunique(),
        "date_range": {
            "start": str(returns_df["date"].min().date()),
            "end": str(returns_df["date"].max().date()),
        },
        "horizon_months": 12,
        "buckets": {},
        "overall": {
            "mean_return": float(returns_df["fwd_return"].mean()),
            "median_return": float(returns_df["fwd_return"].median()),
            "pct_positive": float((returns_df["fwd_return"] > 0).mean()),
            "mean_benchmark": float(returns_df["benchmark_return"].dropna().mean())
                              if returns_df["benchmark_return"].notna().any() else None,
            "mean_excess": float(returns_df["excess_return"].dropna().mean())
                            if returns_df["excess_return"].notna().any() else None,
        },
    }

    bucket_order = ["A (≥80)", "B (65-79)", "C (50-64)", "D (35-49)", "E (<35)"]
    for b in bucket_order:
        sub = returns_df[returns_df["bucket"] == b]
        if len(sub) == 0:
            summary["buckets"][b] = {"n": 0}
            continue
        summary["buckets"][b] = {
            "n": len(sub),
            "n_tickers": int(sub["ticker"].nunique()),
            "mean_return": float(sub["fwd_return"].mean()),
            "median_return": float(sub["fwd_return"].median()),
            "std_return": float(sub["fwd_return"].std()),
            "pct_positive": float((sub["fwd_return"] > 0).mean()),
            "max_return": float(sub["fwd_return"].max()),
            "min_return": float(sub["fwd_return"].min()),
            "mean_excess": float(sub["excess_return"].dropna().mean())
                            if sub["excess_return"].notna().any() else None,
            "sharpe_proxy": (float(sub["fwd_return"].mean()) / float(sub["fwd_return"].std()))
                             if float(sub["fwd_return"].std()) > 0 else None,
        }

    # Sous-score analyse : corrélations dimension → fwd_return
    for dim in ("quality", "value", "momentum", "governance"):
        if dim in returns_df.columns:
            summary.setdefault("subscore_correlations", {})[dim] = \
                float(returns_df[dim].corr(returns_df["fwd_return"]))

    return summary


def run(universe: str = "sp50", years: int = 3, horizon_months: int = 12) -> dict:
    """Pipeline complet. Retourne summary + sauvegarde Parquet/JSON."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 1. Fetch
    log.info(f"\n=== BACKTEST {universe.upper()} {years}y h={horizon_months}m ===")
    data = fetch_universe(universe, years=years)

    # 2. Score historique
    log.info("[backtest] computing historical scores...")
    scores_df = build_universe_history(data)
    log.info(f"[backtest] {len(scores_df)} score points computed across "
             f"{scores_df['ticker'].nunique()} tickers")

    # 3. Forward returns
    log.info("[backtest] computing forward returns...")
    returns_df = compute_forward_returns(scores_df, data, horizon_months)
    log.info(f"[backtest] {len(returns_df)} observations with valid fwd_return")

    # 4. Benchmark
    monthly_dates = sorted(scores_df["date"].unique())
    log.info(f"[backtest] benchmark SPY over {len(monthly_dates)} dates...")
    benchmark = compute_benchmark_returns(monthly_dates, "SPY", horizon_months)

    # 5. Analyse bucket
    summary = bucket_analysis(returns_df, benchmark)

    # 6. Sauvegarde
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    parquet_path = OUT_DIR / f"backtest_{universe}_{years}y_{ts}.parquet"
    summary_path = OUT_DIR / f"backtest_summary_{universe}_{ts}.json"
    latest_path = OUT_DIR / "backtest_latest.json"

    try:
        returns_df.to_parquet(parquet_path, index=False)
        log.info(f"[backtest] saved {parquet_path.name}")
    except Exception as e:
        # Fallback CSV si Parquet pas dispo
        csv_path = parquet_path.with_suffix(".csv")
        returns_df.to_csv(csv_path, index=False)
        log.info(f"[backtest] saved {csv_path.name} (parquet err: {e})")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    # 7. Log récap
    log.info("\n═══ RÉCAP ═══")
    for b, v in summary["buckets"].items():
        if v.get("n", 0) == 0:
            continue
        log.info(f"  {b}: n={v['n']} | mean_return={v['mean_return']*100:+.1f}% | "
                 f"excess={v['mean_excess']*100 if v['mean_excess'] else 0:+.1f}% | "
                 f"%pos={v['pct_positive']*100:.0f}%")
    log.info(f"  Overall: n={summary['n_observations']} | "
             f"mean={summary['overall']['mean_return']*100:+.1f}% | "
             f"excess={summary['overall']['mean_excess']*100 if summary['overall']['mean_excess'] else 0:+.1f}%")

    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="sp50")
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--horizon", type=int, default=12, help="Horizon fwd (mois)")
    args = ap.parse_args()
    run(universe=args.universe, years=args.years, horizon_months=args.horizon)
