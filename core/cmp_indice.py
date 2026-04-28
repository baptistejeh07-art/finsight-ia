"""core/cmp_indice.py -- Builder du dict de comparaison pour deux indices.

Extrait de app.py (_fetch_cmp_indice_data) pour etre utilisable hors
Streamlit (backend FastAPI, CLI, etc.). Aucune dependance Streamlit.

Usage :
    from core.cmp_indice import build_cmp_indice_data, INDICE_CMP_OPTIONS
    data = build_cmp_indice_data("CAC40", "SP500",
                                  indice_data_a=indice_data,
                                  tickers_data_a=tickers_list)
    # data est un dict pret pour CmpIndicePPTXWriter / CmpIndicePDFWriter
    # + perf_history exploitable cote frontend pour un chart interactif.
"""
from __future__ import annotations
import logging
import math as _m
from datetime import date as _d, timedelta as _td
from statistics import median as _med_fn
from typing import Optional

from core.yfinance_cache import get_ticker

log = logging.getLogger(__name__)


# Liste canonique des indices comparables : (display_name, yf_symbol, currency)
# NIKKEI225 / NASDAQ100 / DOWJONES retirés temporairement (bug #100, 27/04/2026) :
# le pipeline `_INDICE_META` (cli_analyze.py:1716) ne les supporte pas, fallback
# silencieux sur S&P 500 → faux rapport. Ré-ajouter quand `_INDICE_META` +
# `_SECTOR_TICKERS` couvriront NASDAQ/Dow (USD, ~3-4h) puis Nikkei (JPY, ~1-2j).
INDICE_CMP_OPTIONS: dict[str, tuple[str, str, str]] = {
    # Codes courts (anciens)
    "CAC40":      ("CAC 40",        "^FCHI",     "EUR"),
    "SP500":      ("S&P 500",       "^GSPC",     "USD"),
    "DAX40":      ("DAX 40",        "^GDAXI",    "EUR"),
    "FTSE100":    ("FTSE 100",      "^FTSE",     "GBP"),
    "STOXX50":    ("Euro Stoxx 50", "^STOXX50E", "EUR"),
    # Display names (avec espaces) — utilisés par run_cmp_indice("CAC 40", ...)
    "CAC 40":     ("CAC 40",        "^FCHI",     "EUR"),
    "S&P 500":    ("S&P 500",       "^GSPC",     "USD"),
    "DAX 40":     ("DAX 40",        "^GDAXI",    "EUR"),
    "FTSE 100":   ("FTSE 100",      "^FTSE",     "GBP"),
    "Euro Stoxx 50": ("Euro Stoxx 50", "^STOXX50E", "EUR"),
}

# Indices entièrement supportés par le pipeline d'analyse (display names + codes
# courts). Source de vérité pour la whitelist backend / frontend / Streamlit.
INDICE_SUPPORTED_NAMES: frozenset[str] = frozenset(
    name for (name, *_rest) in INDICE_CMP_OPTIONS.values()
)
INDICE_SUPPORTED_CODES: frozenset[str] = frozenset(INDICE_CMP_OPTIONS.keys())

_MOIS_FR = {
    1: "janvier", 2: "fevrier", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "aout", 9: "septembre", 10: "octobre", 11: "novembre",
    12: "decembre",
}

