"""Time series de prix + stats de performance pour un ticker.

Expose :
  - fetch_performance(ticker) : dict {period: {change_pct, high, low, ...}}
  - fetch_price_series(ticker, period) : [{date, close}, ...]

Cache in-memory 5 min (yfinance rate-limits + usage redondant UI).
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# Cache distribué Redis avec fallback in-memory (core.cache)
from core.cache import cache as _cache
_CACHE_TTL = 300  # 5 min


PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "3y", "5y"]

# Mapping period → (yfinance_period, yfinance_interval)
_PERIOD_CONFIG = {
    "1d":  ("2d",  "5m"),     # 2 jours pour avoir open/close jour précédent
    "5d":  ("5d",  "30m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "6mo": ("6mo", "1d"),
    "ytd": ("ytd", "1d"),
    "1y":  ("1y",  "1d"),
    "3y":  ("3y",  "1wk"),
    "5y":  ("5y",  "1wk"),
}


@dataclass
class PerformanceStats:
    period: str
    change_pct: Optional[float]
    high: Optional[float]
    low: Optional[float]
    volatility_ann: Optional[float]   # σ annualisée %
    volume_avg: Optional[float]       # volume moyen sur la période
    points: int


def _cache_get(key: str) -> Optional[dict]:
    return _cache.get_json(f"market:{key}")


def _cache_set(key: str, payload: dict) -> None:
    _cache.set_json(f"market:{key}", payload, ttl_seconds=_CACHE_TTL)


def _compute_perf(hist) -> Optional[PerformanceStats]:
    """Calcule stats à partir d'un DataFrame yfinance history."""
    if hist is None or len(hist) < 2:
        return None
    try:
        closes = hist["Close"].dropna()
        if len(closes) < 2:
            return None
        first = float(closes.iloc[0])
        last = float(closes.iloc[-1])
        change = (last / first - 1) * 100 if first > 0 else None
        high = float(hist["High"].max()) if "High" in hist else float(closes.max())
        low = float(hist["Low"].min()) if "Low" in hist else float(closes.min())
        # Volatilité annualisée = σ(log-returns) × √(252 ou 52 pour weekly)
        try:
            import numpy as np
            returns = np.log(closes / closes.shift(1)).dropna()
            if len(returns) > 1:
                sigma = float(returns.std())
                # Détection interval (daily ou weekly)
                ann_factor = 52 if len(returns) < 30 else 252
                vol_ann = sigma * math.sqrt(ann_factor) * 100
            else:
                vol_ann = None
        except Exception:
            vol_ann = None
        vol_avg = None
        if "Volume" in hist:
            try:
                vol_avg = float(hist["Volume"].mean())
            except Exception:
                pass
        return PerformanceStats(
            period="",
            change_pct=round(change, 2) if change is not None else None,
            high=round(high, 2),
            low=round(low, 2),
            volatility_ann=round(vol_ann, 1) if vol_ann else None,
            volume_avg=round(vol_avg) if vol_avg else None,
            points=len(closes),
        )
    except Exception as e:
        log.warning(f"[market] _compute_perf failed: {e}")
        return None


