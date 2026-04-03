#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Calcul des ratios screening depuis Supabase Cache
# scripts/compute_screening.py
#
# Pipeline : Supabase raw JSON -> calculs Python/NumPy -> ScreeningWriter
# Zero LLM. Ratios calcules sur donnees historiques yfinance en cache.
#
# Usage :
#   python scripts/compute_screening.py --universe cac40
#   python scripts/compute_screening.py --universe cac40 --output outputs/generated/screening_cac40.xlsx
# =============================================================================

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Optional

import numpy as np
import requests
import yfinance as yf
from dotenv import load_dotenv

# Chargement .env local uniquement (ignoré sur Streamlit Cloud où il n'existe pas)
_env_local = Path(__file__).parent.parent / ".env"
if _env_local.exists():
    load_dotenv(_env_local, override=True)

sys.path.insert(0, str(Path(__file__).parent.parent))

from outputs.screening_writer import ScreeningWriter
from scripts.cache_update import CAC40_TICKERS, DAX40_TICKERS, STOXX50_TICKERS, FTSE100_TICKERS, fetch_sp500, UNIVERSES

# ---------------------------------------------------------------------------
# Cache revisions analystes (TTL 7 jours — Alpha Vantage 25 req/jour)
# ---------------------------------------------------------------------------
_REVISIONS_CACHE_FILE = Path(__file__).parent.parent / "logs" / "local" / "revisions_cache.json"
_REVISIONS_TTL = 7 * 24 * 3600   # 7 jours en secondes
_revisions_lock = threading.Lock()