# Poids sectoriels approximatifs (yfinance ne fournit pas les constituants des
# indices non-US). Sources : factsheets providers (MSCI, iShares, Euronext) 2025.
_SECTOR_WEIGHTS_APPROX = {
    "SP500":     {"Technology": 29.0, "Financials": 13.0, "Healthcare": 12.0,
                  "Consumer Discretionary": 10.0, "Industrials": 8.5,
                  "Communication Services": 8.0, "Consumer Staples": 6.0,
                  "Energy": 4.0, "Utilities": 2.5, "Materials": 2.5,
                  "Real Estate": 2.5},
    "NASDAQ100": {"Technology": 53.0, "Communication Services": 16.0,
                  "Consumer Discretionary": 14.0, "Healthcare": 6.0,
                  "Industrials": 5.0, "Consumer Staples": 3.0, "Financials": 2.0},
    "DAX40":     {"Financials": 18.0, "Consumer Discretionary": 16.0,
                  "Industrials": 15.0, "Materials": 12.0, "Healthcare": 11.0,
                  "Technology": 10.0, "Consumer Staples": 8.0, "Energy": 5.0,
                  "Utilities": 3.0, "Communication Services": 2.0},
    "FTSE100":   {"Financials": 22.0, "Consumer Staples": 15.0, "Energy": 14.0,
                  "Healthcare": 12.0, "Industrials": 10.0, "Materials": 8.0,
                  "Consumer Discretionary": 8.0, "Technology": 4.0,
                  "Utilities": 4.0, "Telecommunication": 3.0},
    "CAC40":     {"Consumer Discretionary": 25.0, "Industrials": 18.0,
                  "Financials": 16.0, "Healthcare": 12.0, "Technology": 9.0,
                  "Consumer Staples": 8.0, "Materials": 6.0,
                  "Energy": 3.0, "Utilities": 3.0},
    "STOXX50":   {"Financials": 20.0, "Consumer Discretionary": 18.0,
                  "Industrials": 15.0, "Healthcare": 12.0, "Technology": 10.0,
                  "Consumer Staples": 10.0, "Energy": 6.0,
                  "Materials": 5.0, "Utilities": 4.0},
}

# Top 5 constituants hardcoded (yfinance info.constituents souvent vide).
# A maintenir manuellement : poids rebalances tous les trimestres chez providers.
_TOP5_HARDCODED = {
    "SP500": [
        ("Apple Inc.", "AAPL", 7.2, "Technology"),
        ("Microsoft Corp.", "MSFT", 6.8, "Technology"),
        ("NVIDIA Corp.", "NVDA", 5.5, "Technology"),
        ("Amazon.com Inc.", "AMZN", 3.6, "Consumer Discretionary"),
        ("Alphabet Inc. A", "GOOGL", 2.1, "Communication Services"),
    ],
    "NASDAQ100": [
        ("Apple Inc.", "AAPL", 9.0, "Technology"),
        ("Microsoft Corp.", "MSFT", 8.5, "Technology"),
        ("NVIDIA Corp.", "NVDA", 7.2, "Technology"),
        ("Amazon.com Inc.", "AMZN", 5.0, "Consumer Discretionary"),
        ("Meta Platforms", "META", 4.5, "Communication Services"),
    ],
    "DAX40": [
        ("SAP SE", "SAP", 13.5, "Technology"),
        ("Siemens AG", "SIE", 8.2, "Industrials"),
        ("Allianz SE", "ALV", 7.8, "Financials"),
        ("Deutsche Telekom", "DTE", 6.5, "Communication Services"),
        ("BASF SE", "BAS", 4.2, "Materials"),
    ],
    "FTSE100": [
        ("AstraZeneca PLC", "AZN", 9.5, "Healthcare"),
        ("Shell PLC", "SHEL", 7.2, "Energy"),
        ("HSBC Holdings", "HSBA", 6.8, "Financials"),
        ("Unilever PLC", "ULVR", 5.1, "Consumer Staples"),
        ("BP PLC", "BP", 4.5, "Energy"),
    ],
    "CAC40": [
        ("LVMH Moet Hennessy", "MC.PA", 11.5, "Consumer Discretionary"),
        ("TotalEnergies SE", "TTE.PA", 8.3, "Energy"),
        ("Hermes International", "RMS.PA", 7.8, "Consumer Discretionary"),
        ("Sanofi", "SAN.PA", 6.2, "Healthcare"),
        ("Schneider Electric", "SU.PA", 5.9, "Industrials"),
    ],
    "STOXX50": [
        ("ASML Holding", "ASML", 8.5, "Technology"),
        ("LVMH Moet Hennessy", "MC.PA", 6.3, "Consumer Discretionary"),
        ("Siemens AG", "SIE", 5.1, "Industrials"),
        ("SAP SE", "SAP", 4.9, "Technology"),
        ("TotalEnergies SE", "TTE.PA", 4.2, "Energy"),
    ],
    "NIKKEI225": [
        ("Toyota Motor Corp", "7203.T", 3.8, "Consumer Discretionary"),
        ("Softbank Group", "9984.T", 3.2, "Technology"),
        ("Sony Group Corp", "6758.T", 2.9, "Consumer Discretionary"),
        ("Keyence Corp", "6861.T", 2.5, "Technology"),
        ("FANUC Corp", "6954.T", 2.1, "Industrials"),
    ],
    "DOWJONES": [
        ("UnitedHealth Group", "UNH", 8.5, "Healthcare"),
        ("Goldman Sachs", "GS", 6.8, "Financials"),
        ("Microsoft Corp.", "MSFT", 5.9, "Technology"),
        ("Home Depot Inc.", "HD", 5.5, "Consumer Discretionary"),
        ("Caterpillar Inc.", "CAT", 4.8, "Industrials"),
    ],
}

