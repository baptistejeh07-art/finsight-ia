"""analyze_v2_profiles.py — Analyse statistique rigoureuse des 5 profils.

Mesure 4 choses pour chaque profil :
1. **Information Ratio** = mean_excess / std_excess (équivalent Sharpe pour alpha)
2. **t-stat** = mean_excess * sqrt(n) / std_excess (significance statistique)
   - |t| > 2.0 → signal significatif à 95% confidence
   - |t| > 3.0 → très significatif (99%)
3. **Analyse par sous-période** : bull 2015-2019, bear 2020 Covid,
   bull 2020-2021, bear 2022, bull 2023-2025. On regarde quel profil
   surperforme SUR CHAQUE régime.
4. **Analyse par secteur** : Value doit marcher sur Financials/Energy/Utilities,
   Growth sur Tech/Consumer Discretionary.

Usage :
    python -m tools.backtest.analyze_v2_profiles
"""
from __future__ import annotations
import sys
import json
import math
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "backtest"


_PROFILES = [
    "conservative_lt", "value_contrarian", "growth_aggressive",
    "income_dividends", "balanced",
]

_PROFILES_LABEL = {
    "conservative_lt":  "Conservateur LT",
    "value_contrarian": "Value contrarian",
    "growth_aggressive":"Growth agressif",
    "income_dividends": "Income dividendes",
    "balanced":         "Balanced",
}


def _t_stat_and_ir(series: pd.Series) -> tuple[float, float]:
    """Retourne (t_stat, info_ratio) pour une série d'excess returns."""
    clean = series.dropna()
    if len(clean) < 2:
        return 0.0, 0.0
    mean = float(clean.mean())
    std = float(clean.std())
    if std == 0 or math.isnan(std):
        return 0.0, 0.0
    t = mean * math.sqrt(len(clean)) / std
    ir = mean / std
    return round(t, 3), round(ir, 3)


def _period_label(dt: pd.Timestamp) -> str:
    """Stratifie par régime macro connu."""
    d = pd.Timestamp(dt)
    if d < pd.Timestamp("2018-01-01"):
        return "2015-2017 bull"
    if d < pd.Timestamp("2019-01-01"):
        return "2018 correction"
    if d < pd.Timestamp("2020-03-01"):
        return "2019 bull"
    if d < pd.Timestamp("2020-10-01"):
        return "2020 Covid bear+recovery"
    if d < pd.Timestamp("2022-01-01"):
        return "2021 bull"
    if d < pd.Timestamp("2023-01-01"):
        return "2022 bear"
    if d < pd.Timestamp("2024-07-01"):
        return "2023-H1 2024 bull tech"
    return "H2 2024-2025 tech"