def _load_revisions_cache() -> dict:
    try:
        if _REVISIONS_CACHE_FILE.exists():
            with open(_REVISIONS_CACHE_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return {}


def _save_revisions_cache(cache: dict) -> None:
    try:
        _REVISIONS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_REVISIONS_CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except Exception:
        pass


def _fetch_analyst_revision(ticker: str) -> Optional[int]:
    """
    Score de revision analystes = direction nette des changements de recommandation.
    Cascade 4 sources (arret des qu'une source retourne une valeur) :
      1. yfinance eps_revisions  (upLast30days - downLast30days) — US principalement
      2. yfinance recommendations_summary — delta mensuel (0m vs -1m) du consensus
         Fonctionne pour la majorite des blue chips EU (CAC, DAX, FTSE, STOXX)
      3. yfinance upgrades_downgrades — Action 'up'/'down' sur 90 jours
         Fenetre elargie a 90j pour maximiser la couverture EU
      4. FMP /upgrades-downgrades — API deja configuree, couvre EU avec .PA/.DE/.L
    Cache JSON 7 jours dans logs/local/revisions_cache.json.
    Retourne int (peut etre negatif) ou None si indisponible.
    """
    import pandas as pd

    key = ticker.upper()
    now = time.time()

    with _revisions_lock:
        cache = _load_revisions_cache()
        entry = cache.get(key, {})
        if entry and (now - entry.get("ts", 0)) < _REVISIONS_TTL:
            return entry.get("value")

    result: Optional[int] = None
    tkobj = yf.Ticker(ticker)

    # --- Source 1 : yfinance eps_revisions ---
    try:
        rev = tkobj.eps_revisions
        if rev is not None and not rev.empty:
            up_col   = next((c for c in rev.columns if c.lower().startswith("up")   and "30" in c), None)
            down_col = next((c for c in rev.columns if c.lower().startswith("down") and "30" in c), None)
            if up_col and down_col:
                up   = int(rev[up_col].iloc[0]   or 0)
                down = int(rev[down_col].iloc[0] or 0)
                result = up - down
    except Exception:
        pass

    # --- Source 2 : yfinance recommendations_summary (delta mensuel consensus) ---
    # Retourne : period | strongBuy | buy | hold | underperform | sell
    # periods : '0m' (actuel) '-1m' '-2m' '-3m'
    # Score = 2*strongBuy + buy - underperform - 2*sell
    # Revision = Score_0m - Score_(-1m)
    if result is None:
        try:
            rs = tkobj.recommendations_summary
            if rs is not None and not rs.empty and "period" in rs.columns:
                rs = rs.set_index("period") if rs.index.dtype == object else rs
                def _rec_score(period):
                    if period not in rs.index:
                        return None
                    r = rs.loc[period]
                    return (
                        2 * int(r.get("strongBuy",  0) or 0)
                        + int(r.get("buy",          0) or 0)
                        - int(r.get("underperform", 0) or 0)
                        - 2 * int(r.get("sell",     0) or 0)
                    )
                s0  = _rec_score("0m")
                s1m = _rec_score("-1m")
                if s0 is not None and s1m is not None:
                    result = s0 - s1m
        except Exception:
            pass

    # --- Source 3 : yfinance upgrades_downgrades (fenetre 90j pour EU) ---
    if result is None:
        try:
            ud = tkobj.upgrades_downgrades
            if ud is not None and not ud.empty and "Action" in ud.columns:
                cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=90)
                idx = ud.index
                if hasattr(idx, "tz") and idx.tz is not None:
                    ud_recent = ud[idx >= cutoff]
                else:
                    ud_recent = ud[idx >= cutoff.tz_localize(None)]
                actions = ud_recent["Action"].str.lower()
                upgrades   = int((actions == "up").sum())
                downgrades = int((actions == "down").sum())
                if upgrades + downgrades > 0:
                    result = upgrades - downgrades
        except Exception:
            pass

    # --- Source 4 : FMP upgrades-downgrades (couvre EU : .PA .DE .L) ---
    if result is None:
        fmp_key = os.getenv("FMP_API_KEY", "")
        if fmp_key:
            try:
                url = (
                    f"https://financialmodelingprep.com/api/v3/upgrades-downgrades"
                    f"?symbol={ticker}&apikey={fmp_key}"
                )
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    items = resp.json()
                    if isinstance(items, list) and items:
                        # Filtre 90 derniers jours
                        cutoff_str = (
                            datetime.utcnow() - timedelta(days=90)
                        ).strftime("%Y-%m-%d")
                        recent = [
                            i for i in items
                            if i.get("publishedDate", "")[:10] >= cutoff_str
                        ]
                        upgrades   = sum(1 for i in recent if i.get("action", "").lower() in ("upgrade", "initiated", "reiterated buy"))
                        downgrades = sum(1 for i in recent if i.get("action", "").lower() in ("downgrade",))
                        if upgrades + downgrades > 0:
                            result = upgrades - downgrades
            except Exception:
                pass

    # --- Source 5 : Finnhub recommendation-trends (delta mensuel) ---
    # Endpoint : GET /stock/recommendation?symbol={symbol}&token={key}
    # Retourne liste {period, buy, hold, sell, strongBuy, strongSell} tri desc
    # Meme logique delta que source 2 : Score = 2*SB + buy - sell - 2*SS
    # Couvre US + grands tickers internationaux (meilleure portee non-US que yfinance)
    if result is None:
        fh_key = os.getenv("FINNHUB_API_KEY", "")
        if fh_key:
            try:
                url = (
                    f"https://finnhub.io/api/v1/stock/recommendation"
                    f"?symbol={ticker}&token={fh_key}"
                )
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    items = resp.json()
                    if isinstance(items, list) and len(items) >= 2:
                        def _fh_score(item):
                            return (
                                2 * int(item.get("strongBuy",  0) or 0)
                                + int(item.get("buy",          0) or 0)
                                - int(item.get("sell",         0) or 0)
                                - 2 * int(item.get("strongSell", 0) or 0)
                            )
                        # items[0] = mois le plus recent, items[1] = mois precedent
                        delta = _fh_score(items[0]) - _fh_score(items[1])
                        if _fh_score(items[0]) != 0 or _fh_score(items[1]) != 0:
                            result = delta
            except Exception:
                pass

    with _revisions_lock:
        cache = _load_revisions_cache()
        cache[key] = {"value": result, "ts": now}
        _save_revisions_cache(cache)

    return result