# Valorisations fallback (yfinance.info souvent vide pour ^GSPC, ^FCHI etc.)
_PE_FALLBACK = {
    "SP500": 21.5, "SPX": 21.5, "S&P500": 21.5,
    "CAC40": 14.0, "DAX40": 13.5, "FTSE100": 12.0,
    "STOXX50": 13.5, "EUROSTOXX50": 13.5,
    "NASDAQ100": 28.0, "DOWJONES": 18.0, "NIKKEI225": 17.5,
}
_PB_FALLBACK = {
    "SP500": 4.5, "SPX": 4.5, "S&P500": 4.5,
    "CAC40": 1.8, "DAX40": 1.6, "FTSE100": 1.7,
    "STOXX50": 1.9, "EUROSTOXX50": 1.9,
    "NASDAQ100": 6.5, "DOWJONES": 5.0, "NIKKEI225": 1.5,
}
_DY_FALLBACK = {
    "SP500": 0.014, "SPX": 0.014, "S&P500": 0.014,
    "CAC40": 0.032, "DAX40": 0.028, "FTSE100": 0.038,
    "STOXX50": 0.030, "EUROSTOXX50": 0.030,
    "NASDAQ100": 0.008, "DOWJONES": 0.020, "NIKKEI225": 0.020,
}


def _compute_stats(hist, today_dt: _d, rf_annual: float = 0.04):
    """Retourne (perf_ytd, perf_1y, perf_3y, perf_5y, vol_1y, sharpe_1y, max_dd)."""
    if hist is None or hist.empty:
        return (None,) * 7
    try:
        import numpy as _np
        close = hist["Close"].dropna()
        if len(close) < 5:
            return (None,) * 7

        # Perf YTD
        try:
            jan1 = _d(today_dt.year, 1, 1)
            ytd_base = close[close.index.date <= jan1]
            perf_ytd = (float(close.iloc[-1]) / float(ytd_base.iloc[-1]) - 1) if len(ytd_base) > 0 else None
        except Exception:
            perf_ytd = None

        # Perf 1Y / 3Y / 5Y
        def _perf_n_years(n_years: int):
            try:
                d_n = today_dt - _td(days=n_years * 365)
                base = close[close.index.date <= d_n]
                return (float(close.iloc[-1]) / float(base.iloc[-1]) - 1) if len(base) > 0 else None
            except Exception:
                return None

        perf_1y = _perf_n_years(1)
        perf_3y = _perf_n_years(3)
        perf_5y = _perf_n_years(5)

        # Vol 1Y (annualized)
        try:
            d_1y = today_dt - _td(days=380)
            close_1y = close[close.index.date >= d_1y]
            rets_1y = close_1y.pct_change().dropna()
            vol_1y = float(rets_1y.std()) * _np.sqrt(252) * 100 if len(rets_1y) > 20 else None
        except Exception:
            vol_1y = None

        # Sharpe 1Y
        try:
            if vol_1y and perf_1y is not None:
                ret_1y_pct = perf_1y * 100
                rf_pct = rf_annual * 100
                sharpe_1y = (ret_1y_pct - rf_pct) / vol_1y if vol_1y > 0 else None
            else:
                sharpe_1y = None
        except Exception:
            sharpe_1y = None

        # Max Drawdown 1Y
        try:
            close_1y_dd = close[close.index.date >= (today_dt - _td(days=380))]
            if len(close_1y_dd) > 5:
                rolling_max = close_1y_dd.cummax()
                drawdown = (close_1y_dd - rolling_max) / rolling_max
                max_dd = float(drawdown.min())
            else:
                max_dd = None
        except Exception:
            max_dd = None

        return perf_ytd, perf_1y, perf_3y, perf_5y, vol_1y, sharpe_1y, max_dd

    except Exception as _ex:
        log.warning(f"[cmp_indice] _compute_stats error: {_ex}")
        return (None,) * 7


