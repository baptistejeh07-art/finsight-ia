"""walk_forward.py -- Backtest walk-forward sans data leakage.

Probleme elimine : la calibration actuelle (`calibrate_bounds.py`) utilise les
snapshots 2025 pour determiner les quartiles sectoriels, puis applique ces
bornes a tous les scores historiques (2015-2025). Resultat : un ticker score
en 2018 est juge selon les standards qualite de 2025, ce qui leak de
l'information future.

Walk-forward propre :
  A chaque date T, calibrer les bornes sectorielles EN UTILISANT UNIQUEMENT
  les snapshots observables a T (cross-section de l'univers au temps T).
  Scorer les tickers a T avec ces bornes. Mesurer forward return T -> T+12m.

Implementation pragmatique :
  1. Pass 1 : pour chaque (ticker, date), extraire ratios historiques
     via `_compute_ratios_at` (meme logique que score_history.py).
  2. Pass 2 : grouper par date T, calculer `compute_quantiles(cross_section_T)`,
     injecter ces bornes via `set_sector_bounds_override`, scorer chaque
     ticker a T.
  3. Pass 3 : forward returns + aggregation comme run_backtest classique.

Usage :
    python -m tools.backtest.walk_forward --universe sp100 --years 10
"""
from __future__ import annotations
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import numpy as np