# ---------------------------------------------------------------------------
# Overrides sectoriels pour tickers mal classes par yfinance
# Format : ticker_upper -> secteur canonique
# ---------------------------------------------------------------------------
_SECTOR_OVERRIDE: dict[str, str] = {
    "FI":    "Financial Services",   # Fiserv — fintech, classe Technology par yfinance
    "FISV":  "Financial Services",   # ancien ticker Fiserv
    "GPN":   "Financial Services",   # Global Payments
    "WEX":   "Financial Services",   # WEX Inc.
    "COUP":  "Technology",           # Coupa Software
    "PYPL":  "Financial Services",   # PayPal
    "SQ":    "Financial Services",   # Block Inc.
    "AFRM":  "Financial Services",   # Affirm
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("compute_screening")

# ---------------------------------------------------------------------------
# Supabase fetch
# ---------------------------------------------------------------------------

def _fetch_from_supabase(tickers: list[str]) -> dict[str, dict]:
    """Recupere les lignes tickers_cache pour une liste de tickers."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SECRET_KEY manquants dans .env")

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    chunk_size = 50  # eviter URLs trop longues

    result: dict[str, dict] = {}
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        ticker_list = ",".join(chunk)
        try:
            r = requests.get(
                f"{url}/rest/v1/tickers_cache",
                headers=headers,
                params={"ticker": f"in.({ticker_list})", "select": "*", "limit": str(chunk_size)},
                timeout=15,
            )
            r.raise_for_status()
            for row in r.json():
                result[row["ticker"]] = row
        except Exception as e:
            log.warning(f"Supabase fetch chunk {i}-{i+chunk_size}: {e}")

    log.info(f"{len(result)}/{len(tickers)} tickers charges depuis Supabase")
    return result


# ---------------------------------------------------------------------------
# Parsing JSON brut
# ---------------------------------------------------------------------------

def _sorted_years(stmt: dict) -> list[str]:
    """Retourne les annees disponibles triees desc pour n'importe quelle ligne."""
    if not stmt:
        return []
    all_dates: set[str] = set()
    for row_dict in stmt.values():
        if isinstance(row_dict, dict):
            all_dates.update(row_dict.keys())
    return sorted(all_dates, reverse=True)


def _get(stmt: dict, *row_names: str, year_idx: int = 0) -> Optional[float]:
    """Retourne la valeur d'une ligne du JSON brut pour l'annee year_idx (0=plus recente)."""
    years = _sorted_years(stmt)
    if not years or year_idx >= len(years):
        return None
    target_year = years[year_idx]
    for name in row_names:
        if name in stmt and isinstance(stmt[name], dict):
            val = stmt[name].get(target_year)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
    return None


def _parse_stmt(raw: Any) -> dict:
    """Parse le champ JSON (peut etre str ou dict selon openpyxl)."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


# ---------------------------------------------------------------------------
# Calculs financiers
# ---------------------------------------------------------------------------

def _ebitda(is_: dict, cf: dict, year_idx: int = 0) -> Optional[float]:
    # 1. Direct EBITDA
    v = _get(is_, "EBITDA", year_idx=year_idx)
    if v:
        return v
    # 2. Normalized EBITDA
    v = _get(is_, "Normalized EBITDA", year_idx=year_idx)
    if v:
        return v
    # 3. EBIT + D&A
    ebit = _get(is_, "EBIT", year_idx=year_idx)
    da   = _get(is_, "Reconciled Depreciation",
                "Depreciation And Amortization In Income Statement",
                year_idx=year_idx)
    if da is None:
        da = _get(cf, "Depreciation And Amortization",
                  "Reconciled Depreciation", "Depreciation",
                  year_idx=year_idx)
    if ebit is not None and da is not None:
        return ebit + abs(da)
    # 4. Net Income + Tax + Interest + D&A
    ni   = _get(is_, "Net Income", "Net Income From Continuing Operation Net Minority Interest",
                "Net Income Common Stockholders", year_idx=year_idx)
    tax  = _get(is_, "Tax Provision", "Income Tax Expense", year_idx=year_idx)
    inte = _get(is_, "Interest Expense Non Operating", "Interest Expense", year_idx=year_idx)
    if da is None:
        da = _get(cf, "Depreciation And Amortization", "Reconciled Depreciation",
                  year_idx=year_idx)
    if ni is not None and da is not None:
        return ni + abs(tax or 0) + abs(inte or 0) + abs(da)
    return None


def _altman_z(bs: dict, is_: dict) -> Optional[float]:
    """Altman Z'' (version non-manufacturiere)."""
    ta   = _get(bs, "Total Assets")
    re   = _get(bs, "Retained Earnings", "Retained Earnings Total Equity")
    ca   = _get(bs, "Current Assets", "Total Current Assets")
    cl   = _get(bs, "Current Liabilities", "Total Current Liabilities")
    bve  = _get(bs, "Common Stock Equity", "Stockholders Equity", "Total Stockholders Equity")
    tl   = _get(bs, "Total Liabilities Net Minority Interest", "Total Liabilities")
    ebit = _get(is_, "EBIT")
    if ebit is None:
        rev  = _get(is_, "Total Revenue", "Revenue")
        cogs = _get(is_, "Cost Of Revenue", "Reconciled Cost Of Revenue")
        sga  = _get(is_, "Selling General And Administration", "Selling General And Administrative")
        da   = _get(is_, "Reconciled Depreciation")
        if rev and cogs:
            gp = rev - abs(cogs or 0)
            ebit = gp - abs(sga or 0) - abs(da or 0)

    if not all(v is not None for v in [ta, re, ca, cl, bve, tl, ebit]):
        return None
    if ta == 0 or tl == 0:
        return None

    wc = (ca or 0) - (cl or 0)
    x1 = wc  / ta
    x2 = (re or 0) / ta
    x3 = ebit / ta
    x4 = (bve or 0) / tl
    return round(6.56*x1 + 3.26*x2 + 6.72*x3 + 1.05*x4, 2)


def _beneish_m(is_: dict, bs: dict, cf: dict) -> Optional[float]:
    """Beneish M-Score (5-variable simplifie). Necessite N et N-1."""
    def g(stmt, *keys, yr=0): return _get(stmt, *keys, year_idx=yr)

    rev0  = g(is_, "Total Revenue", yr=0)
    rev1  = g(is_, "Total Revenue", yr=1)
    cogs0 = g(is_, "Cost Of Revenue", "Reconciled Cost Of Revenue", yr=0)
    cogs1 = g(is_, "Cost Of Revenue", "Reconciled Cost Of Revenue", yr=1)
    rec0  = g(bs, "Accounts Receivable", "Net Receivables", yr=0)
    rec1  = g(bs, "Accounts Receivable", "Net Receivables", yr=1)
    ppe0  = g(bs, "Net PPE", "Net Property Plant And Equipment", yr=0)
    ppe1  = g(bs, "Net PPE", "Net Property Plant And Equipment", yr=1)
    da0   = g(is_, "Reconciled Depreciation", yr=0) or g(cf, "Depreciation And Amortization", yr=0)
    da1   = g(is_, "Reconciled Depreciation", yr=1) or g(cf, "Depreciation And Amortization", yr=1)
    sga0  = g(is_, "Selling General And Administration", "Selling General And Administrative", yr=0)
    sga1  = g(is_, "Selling General And Administration", "Selling General And Administrative", yr=1)

    if not all(v is not None and v != 0 for v in [rev0, rev1, cogs0, cogs1]):
        return None

    try:
        dsri = ((rec0 / rev0) / (rec1 / rev1)) if rec0 and rec1 else 1.0
        gmi  = ((rev1 - abs(cogs1)) / rev1) / ((rev0 - abs(cogs0)) / rev0)
        sgi  = rev0 / rev1
        depi = ((abs(da1) / (abs(da1) + (ppe1 or 1))) /
                (abs(da0) / (abs(da0) + (ppe0 or 1)))) if da0 and da1 else 1.0
        sgai = ((abs(sga0) / rev0) / (abs(sga1) / rev1)) if sga0 and sga1 else 1.0
        # AQI
        ta0  = g(bs, "Total Assets", yr=0)
        ta1  = g(bs, "Total Assets", yr=1)
        ca0  = g(bs, "Current Assets", "Total Current Assets", yr=0)
        ca1  = g(bs, "Current Assets", "Total Current Assets", yr=1)
        aqi  = 1.0
        if ta0 and ta1 and ca0 and ca1 and ppe0 and ppe1:
            aqi = ((1 - (ca0 + ppe0) / ta0) /
                   (1 - (ca1 + ppe1) / ta1))

        m = (-6.065
             + 0.823  * dsri
             + 0.906  * gmi
             + 0.593  * aqi
             + 0.717  * sgi
             + 0.107  * depi
             - 0.172  * sgai)
        return round(m, 2)
    except (ZeroDivisionError, TypeError):
        return None


def _momentum_52w(ticker: str, hist_df) -> Optional[float]:
    """Performance 52 semaines depuis l'historique yfinance."""
    try:
        if hist_df is None or hist_df.empty or len(hist_df) < 12:
            return None
        current = float(hist_df["Close"].iloc[-1])
        past    = float(hist_df["Close"].iloc[0])
        if past == 0:
            return None
        return round((current - past) / past * 100, 1)
    except Exception:
        return None


def _wacc(info: dict, is_: dict, bs: dict) -> Optional[float]:
    """WACC simplifie : CAPM pour le cout des fonds propres + dette."""
    rf   = 0.04    # taux sans risque approx
    erp  = 0.055   # prime de risque marche

    beta = info.get("beta")
    if beta is None or beta <= 0:
        beta = 1.0

    ke = rf + beta * erp

    # Cout de la dette = interest_expense / total_debt
    inte = abs(_get(is_, "Interest Expense Non Operating", "Interest Expense") or 0)
    ltd  = _get(bs, "Long Term Debt", "Long Term Debt And Capital Lease Obligation") or 0
    std  = _get(bs, "Current Debt", "Short Term Debt",
                "Current Debt And Capital Lease Obligation") or 0
    total_debt = ltd + std
    kd = (inte / total_debt) if total_debt > 0 else 0.04
    kd = min(kd, 0.15)  # plafond raisonnable

    # Structure de capital (market)
    price  = info.get("currentPrice") or info.get("regularMarketPrice")
    shares = info.get("sharesOutstanding")
    mc = (float(price) * float(shares)) if price and shares else None
    ta = _get(bs, "Total Assets")

    if mc and total_debt > 0:
        total_v = mc + total_debt
        we = mc / total_v
        wd = total_debt / total_v
    else:
        we, wd = 0.70, 0.30

    tax_rate = 0.25  # taux IS approx
    wacc = we * ke + wd * kd * (1 - tax_rate)
    return round(wacc * 100, 1)


_TGR_BY_SECTOR = {
    "Technology": 3.0, "Healthcare": 2.5, "Health Care": 2.5,
    "Financials": 2.5, "Consumer Discretionary": 2.5,
    "Consumer Staples": 2.0, "Energy": 2.0,
    "Industrials": 2.5, "Materials": 2.0,
    "Real Estate": 2.5, "Utilities": 2.0,
    "Communication Services": 2.5,
}


def _tgr(sector: str) -> float:
    return _TGR_BY_SECTOR.get(sector, 2.5)


# ---------------------------------------------------------------------------
# Scoring percentile intra-univers (0-100)
# ---------------------------------------------------------------------------

def _percentile_score(values: list[Optional[float]],
                      higher_is_better: bool = True) -> list[Optional[int]]:
    """
    Transforme une liste de valeurs en scores 0-100 par rang percentile.
    None reste None.
    """
    indexed = [(v, i) for i, v in enumerate(values) if v is not None]
    if not indexed:
        return [None] * len(values)

    indexed_sorted = sorted(indexed, key=lambda x: x[0],
                            reverse=higher_is_better)
    n = len(indexed_sorted)
    rank_map: dict[int, int] = {}
    for rank, (_, orig_i) in enumerate(indexed_sorted):
        rank_map[orig_i] = int(round((1 - rank / (n - 1 if n > 1 else 1)) * 100))

    return [rank_map.get(i) if values[i] is not None else None
            for i in range(len(values))]


def _compute_scores(data: list[dict]) -> list[dict]:
    """Calcule les 4 scores + score_global par rang dans l'univers."""
    n = len(data)

    # Value : ev_ebitda bas = bon, pe bas = bon, ev_revenue bas = bon
    def _value_composite(t):
        scores = []
        for k in ("ev_ebitda", "pe", "ev_revenue"):
            v = t.get(k)
            if v is not None:
                try:
                    scores.append(float(v))
                except (ValueError, TypeError):
                    pass
        return (sum(scores) / len(scores)) if scores else None

    # Growth : revenue_growth haut, ebitda_ntm_growth haut
    def _growth_composite(t):
        scores = []
        for k in ("revenue_growth", "ebitda_ntm_growth"):
            v = t.get(k)
            if v is not None:
                try:
                    scores.append(float(v))
                except (ValueError, TypeError):
                    pass
        return (sum(scores) / len(scores)) if scores else None

    # Quality : gross_margin haut, net_margin haut, altman_z haut, current_ratio haut
    def _quality_composite(t):
        scores = []
        for k in ("gross_margin", "net_margin", "current_ratio"):
            v = t.get(k)
            if v is not None:
                try:
                    scores.append(float(v))
                except (ValueError, TypeError):
                    pass
        # altman_z : normalise sur [-5, 10] → [0, 1]
        z = t.get("altman_z")
        if z is not None:
            try:
                scores.append((float(z) + 5) / 15)
            except (ValueError, TypeError):
                pass
        return (sum(scores) / len(scores)) if scores else None

    # Momentum
    def _mom_composite(t):
        v = t.get("momentum_52w")
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    val_raw  = [_value_composite(t)   for t in data]
    grw_raw  = [_growth_composite(t)  for t in data]
    qua_raw  = [_quality_composite(t) for t in data]
    mom_raw  = [_mom_composite(t)     for t in data]

    val_scores = _percentile_score(val_raw, higher_is_better=False)  # faible mult = bon
    grw_scores = _percentile_score(grw_raw, higher_is_better=True)
    qua_scores = _percentile_score(qua_raw, higher_is_better=True)
    mom_scores = _percentile_score(mom_raw, higher_is_better=True)

    for i, t in enumerate(data):
        t["score_value"]    = val_scores[i]
        t["score_growth"]   = grw_scores[i]
        t["score_quality"]  = qua_scores[i]
        t["score_momentum"] = mom_scores[i]
        parts = [s for s in [val_scores[i], grw_scores[i],
                              qua_scores[i], mom_scores[i]] if s is not None]
        t["score_global"] = int(round(sum(parts) / len(parts))) if parts else None

    return data


# ---------------------------------------------------------------------------
# Enrichissement yfinance temps reel
# ---------------------------------------------------------------------------

def _enrich_realtime(ticker: str, cache_info: dict) -> dict:
    """
    Recupere prix, shares, beta, momentum 52W depuis yfinance.
    Retourne un dict de champs a merger dans le ticker_dict.
    """
    extra: dict = {}
    try:
        tk = yf.Ticker(ticker)

        def _info():
            try:
                return tk.info or {}
            except Exception:
                return {}

        def _hist():
            try:
                return tk.history(period="1y", interval="1mo")
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_info = pool.submit(_info)
            f_hist = pool.submit(_hist)

        info = f_info.result()
        hist = f_hist.result()

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        # Fallback price : fast_info -> history si info ne retourne pas de prix
        if not price:
            try:
                fi = tk.fast_info
                price = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
            except Exception:
                pass
        if not price and hist is not None and not hist.empty:
            try:
                price = round(float(hist["Close"].iloc[-1]), 2)
            except Exception:
                pass
        extra["price"]  = price
        extra["shares"] = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        extra["beta"]   = info.get("beta") or 1.0
        extra["_info"]  = info
        extra["_hist"]  = hist

        if hist is not None and not hist.empty:
            extra["momentum_52w"] = _momentum_52w(ticker, hist)

    except Exception as e:
        log.warning(f"[{ticker}] yfinance realtime: {e}")

    return extra


# ---------------------------------------------------------------------------
# Calcul complet d'un ticker
# ---------------------------------------------------------------------------

def compute_ticker(ticker: str, cache_row: Optional[dict]) -> Optional[dict]:
    """
    Calcule tous les ratios pour un ticker depuis le cache Supabase.
    Retourne un dict tickers_data ou None si donnees insuffisantes.
    """
    if not cache_row:
        log.warning(f"[{ticker}] absent du cache Supabase")
        return None

    is_  = _parse_stmt(cache_row.get("income_statement") or {})
    bs   = _parse_stmt(cache_row.get("balance_sheet")    or {})
    cf   = _parse_stmt(cache_row.get("cash_flow")        or {})

    if not is_ and not bs:
        log.warning(f"[{ticker}] cache vide (IS + BS absents)")
        return None

    # --- Enrichissement temps reel ---
    rt = _enrich_realtime(ticker, cache_row)
    info   = rt.get("_info", {})
    price  = rt.get("price")
    shares = rt.get("shares") or info.get("sharesOutstanding")

    # --- Donnees IS ---
    revenue0    = _get(is_, "Total Revenue", "Revenue", "Operating Revenue")
    revenue1    = _get(is_, "Total Revenue", "Revenue", "Operating Revenue", year_idx=1)
    gross_profit= _get(is_, "Gross Profit")
    net_income  = _get(is_, "Net Income",
                       "Net Income From Continuing Operation Net Minority Interest",
                       "Net Income Common Stockholders")
    interest_exp= _get(is_, "Interest Expense Non Operating", "Interest Expense")
    ebit_v      = _get(is_, "EBIT")
    da_v        = _get(is_, "Reconciled Depreciation",
                       "Depreciation And Amortization In Income Statement")
    if da_v is None:
        da_v = _get(cf, "Depreciation And Amortization", "Reconciled Depreciation")

    ebitda0 = _ebitda(is_, cf, year_idx=0)
    ebitda1 = _ebitda(is_, cf, year_idx=1)

    # --- Donnees BS ---
    cash     = _get(bs, "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash And Short Term Investments")
    ltd      = _get(bs, "Long Term Debt", "Long Term Debt And Capital Lease Obligation") or 0
    std      = _get(bs, "Current Debt", "Short Term Debt",
                    "Current Debt And Capital Lease Obligation") or 0
    total_debt = ltd + std
    net_debt   = total_debt - (cash or 0)
    total_eq   = _get(bs, "Common Stock Equity", "Stockholders Equity", "Total Stockholders Equity")
    total_ass  = _get(bs, "Total Assets")
    curr_ass   = _get(bs, "Current Assets", "Total Current Assets")
    curr_liab  = _get(bs, "Current Liabilities", "Total Current Liabilities")

    # --- Marche ---
    if price and shares:
        market_cap = round(float(price) * float(shares) / 1e9, 2)  # Mds
    else:
        market_cap = None

    ev = (market_cap + net_debt / 1e9) if market_cap is not None else None

    # Convertir IS/BS de raw (unites absolues) en Mds
    def _mds(v):
        return round(v / 1e9, 2) if v is not None else None

    revenue_ltm  = _mds(revenue0)
    ebitda_ltm   = _mds(ebitda0)
    net_inc_mds  = _mds(net_income)

    # --- Multiples ---
    ev_ebitda = round(ev / ebitda_ltm, 1) if (ev and ebitda_ltm and ebitda_ltm > 0) else None
    if ev_ebitda is None:
        _yf_ev_ebitda = info.get("enterpriseToEbitda")
        if _yf_ev_ebitda and 1.0 < float(_yf_ev_ebitda) < 200:
            ev_ebitda = round(float(_yf_ev_ebitda), 1)
    if ev_ebitda is None:
        # 3e fallback : enterpriseValue / ebitda directs (yfinance brut)
        _yf_ev_raw  = info.get("enterpriseValue")
        _yf_ebitda  = info.get("ebitda")
        if _yf_ev_raw and _yf_ebitda and float(_yf_ebitda) > 0:
            _ev_eb_raw = float(_yf_ev_raw) / float(_yf_ebitda)
            if 1.0 < _ev_eb_raw < 200:
                ev_ebitda = round(_ev_eb_raw, 1)
    ev_revenue= round(ev / revenue_ltm, 1) if (ev and revenue_ltm and revenue_ltm > 0) else None
    eps       = round(net_income / shares, 2) if (net_income and shares and shares > 0) else None
    pe        = round(float(price) / eps, 1) if (price and eps and eps > 0) else None

    # --- Marges ---
    gross_margin  = round(gross_profit / revenue0 * 100, 1) if (gross_profit and revenue0) else None
    ebitda_margin = round(ebitda0 / revenue0 * 100, 1)      if (ebitda0 and revenue0) else None
    net_margin    = round(net_income / revenue0 * 100, 1)   if (net_income and revenue0) else None

    # --- Croissance ---
    revenue_growth = (
        round((revenue0 - revenue1) / abs(revenue1) * 100, 1)
        if (revenue0 and revenue1 and revenue1 != 0) else None
    )
    ebitda_ntm_growth = (
        round((ebitda0 - ebitda1) / abs(ebitda1) * 100, 1)
        if (ebitda0 and ebitda1 and ebitda1 != 0) else None
    )

    # --- Rentabilite ---
    roe = round(net_income / total_eq * 100, 1) if (net_income and total_eq and total_eq != 0) else None
    roa = round(net_income / total_ass * 100, 1) if (net_income and total_ass and total_ass != 0) else None

    # --- Liquidite ---
    current_ratio = round(curr_ass / curr_liab, 2) if (curr_ass and curr_liab and curr_liab != 0) else None
    nd_ebitda = round(net_debt / ebitda0, 1) if (ebitda0 and ebitda0 != 0) else None
    ebit_v2   = ebit_v or (ebitda0 - abs(da_v or 0)) if ebitda0 else None
    interest_coverage = (
        round(ebit_v2 / abs(interest_exp), 0)
        if (ebit_v2 and interest_exp and interest_exp != 0) else None
    )

    # --- Croissance EPS (yfinance earningsGrowth, decimal) ---
    _eg_raw = info.get("earningsGrowth")
    earnings_growth = round(float(_eg_raw) * 100, 1) if _eg_raw is not None else None

    # --- FCF Yield (%) ---
    _cf_fcf = _get(cf, "Free Cash Flow")
    if _cf_fcf is None:
        _ocf   = _get(cf, "Operating Cash Flow")
        _capex = _get(cf, "Capital Expenditure")
        if _ocf is not None and _capex is not None:
            _cf_fcf = _ocf + _capex   # CapEx negatif dans yfinance
    _mktcap_raw = float(price) * float(shares) if (price and shares) else None
    fcf_yield = (
        round(_cf_fcf / _mktcap_raw * 100, 1)
        if (_cf_fcf and _mktcap_raw and _mktcap_raw > 0) else None
    )

    # --- Revisions analystes (cache 7j) ---
    analyst_revision = _fetch_analyst_revision(ticker)

    # --- Qualite ---
    altman  = _altman_z(bs, is_)
    beneish = _beneish_m(is_, bs, cf)
    mom52w  = rt.get("momentum_52w")

    # --- WACC / TGR ---
    wacc_val = _wacc(info, is_, bs)
    sector   = _SECTOR_OVERRIDE.get(ticker.upper()) \
               or cache_row.get("sector") or info.get("sector") or ""
    tgr_val  = _tgr(sector)

    return {
        "ticker":      ticker.upper(),
        "company":     cache_row.get("company_name") or info.get("longName") or ticker,
        "sector":      sector,
        "country":     "FR" if ticker.endswith(".PA") else
                       "DE" if ticker.endswith(".DE") else
                       "GB" if ticker.endswith(".L")  else
                       "US",
        "currency":    cache_row.get("currency") or info.get("currency") or "USD",
        "price":       round(float(price), 2) if price else None,
        "market_cap":  market_cap,
        "ev":          round(ev, 2) if ev else None,
        "revenue_ltm": revenue_ltm,
        "ebitda_ltm":  ebitda_ltm,
        "ev_ebitda":   ev_ebitda,
        "ev_revenue":  ev_revenue,
        "pe":          pe,
        "eps":         eps,
        "gross_margin":   gross_margin,
        "ebitda_margin":  ebitda_margin,
        "net_margin":     net_margin,
        "revenue_growth": revenue_growth,
        "roe":         roe,
        "roa":         roa,
        "current_ratio":   current_ratio,
        "net_debt_ebitda": nd_ebitda,
        "interest_coverage": interest_coverage,
        "altman_z":    altman,
        "beneish_m":   beneish,
        "momentum_52w":mom52w,
        # scores calcules apres agregation
        "score_value":    None,
        "score_growth":   None,
        "score_quality":  None,
        "score_momentum": None,
        "score_global":   None,
        "next_earnings":     cache_row.get("next_earnings"),
        "ebitda_ntm_growth": ebitda_ntm_growth,
        "earnings_growth":   earnings_growth,
        "fcf_yield":         fcf_yield,
        "analyst_revision":  analyst_revision,
        "wacc": wacc_val,
        "tgr":  tgr_val,
    }


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def build_tickers_data(tickers: list[str], workers: int = 6) -> list[dict]:
    """
    Pipeline complet : Supabase -> calculs -> scores.
    Retourne tickers_data pret pour ScreeningWriter.
    """
    # 1. Fetch Supabase
    cache = _fetch_from_supabase(tickers)

    # 2. Calcul parallele
    results: list[dict] = []
    errors: list[str] = []

    log.info(f"Calcul ratios pour {len(tickers)} tickers ({workers} workers) ...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(compute_ticker, t, cache.get(t.upper())): t
            for t in tickers
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
                else:
                    errors.append(ticker)
            except Exception as e:
                log.error(f"[{ticker}] compute error: {e}")
                errors.append(ticker)

    log.info(f"{len(results)} tickers calcules, {len(errors)} echecs")
    if errors:
        log.warning(f"Echecs : {', '.join(errors)}")

    # 3. Scores intra-univers
    results = _compute_scores(results)

    # Trier par score_global desc
    results.sort(key=lambda x: x.get("score_global") or 0, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FinSight IA — Calcul ratios screening depuis Supabase",
    )
    parser.add_argument(
        "--universe",
        choices=["cac40", "dax40", "stoxx50", "ftse100", "sp500"],
        default="cac40",
    )
    parser.add_argument("--tickers", nargs="+", metavar="TICKER")
    parser.add_argument("--output",  default="", help="Chemin fichier Excel de sortie")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
        universe_name = "Selection manuelle"
    elif args.universe == "sp500":
        tickers = fetch_sp500()
        universe_name = "S&P 500"
    else:
        tickers = UNIVERSES[args.universe]
        universe_name = {"cac40":"CAC 40","dax40":"DAX 40",
                         "stoxx50":"EURO STOXX 50","ftse100":"FTSE 100"}[args.universe]

    log.info(f"Univers : {universe_name} ({len(tickers)} tickers)")

    t0 = time.time()
    tickers_data = build_tickers_data(tickers, workers=args.workers)
    elapsed = round(time.time() - t0, 1)
    log.info(f"Pipeline termine en {elapsed}s — {len(tickers_data)} tickers valides")

    if not tickers_data:
        log.error("Aucun ticker valide — abandon")
        sys.exit(1)

    output_path = args.output or (
        f"outputs/generated/screening_{args.universe}_{date.today().strftime('%Y%m%d')}.xlsx"
    )
    out = ScreeningWriter.generate(tickers_data, universe_name, output_path)
    log.info(f"Fichier genere : {out}")


if __name__ == "__main__":
    main()