def fetch_performance(ticker: str) -> dict:
    """Retourne {ticker, current_price, periods: {1d:{...}, 5d:{...}, ...}, meta}.

    Calcule en un seul appel yfinance (période 5y, interval daily) + sous-coupes
    en Python pour chaque période — évite 9 appels réseau.
    """
    if not ticker:
        return {"error": "ticker manquant"}
    key = f"perf:{ticker}"
    cached = _cache_get(key)
    if cached:
        return cached

    try:
        from core.yfinance_cache import get_ticker
        tk = get_ticker(ticker)
        # Un seul fetch 5y daily — on sous-tranche ensuite en Python
        hist_all = tk.history(period="5y", interval="1d")
        if hist_all is None or len(hist_all) == 0:
            return {"ticker": ticker, "error": "no history"}

        # Current price
        current_price = float(hist_all["Close"].iloc[-1]) if len(hist_all) > 0 else None
    except Exception as e:
        log.warning(f"[market] fetch history fail {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)[:80]}

    import pandas as pd
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    periods_stats: dict[str, dict] = {}

    _SLICES = {
        "5d":  now - timedelta(days=7),
        "1mo": now - timedelta(days=30),
        "3mo": now - timedelta(days=90),
        "6mo": now - timedelta(days=180),
        "ytd": datetime(now.year, 1, 1),
        "1y":  now - timedelta(days=365),
        "3y":  now - timedelta(days=365 * 3),
        "5y":  now - timedelta(days=365 * 5),
    }

    # 1d spécial : dernière session vs clôture précédente
    try:
        if len(hist_all) >= 2:
            last = float(hist_all["Close"].iloc[-1])
            prev = float(hist_all["Close"].iloc[-2])
            periods_stats["1d"] = {
                "change_pct": round((last / prev - 1) * 100, 2) if prev > 0 else None,
                "high": round(float(hist_all["High"].iloc[-1]), 2) if "High" in hist_all else None,
                "low": round(float(hist_all["Low"].iloc[-1]), 2) if "Low" in hist_all else None,
                "volatility_ann": None,
                "volume_avg": round(float(hist_all["Volume"].iloc[-1])) if "Volume" in hist_all else None,
                "points": 1,
            }
    except Exception:
        pass

    # Autres périodes
    try:
        idx = hist_all.index
        if hasattr(idx, "tz") and idx.tz is not None:
            idx_naive = idx.tz_convert(None) if hasattr(idx, "tz_convert") else idx.tz_localize(None)
        else:
            idx_naive = idx
    except Exception:
        idx_naive = hist_all.index

    for p, cutoff in _SLICES.items():
        try:
            mask = idx_naive >= cutoff
            slice_df = hist_all[mask]
            stats = _compute_perf(slice_df)
            if stats:
                periods_stats[p] = {
                    "change_pct": stats.change_pct,
                    "high": stats.high,
                    "low": stats.low,
                    "volatility_ann": stats.volatility_ann,
                    "volume_avg": stats.volume_avg,
                    "points": stats.points,
                }
        except Exception as e:
            log.debug(f"[market] period {p} fail: {e}")
            continue

    result = {
        "ticker": ticker,
        "current_price": round(current_price, 2) if current_price else None,
        "periods": periods_stats,
    }
    _cache_set(key, result)
    return result


def fetch_price_series(ticker: str, period: str = "1mo") -> dict:
    """Retourne une série temporelle {dates, closes} pour un period donné."""
    if period not in _PERIOD_CONFIG:
        period = "1mo"
    key = f"series:{ticker}:{period}"
    cached = _cache_get(key)
    if cached:
        return cached

    yf_period, yf_interval = _PERIOD_CONFIG[period]
    try:
        from core.yfinance_cache import get_ticker
        tk = get_ticker(ticker)
        hist = tk.history(period=yf_period, interval=yf_interval)
        if hist is None or len(hist) == 0:
            return {"ticker": ticker, "period": period, "error": "no data"}
        closes = hist["Close"].dropna()
        points = [
            {"date": str(idx.date() if hasattr(idx, "date") else idx), "close": round(float(v), 2)}
            for idx, v in closes.items()
        ]
        result = {
            "ticker": ticker,
            "period": period,
            "interval": yf_interval,
            "points": points,
        }
        _cache_set(key, result)
        return result
    except Exception as e:
        log.warning(f"[market] fetch_price_series {ticker}/{period} fail: {e}")
        return {"ticker": ticker, "period": period, "error": str(e)[:80]}


def _detect_benchmark(ticker: str, sector: str = "") -> tuple[str, str]:
    """Retourne (index_ticker, index_name) selon le pays du ticker.
    Ex: RMS.PA → (^FCHI, CAC 40) ; AAPL → (^GSPC, S&P 500).
    """
    t = ticker.upper()
    eu_fr = (".PA",)
    eu_de = (".DE",)
    eu_uk = (".L",)
    eu_ch = (".SW",)
    eu_nl = (".AS",)
    eu_it = (".MI",)
    eu_es = (".MC",)
    if any(t.endswith(s) for s in eu_fr):
        return "^FCHI", "CAC 40"
    if any(t.endswith(s) for s in eu_de):
        return "^GDAXI", "DAX 40"
    if any(t.endswith(s) for s in eu_uk):
        return "^FTSE", "FTSE 100"
    if any(t.endswith(s) for s in eu_ch):
        return "^SSMI", "SMI"
    if any(t.endswith(s) for s in eu_nl + eu_it + eu_es):
        return "^STOXX50E", "Euro Stoxx 50"
    if t.endswith(".T"):
        return "^N225", "Nikkei 225"
    if t.endswith(".HK"):
        return "^HSI", "Hang Seng"
    return "^GSPC", "S&P 500"


_SECTOR_ETFS = {
    "technology": ("XLK", "US Tech (XLK)"),
    "information technology": ("XLK", "US Tech (XLK)"),
    "healthcare": ("XLV", "US Healthcare (XLV)"),
    "health care": ("XLV", "US Healthcare (XLV)"),
    "financials": ("XLF", "US Financials (XLF)"),
    "financial services": ("XLF", "US Financials (XLF)"),
    "energy": ("XLE", "US Energy (XLE)"),
    "consumer cyclical": ("XLY", "US Cons. Disc. (XLY)"),
    "consumer discretionary": ("XLY", "US Cons. Disc. (XLY)"),
    "consumer defensive": ("XLP", "US Cons. Staples (XLP)"),
    "consumer staples": ("XLP", "US Cons. Staples (XLP)"),
    "industrials": ("XLI", "US Industrials (XLI)"),
    "communication services": ("XLC", "US Comm. (XLC)"),
    "utilities": ("XLU", "US Utilities (XLU)"),
    "real estate": ("XLRE", "US Real Estate (XLRE)"),
    "basic materials": ("XLB", "US Materials (XLB)"),
    "materials": ("XLB", "US Materials (XLB)"),
}


def fetch_price_series_multi(ticker: str, period: str = "1mo", sector: str = "") -> dict:
    """Retourne les séries prix du ticker + indice + ETF secteur,
    normalisées en base 100 au début de la période.
    """
    if period not in _PERIOD_CONFIG:
        period = "1mo"
    key = f"series_multi:{ticker}:{period}:{sector.lower()[:30]}"
    cached = _cache_get(key)
    if cached:
        return cached

    idx_ticker, idx_name = _detect_benchmark(ticker, sector)
    sec_ticker, sec_name = _SECTOR_ETFS.get(sector.lower().strip(), (None, None))

    series = {}
    main = fetch_price_series(ticker, period)
    if main.get("points"):
        series["main"] = {"name": ticker, "ticker": ticker, "points": main["points"]}

    idx = fetch_price_series(idx_ticker, period)
    if idx.get("points"):
        series["index"] = {"name": idx_name, "ticker": idx_ticker, "points": idx["points"]}

    if sec_ticker:
        sec = fetch_price_series(sec_ticker, period)
        if sec.get("points"):
            series["sector"] = {"name": sec_name, "ticker": sec_ticker, "points": sec["points"]}

    # Normalise en base 100 au 1er point de chaque série
    for s in series.values():
        pts = s.get("points") or []
        if pts and pts[0]["close"] > 0:
            base = pts[0]["close"]
            for p in pts:
                p["base100"] = round(p["close"] / base * 100, 2)

    result = {
        "ticker": ticker,
        "period": period,
        "sector": sector,
        "series": series,
    }
    _cache_set(key, result)
    return result
