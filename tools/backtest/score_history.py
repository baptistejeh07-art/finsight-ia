"""score_history.py — Calcule le Score FinSight à chaque snapshot historique.

Règle d'or : **pas de look-ahead bias**. À chaque date t, on utilise
EXCLUSIVEMENT les données connues à t (dernière publication de bilan
annuel avant t + prix à t).

Stratégie pragmatique pour MVP :
- yfinance nous donne ~4 ans de financials annuels (dates précises des
  publications). Pour chaque mois t, on prend le dernier snapshot annuel
  publié **avant** t.
- Ratios calculés à partir de ce snapshot + prix à t pour les valorisations
  (P/E, EV/EBITDA, FCF Yield).
- Momentum 52w : calculé depuis les prix mensuels (window glissante).

Output : DataFrame long format
    ticker | date | score | grade | quality | value | momentum | governance
             | ratios_snapshot (JSON) | price_at_t

Cache : Parquet dans outputs/backtest/scores_{universe}_{date}.parquet
"""
from __future__ import annotations
import sys
import logging
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import numpy as np

from core.finsight_score import compute_score

log = logging.getLogger(__name__)


def _compute_ratios_at(t_data: dict, target_date: pd.Timestamp) -> dict:
    """Reconstruit un ratio_dict FinSight à target_date depuis les financials
    annuels disponibles. Retourne dict avec les clés attendues par compute_score.
    """
    prices = t_data.get("prices")
    fin = t_data.get("financials")
    bs = t_data.get("balance")
    cf = t_data.get("cashflow")
    info = t_data.get("info") or {}

    if prices is None or len(prices) == 0:
        return {}

    # Prix à target_date (dernier close <= target_date)
    prices_df = prices.copy()
    # yfinance retourne index timezone-aware parfois
    if hasattr(prices_df.index, "tz") and prices_df.index.tz is not None:
        prices_df.index = prices_df.index.tz_localize(None)
    valid_prices = prices_df[prices_df.index <= target_date]
    if len(valid_prices) == 0:
        return {}
    price_at_t = float(valid_prices["Close"].iloc[-1])

    # Snapshot financial annuel le plus récent AVANT target_date.
    # yfinance columns = dates de publication (en datetime).
    def _get_last_col(df: pd.DataFrame):
        if df is None or len(df) == 0:
            return None, None
        # Columns sont dates. On prend la plus récente avant target_date.
        def _ts_naive(c):
            t = pd.Timestamp(c)
            return t.tz_localize(None) if t.tz is not None else t
        try:
            cols_sorted = sorted(df.columns, key=_ts_naive)
            for c in reversed(cols_sorted):
                if _ts_naive(c) <= target_date:
                    return c, df[c]
        except Exception:
            pass
        return None, None

    _fin_date, fin_col = _get_last_col(fin) if fin is not None else (None, None)
    _bs_date, bs_col = _get_last_col(bs) if bs is not None else (None, None)
    _cf_date, cf_col = _get_last_col(cf) if cf is not None else (None, None)

    def _val(series, keys) -> Optional[float]:
        """Cherche la première clé présente dans l'ordre fourni."""
        if series is None:
            return None
        for k in keys:
            if k in series.index:
                v = series.loc[k]
                try:
                    return float(v) if pd.notna(v) else None
                except Exception:
                    pass
        return None

    # Extraction
    revenue = _val(fin_col, ["Total Revenue", "Revenue", "Operating Revenue"])
    ebit = _val(fin_col, ["Operating Income", "Ebit", "EBIT"])
    ebitda = _val(fin_col, ["EBITDA", "Normalized EBITDA"])
    net_income = _val(fin_col, ["Net Income", "Net Income Common Stockholders"])
    gross_profit = _val(fin_col, ["Gross Profit"])

    total_assets = _val(bs_col, ["Total Assets"])
    total_equity = _val(bs_col, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
    total_debt = _val(bs_col, ["Total Debt", "Net Debt"])
    cash = _val(bs_col, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    current_assets = _val(bs_col, ["Current Assets"])
    current_liab = _val(bs_col, ["Current Liabilities"])

    fcf = _val(cf_col, ["Free Cash Flow"])
    capex = _val(cf_col, ["Capital Expenditure"])
    # Dividends + shares pour governance historique (fix NaN correlation)
    dividends_paid = _val(cf_col, ["Cash Dividends Paid",
                                    "Common Stock Dividend Paid",
                                    "Cash Dividend Paid"])
    # Dividends paid est négatif (flux sortant) → on prend la valeur abs
    if dividends_paid is not None:
        dividends_paid = abs(dividends_paid)
    shares_out = _val(bs_col, ["Share Issued", "Ordinary Shares Number",
                                "Common Stock Equity"])
    # Retained earnings pour Altman (déjà fait plus bas mais récupéré ici)

    # Ratios de base
    ratios: dict = {}
    if revenue and revenue > 0:
        if ebitda:
            ratios["ebitda_margin"] = ebitda / revenue
        if net_income is not None:
            ratios["net_margin"] = net_income / revenue
        if gross_profit:
            ratios["gross_margin"] = gross_profit / revenue

    # Valorisations (nécessite price + shares)
    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    mcap = (price_at_t * shares) if shares else None
    if mcap and net_income and net_income > 0:
        ratios["pe_ratio"] = mcap / net_income
    ev = (mcap + (total_debt or 0) - (cash or 0)) if mcap else None
    if ev and ebitda and ebitda > 0:
        ratios["ev_ebitda"] = ev / ebitda
    if ev and revenue and revenue > 0:
        ratios["ev_revenue"] = ev / revenue
    if fcf and mcap and mcap > 0:
        ratios["fcf_yield"] = fcf / mcap

    # ROE / ROIC
    if net_income is not None and total_equity and total_equity > 0:
        ratios["roe"] = net_income / total_equity
    if ebit and total_assets and total_equity:
        # IC ≈ equity + debt - cash
        ic = total_equity + (total_debt or 0) - (cash or 0)
        if ic and ic > 0:
            tax = 0.25  # approx
            nopat = ebit * (1 - tax)
            ratios["roic"] = nopat / ic

    # Solvabilité
    if total_debt is not None and ebitda and ebitda > 0:
        nd = total_debt - (cash or 0)
        ratios["net_debt_ebitda"] = nd / ebitda

    # ── Governance historique (fix NaN correlation) ──
    # Payout ratio = dividendes versés / net income
    if dividends_paid and net_income and net_income > 0:
        payout = dividends_paid / net_income
        if 0 < payout < 3.0:  # sanity check
            ratios["payout_ratio"] = payout
    # Dividend yield = dividendes / market cap
    if dividends_paid and mcap and mcap > 0:
        dy = dividends_paid / mcap
        if 0 < dy < 0.20:
            ratios["div_yield"] = dy
    # Shares change YoY — compare shares du snapshot actuel vs précédent
    try:
        if bs is not None and len(bs.columns) >= 2:
            def _ts_naive_sh(c):
                t = pd.Timestamp(c)
                return t.tz_localize(None) if t.tz is not None else t
            cols_sorted = sorted(bs.columns, key=_ts_naive_sh)
            valid = [c for c in cols_sorted if _ts_naive_sh(c) <= target_date]
            if len(valid) >= 2:
                cur_s = _val(bs[valid[-1]], ["Share Issued", "Ordinary Shares Number"])
                prev_s = _val(bs[valid[-2]], ["Share Issued", "Ordinary Shares Number"])
                if cur_s and prev_s and prev_s > 0:
                    change = (cur_s / prev_s) - 1
                    if abs(change) < 0.50:  # sanity : >50% = merger/split, skip
                        ratios["shares_change_pct"] = change
    except Exception:
        pass

    # Altman Z (non-manufacturing simplifié)
    if total_assets and total_assets > 0:
        wc = (current_assets or 0) - (current_liab or 0)
        retained = _val(bs_col, ["Retained Earnings"]) or 0
        x1 = wc / total_assets
        x2 = retained / total_assets
        x3 = (ebit or 0) / total_assets
        x4 = (total_equity or 0) / max(total_debt or 1, 1)
        # Altman Z' (non-manufacturing) = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
        try:
            ratios["altman_z"] = round(6.56*x1 + 3.26*x2 + 6.72*x3 + 1.05*x4, 2)
        except Exception:
            pass

    # Momentum 52 semaines (depuis prix mensuels)
    try:
        cutoff_12m = target_date - pd.DateOffset(months=12)
        prices_12m = valid_prices[valid_prices.index >= cutoff_12m]
        if len(prices_12m) >= 2:
            p0 = float(prices_12m["Close"].iloc[0])
            p1 = float(prices_12m["Close"].iloc[-1])
            if p0 > 0:
                ratios["momentum_52w"] = (p1 / p0) - 1
    except Exception:
        pass

    # Revenue growth YoY
    if fin is not None and len(fin.columns) >= 2:
        try:
            def _ts_naive_rg(c):
                t = pd.Timestamp(c)
                return t.tz_localize(None) if t.tz is not None else t
            cols_sorted = sorted(fin.columns, key=_ts_naive_rg)
            # Prendre les 2 snapshots <= target_date les plus récents
            valid = [c for c in cols_sorted if _ts_naive_rg(c) <= target_date]
            if len(valid) >= 2:
                cur = fin[valid[-1]]
                prev = fin[valid[-2]]
                rc = _val(cur, ["Total Revenue", "Revenue"])
                rp = _val(prev, ["Total Revenue", "Revenue"])
                if rc and rp and rp > 0:
                    ratios["revenue_growth"] = (rc / rp) - 1
        except Exception:
            pass

    return ratios, price_at_t


def score_history_for_ticker(
    ticker: str,
    t_data: dict,
    sector: Optional[str] = None,
    monthly_dates: Optional[list[pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Calcule le Score FinSight à chaque date mensuelle fournie."""
    if t_data.get("error"):
        return pd.DataFrame()

    info = t_data.get("info") or {}
    sec = sector or info.get("sector", "")
    industry = info.get("industry", "")

    prices = t_data.get("prices")
    if prices is None or len(prices) == 0:
        return pd.DataFrame()

    # Dates mensuelles : 1er de chaque mois observable dans les prix
    if monthly_dates is None:
        idx = prices.index
        if hasattr(idx, "tz") and idx.tz is not None:
            idx = idx.tz_localize(None)
        monthly_dates = pd.to_datetime(idx.unique())

    rows = []
    for dt in monthly_dates:
        try:
            ratios, price_at_t = _compute_ratios_at(t_data, dt)
            if not ratios:
                continue
            # backtest_mode=True : skip facteurs v1.1 (Beneish, EPS rev,
            # short, insider, institutional) qui n'ont pas de data historique
            # yfinance. Évite la pollution _neutral qui dilue le signal.
            sc = compute_score(ratios, sector=sec, industry=industry,
                                backtest_mode=True)
            rows.append({
                "ticker": ticker,
                "date": dt,
                "score": sc["global"],
                "grade": sc["grade"],
                "quality": sc["quality"],
                "value": sc["value"],
                "momentum": sc["momentum"],
                "governance": sc["governance"],
                "sector_profile": sc.get("sector_profile_used", "STANDARD"),
                "price": price_at_t,
            })
        except Exception as e:
            log.debug(f"[score_history] {ticker}@{dt}: {e}")
            continue

    return pd.DataFrame(rows)


def build_universe_history(
    universe_data: dict[str, dict],
) -> pd.DataFrame:
    """Agrège score_history pour tous les tickers d'un univers."""
    all_dfs = []
    for tk, t_data in universe_data.items():
        df = score_history_for_ticker(tk, t_data)
        if len(df) > 0:
            all_dfs.append(df)
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)