from core.finsight_score import compute_score, set_sector_bounds_override
from tools.backtest.fetch_history import fetch_universe, fetch_one_ticker, OUT_DIR
from tools.backtest.score_history import _compute_ratios_at
from tools.backtest.calibrate_bounds import compute_quantiles
from tools.backtest.run_backtest import (
    compute_forward_returns, compute_benchmark_returns,
    _SECTOR_TO_ETF, _sector_etf, bucket_analysis,
)

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Pass 1 : extraction des ratios historiques (sans scoring)
# ------------------------------------------------------------------
def extract_ratios_history(
    universe_data: dict[str, dict],
    monthly_dates: Optional[list[pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Retourne DataFrame long : (ticker, date, sector, ratios...).

    Reutilise _compute_ratios_at de score_history. Pas de scoring ici,
    juste les ratios bruts.
    """
    rows = []
    for tk, t_data in universe_data.items():
        if t_data.get("error"):
            continue
        info = t_data.get("info") or {}
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        prices = t_data.get("prices")
        if prices is None or len(prices) == 0:
            continue

        if monthly_dates is None:
            idx = prices.index
            if hasattr(idx, "tz") and idx.tz is not None:
                idx = idx.tz_localize(None)
            dates = pd.to_datetime(idx.unique())
        else:
            dates = monthly_dates

        for dt in dates:
            try:
                ratios, price_at_t = _compute_ratios_at(t_data, dt)
                if not ratios:
                    continue
                row = {
                    "ticker": tk,
                    "date": dt,
                    "sector": sector,
                    "industry": industry,
                    "price": price_at_t,
                }
                row.update(ratios)
                rows.append(row)
            except Exception as e:
                log.debug(f"[wf.extract] {tk}@{dt}: {e}")
                continue
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# Pass 2 : scoring avec bornes date-specifiques
# ------------------------------------------------------------------
def score_with_walk_forward_bounds(
    ratios_df: pd.DataFrame,
    min_tickers_per_sector: int = 5,
    min_tickers_per_date: int = 20,
) -> pd.DataFrame:
    """Pour chaque date T, calibre les bornes sur cross-section a T et score.

    Args:
        ratios_df : output de extract_ratios_history
        min_tickers_per_sector : seuil minimal pour retenir un sector dans
                                  les quartiles a une date T. En dessous,
                                  on retombe sur _default.
        min_tickers_per_date : seuil minimal de tickers observables a T pour
                                que la calibration date-specific soit fiable.
                                En dessous, on utilise les bornes expanding
                                (toutes donnees jusqu'a T).

    Retourne DataFrame avec score colonnes ajoutees.
    """
    if len(ratios_df) == 0:
        return pd.DataFrame()

    dates = sorted(ratios_df["date"].unique())
    log.info(f"[wf.score] {len(dates)} dates distinctes, "
             f"{ratios_df['ticker'].nunique()} tickers")

    scored_rows = []
    expanding_snapshots = []  # fallback si cross-section trop petite a T

    for dt in dates:
        sub = ratios_df[ratios_df["date"] == dt]

        # Construire snapshots au format attendu par compute_quantiles
        snapshots_at_t = [
            {**row.to_dict(), "sector": row.get("sector") or "Unknown"}
            for _, row in sub.iterrows()
        ]

        # Bornes a T
        if len(snapshots_at_t) >= min_tickers_per_date:
            bounds_t = compute_quantiles(snapshots_at_t)
        else:
            # Expanding window : utilise tout ce qui precede
            bounds_t = compute_quantiles(
                expanding_snapshots + snapshots_at_t
            ) if expanding_snapshots else {}

        # Scorer chaque ticker a T avec ces bornes
        set_sector_bounds_override(bounds_t)
        try:
            for _, row in sub.iterrows():
                ratios = {k: v for k, v in row.to_dict().items()
                           if k not in ("ticker", "date", "sector",
                                         "industry", "price")}
                sc = compute_score(
                    ratios,
                    sector=row.get("sector") or "",
                    industry=row.get("industry") or "",
                    backtest_mode=True,
                )
                # v2 : scores par pilier + recos profils
                try:
                    from core.finsight_score_v2 import (
                        compute_scores_v2, recommend_all_profiles,
                    )
                    scores_v2 = compute_scores_v2(
                        ratios,
                        sector=row.get("sector") or "",
                        industry=row.get("industry") or "",
                    )
                    recos = recommend_all_profiles(scores_v2)
                except Exception:
                    scores_v2 = None
                    recos = {}

                out_row = {
                    "ticker": row["ticker"],
                    "date": dt,
                    "sector_profile": sc.get("sector_profile_used", "STANDARD"),
                    "score": sc["global"],
                    "grade": sc["grade"],
                    "quality": sc["quality"],
                    "value": sc["value"],
                    "momentum": sc["momentum"],
                    "governance": sc["governance"],
                    "price": row["price"],
                }
                if scores_v2:
                    out_row["v2_quality"] = scores_v2["quality"]["score"]
                    out_row["v2_value"] = scores_v2["value"]["score"]
                    out_row["v2_momentum"] = scores_v2["momentum"]["score"]
                    out_row["v2_risk"] = scores_v2["risk"]["score"]
                for prof_key, reco in (recos or {}).items():
                    out_row[f"v2_{prof_key}_composite"] = reco["composite"]
                    out_row[f"v2_{prof_key}_reco"] = reco["recommendation"]
                scored_rows.append(out_row)
        finally:
            # Restaure chargement standard (important pour ne pas polluer
            # les autres appels compute_score post-backtest)
            set_sector_bounds_override(None)

        expanding_snapshots.extend(snapshots_at_t)

    return pd.DataFrame(scored_rows)


# ------------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------------
def run_walk_forward(
    universe: str = "sp100",
    years: int = 10,
    horizon_months: int = 12,
) -> dict:
    """Pipeline walk-forward complet : fetch + extract + score + forward + agg."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    log.info(f"[wf] fetching {universe} ({years}y)...")
    universe_data = fetch_universe(universe, years=years)
    log.info(f"[wf] {len(universe_data)} tickers OK")

    log.info("[wf] pass 1 : extraction ratios historiques...")
    ratios_df = extract_ratios_history(universe_data)
    log.info(f"[wf] {len(ratios_df)} observations (ticker, date)")

    log.info("[wf] pass 2 : scoring walk-forward (bornes date-specific)...")
    scored_df = score_with_walk_forward_bounds(ratios_df)
    log.info(f"[wf] {len(scored_df)} scores")

    log.info("[wf] pass 3 : forward returns 12m...")
    returns_df = compute_forward_returns(
        scored_df, universe_data, horizon_months=horizon_months
    )
    log.info(f"[wf] {len(returns_df)} observations forward")

    if len(returns_df) == 0:
        log.warning("[wf] aucun forward return calcule")
        return {}

    # Benchmark SPY + sectoriel
    monthly_dates = sorted(returns_df["date"].unique())
    spy_returns = compute_benchmark_returns(
        monthly_dates, benchmark="SPY",
        horizon_months=horizon_months, years=years,
    )

    # Benchmarks sectoriels (XLK, XLV, etc.)
    sector_benchmarks = {}
    for etf in set(_SECTOR_TO_ETF.values()):
        try:
            rets = compute_benchmark_returns(
                monthly_dates, benchmark=etf,
                horizon_months=horizon_months, years=years,
            )
            if rets:
                sector_benchmarks[etf] = rets
        except Exception as e:
            log.debug(f"[wf.bench] {etf}: {e}")

    # Ajoute sector_profile pour bucket_analysis (via scored_df)
    summary = bucket_analysis(returns_df, spy_returns, sector_benchmarks)
    summary["version"] = "v2_walk_forward"
    summary["methodology"] = (
        "walk-forward : bornes sectorielles calibrees a chaque date T "
        "depuis la cross-section des tickers observables a T. Elimine "
        "le data leakage vs calibration snapshot 2025."
    )

    # Sauvegardes
    date_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parquet_path = OUT_DIR / f"backtest_wf_{universe}_{years}y_{date_stamp}.parquet"
    returns_df.to_parquet(parquet_path)
    log.info(f"[wf] parquet saved : {parquet_path.name}")

    summary_path = OUT_DIR / f"backtest_wf_summary_{date_stamp}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    log.info(f"[wf] summary saved : {summary_path.name}")

    # Alias "latest"
    latest_path = OUT_DIR / "backtest_wf_latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="sp100")
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--horizon", type=int, default=12)
    args = ap.parse_args()
    s = run_walk_forward(args.universe, args.years, args.horizon)
    print(json.dumps(s, indent=2, default=str)[:3000])