def analyze(parquet_path: Path):
    log.info(f"Reading {parquet_path.name}")
    df = pd.read_parquet(parquet_path)
    log.info(f"  {len(df)} obs, {df['ticker'].nunique()} tickers")

    # === 1. Statistiques par profil sur tout le backtest ===
    print("\n" + "=" * 80)
    print("1. STATISTIQUES GLOBALES PAR PROFIL (filtre reco = BUY uniquement)")
    print("=" * 80)
    print(f"{'Profil':<20} | {'n':>5} | {'mean':>7} | {'excess':>7} | {'std':>6} | {'t-stat':>7} | {'IR':>6} | {'%pos':>5}")
    print("-" * 80)
    for prof in _PROFILES:
        reco_col = f"v2_{prof}_reco"
        comp_col = f"v2_{prof}_composite"
        if reco_col not in df.columns:
            continue
        buy = df[df[reco_col] == "BUY"].copy()
        if len(buy) == 0:
            print(f"{_PROFILES_LABEL[prof]:<20} | {'0':>5} | no BUY observations")
            continue
        mean_ret = float(buy["fwd_return"].mean())
        mean_exc = float(buy["excess_return"].mean())
        std_exc = float(buy["excess_return"].std())
        t, ir = _t_stat_and_ir(buy["excess_return"])
        pct_pos = float((buy["fwd_return"] > 0).mean())
        # Signal : significance stars
        stars = "***" if abs(t) >= 3 else "**" if abs(t) >= 2 else "*" if abs(t) >= 1.65 else ""
        print(f"{_PROFILES_LABEL[prof]:<20} | {len(buy):>5} | "
              f"{mean_ret*100:>+6.1f}% | {mean_exc*100:>+6.1f}% | "
              f"{std_exc*100:>5.1f}% | {t:>+6.2f}{stars:<3} | "
              f"{ir:>+5.2f} | {pct_pos*100:>4.0f}%")

    print("\nLégende : * t>1.65 (90%) · ** t>2 (95%) · *** t>3 (99%)")
    print("IR (Information Ratio) = mean/std — >0.5 = bon, >1.0 = excellent")

    # === 2. Par sous-période macro ===
    print("\n" + "=" * 80)
    print("2. EXCESS BUY PAR SOUS-PÉRIODE MACRO")
    print("=" * 80)
    df["period"] = df["date"].apply(_period_label)
    periods = ["2015-2017 bull", "2018 correction", "2019 bull",
               "2020 Covid bear+recovery", "2021 bull", "2022 bear",
               "2023-H1 2024 bull tech", "H2 2024-2025 tech"]
    print(f"{'Profil':<20} | " + " | ".join(f"{p[:12]:>12}" for p in periods))
    print("-" * (20 + 15 * len(periods)))
    for prof in _PROFILES:
        reco_col = f"v2_{prof}_reco"
        if reco_col not in df.columns:
            continue
        buy = df[df[reco_col] == "BUY"]
        line = f"{_PROFILES_LABEL[prof]:<20} | "
        cells = []
        for p in periods:
            sub = buy[buy["period"] == p]
            if len(sub) == 0:
                cells.append(f"{'—':>12}")
            else:
                exc = float(sub["excess_return"].mean()) * 100
                cells.append(f"{exc:+6.1f}% (n{len(sub):>2d})")
        line += " | ".join(cells)
        print(line)

    # === 3. Par secteur ===
    print("\n" + "=" * 80)
    print("3. EXCESS BUY PAR SECTEUR (top secteurs)")
    print("=" * 80)
    if "sector_profile" in df.columns:
        top_sectors = df["sector_profile"].value_counts().head(5).index.tolist()
        print(f"{'Profil':<20} | " + " | ".join(f"{s[:15]:>15}" for s in top_sectors))
        print("-" * (20 + 18 * len(top_sectors)))
        for prof in _PROFILES:
            reco_col = f"v2_{prof}_reco"
            if reco_col not in df.columns:
                continue
            buy = df[df[reco_col] == "BUY"]
            line = f"{_PROFILES_LABEL[prof]:<20} | "
            cells = []
            for sec in top_sectors:
                sub = buy[buy["sector_profile"] == sec]
                if len(sub) == 0:
                    cells.append(f"{'—':>15}")
                else:
                    exc = float(sub["excess_return"].mean()) * 100
                    cells.append(f"{exc:+6.1f}% (n{len(sub):>2d})")
            line += " | ".join(cells)
            print(line)

    # === 4. Interprétation automatique ===
    print("\n" + "=" * 80)
    print("4. INTERPRÉTATION")
    print("=" * 80)
    for prof in _PROFILES:
        reco_col = f"v2_{prof}_reco"
        if reco_col not in df.columns:
            continue
        buy = df[df[reco_col] == "BUY"]
        if len(buy) == 0:
            continue
        t, ir = _t_stat_and_ir(buy["excess_return"])
        mean_exc = float(buy["excess_return"].mean())

        # Verdict statistique
        if len(buy) < 30:
            verdict_stat = f"échantillon limité (n={len(buy)})"
        elif abs(t) >= 3:
            verdict_stat = f"TRÈS significatif (t={t:+.2f}, p<0.01)"
        elif abs(t) >= 2:
            verdict_stat = f"significatif (t={t:+.2f}, p<0.05)"
        elif abs(t) >= 1.65:
            verdict_stat = f"marginal (t={t:+.2f}, p<0.10)"
        else:
            verdict_stat = f"non significatif (t={t:+.2f})"

        # Recherche période la plus favorable
        by_period = buy.groupby("period")["excess_return"].mean().sort_values(ascending=False)
        best_period = by_period.index[0] if len(by_period) > 0 else "N/A"
        best_excess = by_period.iloc[0] * 100 if len(by_period) > 0 else 0

        print(f"\n{_PROFILES_LABEL[prof]}:")
        print(f"  • Alpha annualisé moyen : {mean_exc*100:+.1f}%")
        print(f"  • Significance : {verdict_stat}")
        print(f"  • Meilleure période : {best_period} ({best_excess:+.1f}% excess)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Cherche le parquet le plus récent
    parquets = sorted(OUT_DIR.glob("backtest_sp100_*.parquet"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if not parquets:
        print("No backtest parquet found. Run run_backtest first.")
        sys.exit(1)
    analyze(parquets[0])