def _score_proxy(perf_1y, sharpe_1y, vol_1y, perf_3y):
    """Score composite proxy 0-100 depuis stats de performance/risque."""
    sc = 50  # baseline neutre
    try:
        if perf_1y is not None:
            sc += max(-15, min(25, float(perf_1y) * 100 * 1.0))
        if sharpe_1y is not None:
            sc += max(-10, min(15, float(sharpe_1y) * 10))
        if vol_1y is not None:
            sc -= max(-5, min(10, (float(vol_1y) - 15) * 0.5))
        if perf_3y is not None:
            sc += max(-5, min(5, float(perf_3y) * 100 * 0.1))
    except Exception:
        pass
    return int(max(0, min(100, sc)))


def build_cmp_indice_data(
    universe_a: str,
    universe_b: str,
    indice_data_a: Optional[dict] = None,
    tickers_data_a: Optional[list] = None,
) -> dict:
    """Construit le dict de comparaison pour deux indices.

    Args:
        universe_a : cle d'indice A (ex: "CAC40", "SP500"). Voir INDICE_CMP_OPTIONS.
        universe_b : cle d'indice B.
        indice_data_a : resultat de _fetch_real_indice_data(universe_a) (optionnel).
                        Si None, certaines infos secondaires (score_global, erp)
                        prennent des defauts neutres.
        tickers_data_a : liste de constituants de l'indice A (output de
                         _fetch_real_indice_data). Sert a calculer compo
                         sectorielle et mediane P/E, P/B, div_yield de A.

    Returns:
        dict pret pour CmpIndicePPTXWriter / CmpIndicePDFWriter / CmpIndiceXlsxWriter,
        et exploitable cote frontend pour un chart interactif (perf_history
        contient dates + series base 100 pour les deux indices).
    """
    indice_data_a = indice_data_a or {}
    tickers_data_a = tickers_data_a or []

    _today = _d.today()
    today_str = f"{_today.day} {_MOIS_FR[_today.month]} {_today.year}"

    name_a, yf_a, cur_a = INDICE_CMP_OPTIONS.get(
        universe_a, (indice_data_a.get("indice", universe_a), "^GSPC", "USD"))
    name_b, yf_b, cur_b = INDICE_CMP_OPTIONS.get(
        universe_b, (universe_b, "^GSPC", "USD"))

    # Fetch prix indice B
    try:
        hist_b = get_ticker(yf_b).history(period="5y")
    except Exception:
        hist_b = None

    (perf_ytd_b, perf_1y_b, perf_3y_b, perf_5y_b,
     vol_1y_b, sharpe_1y_b, max_dd_b) = _compute_stats(hist_b, _today)

    # Indice B -- valorisation depuis yfinance (souvent None pour les indices)
    pe_fwd_b, pb_b, div_yield_b, erp_b_str = None, None, None, "\u2014"
    try:
        info_b = get_ticker(yf_b).info or {}
        pe_fwd_b = info_b.get("forwardPE") or info_b.get("trailingPE")
        pb_b = info_b.get("priceToBook")
        div_yield_b = info_b.get("dividendYield")
    except Exception:
        pass

    # ERP indice B -- rf 10Y (simplification : TNX pour tous, fallback 4%)
    try:
        rf_hist_b = get_ticker("^TNX").history(period="5d")
        rf_b = float(rf_hist_b["Close"].iloc[-1]) / 100 if not rf_hist_b.empty else 0.04
        if perf_1y_b and vol_1y_b:
            erp_val_b = (perf_1y_b - rf_b) * 100
            erp_b_str = f"{erp_val_b:+.1f}".replace(".", ",") + "\u00a0%"
    except Exception:
        pass

    # Perf history pour graphique base 100 (1 an glissant)
    perf_history = None
    try:
        start_str = (_today - _td(days=380)).strftime("%Y-%m-%d")
        hist_a_1y = get_ticker(yf_a).history(start=start_str)
        hist_b_1y = get_ticker(yf_b).history(start=start_str)

        if (hist_a_1y is not None and not hist_a_1y.empty
                and hist_b_1y is not None and not hist_b_1y.empty):
            close_a = hist_a_1y["Close"].dropna()
            close_b = hist_b_1y["Close"].dropna()

            dates_a = set(str(d)[:10] for d in close_a.index)
            dates_b = set(str(d)[:10] for d in close_b.index)
            common = sorted(dates_a & dates_b)[:380]

            if len(common) > 10:
                ca_map = {str(d)[:10]: float(v) for d, v in zip(close_a.index, close_a)}
                cb_map = {str(d)[:10]: float(v) for d, v in zip(close_b.index, close_b)}
                base_a = ca_map.get(common[0], 1) or 1
                base_b = cb_map.get(common[0], 1) or 1

                perf_history = {
                    "dates":    common,
                    "indice_a": [round(ca_map.get(d, base_a) / base_a * 100, 1) for d in common],
                    "indice_b": [round(cb_map.get(d, base_b) / base_b * 100, 1) for d in common],
                }
    except Exception as _ex:
        log.warning(f"[cmp_indice] perf_history error: {_ex}")

    # Extraction indice A depuis tickers_data_a + indice_data_a
    perf_ytd_a, perf_1y_a, perf_3y_a, perf_5y_a = None, None, None, None
    vol_1y_a, sharpe_1y_a, max_dd_a = None, None, None
    try:
        if yf_a:
            hist_a5 = get_ticker(yf_a).history(period="5y")
            (perf_ytd_a, perf_1y_a, perf_3y_a, perf_5y_a,
             vol_1y_a, sharpe_1y_a, max_dd_a) = _compute_stats(hist_a5, _today)
    except Exception:
        pass

    # Valorisation A depuis tickers_data_a (medianes)
    pe_fwd_a, pb_a, div_yield_a = None, None, None
    erp_a_str = indice_data_a.get("erp", "\u2014")

    try:
        _pe_list = [float(t.get("pe_ratio") or t.get("pe") or 0)
                    for t in tickers_data_a
                    if (t.get("pe_ratio") or t.get("pe"))
                    and 5 < float(t.get("pe_ratio") or t.get("pe") or 0) < 100]
        if _pe_list:
            pe_fwd_a = _med_fn(_pe_list)
    except Exception:
        pass

    try:
        _pb_list = [float(t.get("pb") or t.get("priceToBook") or 0)
                    for t in tickers_data_a
                    if (t.get("pb") or t.get("priceToBook"))
                    and 0 < float(t.get("pb") or t.get("priceToBook") or 0) < 30]
        if _pb_list:
            pb_a = _med_fn(_pb_list)
    except Exception:
        pass

    try:
        _dy_list = [float(t.get("dividend_yield") or 0)
                    for t in tickers_data_a
                    if t.get("dividend_yield")
                    and float(t.get("dividend_yield") or 0) > 0]
        if _dy_list:
            div_yield_a = _med_fn(_dy_list) / 100  # % -> decimal
    except Exception:
        pass

    # Composition sectorielle A (depuis constituants)
    sector_weights_a: dict = {}
    for t in tickers_data_a:
        sec = t.get("sector") or "Autre"
        sector_weights_a[sec] = sector_weights_a.get(sec, 0) + 1
    total_a = sum(sector_weights_a.values()) or 1
    sector_weights_a = {k: round(v / total_a * 100, 1)
                        for k, v in sector_weights_a.items()
                        if k != "Autre"}
    # Bug B13 audit 27/04 : si tickers_data_a vide (DAX/FTSE/STOXX peu fournis
    # par yfinance), fallback sur poids sectoriels approximatifs comme pour B.
    # Sinon le chart Composition Sectorielle n'affiche que B.
    if not sector_weights_a:
        sector_weights_a = _SECTOR_WEIGHTS_APPROX.get(universe_a, {})

    # Composition sectorielle B (approximation depuis poids connus)
    sector_weights_b = _SECTOR_WEIGHTS_APPROX.get(universe_b, {})

    # Merge A + B pour sector_comparison
    all_sectors = sorted(set(list(sector_weights_a.keys()) + list(sector_weights_b.keys())))
    sector_comparison = []
    for sec in all_sectors:
        wa = sector_weights_a.get(sec)
        wb = sector_weights_b.get(sec)
        sector_comparison.append((sec, wa, wb))
    sector_comparison.sort(key=lambda x: (x[1] or 0) + (x[2] or 0), reverse=True)

    # Top 5 constituants A (tries par market cap)
    _all_mcaps = [t.get("market_cap") or 0 for t in tickers_data_a]
    _total_mcap = sum(_all_mcaps) or 1
    top5_a_raw = sorted(tickers_data_a,
                        key=lambda t: t.get("market_cap") or 0, reverse=True)[:5]
    top5_a = [
        (
            t.get("company", t.get("ticker", "")),
            t.get("ticker", ""),
            round((t.get("market_cap") or 0) / _total_mcap * 100, 1)
            if (t.get("market_cap") or 0) > 0 else None,
            t.get("sector", ""),
        )
        for t in top5_a_raw
    ]
    # Bug B15 audit 27/04 : fallback sur hardcoded si tickers_data_a vide
    # (DAX/FTSE/STOXX peu fournis par yfinance free tier).
    if not top5_a:
        top5_a = _TOP5_HARDCODED.get(universe_a, [])

    # Top 5 B (hardcoded)
    top5_b = _TOP5_HARDCODED.get(universe_b, [])

    # ERP A -- fallback si non deja calcule dans indice_data_a
    try:
        if isinstance(erp_a_str, str) and erp_a_str not in ("\u2014", "---", ""):
            pass
        elif vol_1y_a and perf_1y_a:
            erp_val_a = (perf_1y_a - 0.04) * 100
            erp_a_str = f"{erp_val_a:+.1f}".replace(".", ",") + "\u00a0%"
    except Exception:
        pass

    # Score composite proxy pour B
    score_b_proxy = _score_proxy(perf_1y_b, sharpe_1y_b, vol_1y_b, perf_3y_b)
    if score_b_proxy >= 65:
        signal_b_proxy = "Surpondérer"
    elif score_b_proxy >= 45:
        signal_b_proxy = "Neutre"
    else:
        signal_b_proxy = "Sous-pondérer"

    # Fallbacks valorisation indices (yfinance.info vide pour ^GSPC etc.)
    if pe_fwd_b is None:
        pe_fwd_b = _PE_FALLBACK.get(universe_b)
    if pb_b is None:
        pb_b = _PB_FALLBACK.get(universe_b)
    if div_yield_b is None:
        div_yield_b = _DY_FALLBACK.get(universe_b)
    if pe_fwd_a is None:
        pe_fwd_a = _PE_FALLBACK.get(universe_a)
    if pb_a is None:
        pb_a = _PB_FALLBACK.get(universe_a)
    if div_yield_a is None:
        div_yield_a = _DY_FALLBACK.get(universe_a)

    return {
        "name_a":       name_a,
        "name_b":       name_b,
        "code_a":       universe_a,
        "code_b":       universe_b,
        "ticker_a":     yf_a,
        "ticker_b":     yf_b,
        "currency_a":   cur_a,
        "currency_b":   cur_b,
        "date":         today_str,
        # Performance
        "perf_ytd_a":   perf_ytd_a,  "perf_ytd_b":   perf_ytd_b,
        "perf_1y_a":    perf_1y_a,   "perf_1y_b":    perf_1y_b,
        "perf_3y_a":    perf_3y_a,   "perf_3y_b":    perf_3y_b,
        "perf_5y_a":    perf_5y_a,   "perf_5y_b":    perf_5y_b,
        # Risque
        "vol_1y_a":     vol_1y_a,    "vol_1y_b":     vol_1y_b,
        "sharpe_1y_a":  sharpe_1y_a, "sharpe_1y_b":  sharpe_1y_b,
        "max_dd_a":     max_dd_a,    "max_dd_b":     max_dd_b,
        # Valorisation
        "pe_fwd_a":     pe_fwd_a,    "pe_fwd_b":     pe_fwd_b,
        "pb_a":         pb_a,        "pb_b":         pb_b,
        "div_yield_a":  div_yield_a, "div_yield_b":  div_yield_b,
        "erp_a":        erp_a_str,   "erp_b":        erp_b_str,
        # Score
        "score_a":      indice_data_a.get("score_global", 50),
        "score_b":      score_b_proxy,
        "signal_a":     indice_data_a.get("signal_global", "Neutre"),
        "signal_b":     signal_b_proxy,
        # Composition
        "sector_comparison": sector_comparison,
        "top5_a":       top5_a,
        "top5_b":       top5_b,
        # Historique (base 100, exploitable PNG matplotlib ET JSON pour chart interactif)
        "perf_history": perf_history,
    }
