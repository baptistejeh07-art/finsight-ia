"""
audit_indice_cmp.py - Test autonome du comparatif indice avec donnees reelles yfinance
Usage: python tools/audit_indice_cmp.py
"""
import sys, logging, math
from pathlib import Path
from datetime import date, timedelta
from statistics import median as med
from core.yfinance_cache import get_ticker

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

import yfinance as yf
import numpy as np

def _compute_stats(sym, rf=0.04):
    """Calcule perf YTD/1Y/3Y, vol, sharpe, max_dd depuis yfinance."""
    today = date.today()
    hist = get_ticker(sym).history(period="5y")
    if hist is None or hist.empty:
        return {}
    close = hist["Close"].dropna()

    def _perf(d_start):
        try:
            base = close[close.index.date <= d_start]
            if not len(base): return None
            return float(close.iloc[-1]) / float(base.iloc[-1]) - 1
        except: return None

    def _vol_1y():
        try:
            c1y = close[close.index.date >= today - timedelta(days=380)]
            r = c1y.pct_change().dropna()
            return float(r.std()) * np.sqrt(252) * 100 if len(r) > 20 else None
        except: return None

    def _sharpe(p1y, v):
        if p1y is None or v is None or v <= 0: return None
        return (p1y * 100 - rf * 100) / v

    def _maxdd():
        try:
            roll_max = close.cummax()
            dd = (close - roll_max) / roll_max
            return float(dd.min()) * 100
        except: return None

    def _perf_hist_norm():
        try:
            start = today - timedelta(days=365)
            c1y = close[close.index.date >= start]
            if len(c1y) < 5: return None, None
            base = float(c1y.iloc[0])
            dates = [str(d)[:10] for d in c1y.index.date]
            vals = [float(v) / base * 100 for v in c1y]
            return dates, vals
        except: return None, None

    p_ytd = _perf(date(today.year, 1, 1))
    p_1y  = _perf(today - timedelta(days=365))
    p_3y  = _perf(today - timedelta(days=3*365))
    p_5y  = _perf(today - timedelta(days=5*365))
    v     = _vol_1y()
    dates_h, vals_h = _perf_hist_norm()

    return {
        "perf_ytd":    p_ytd,
        "perf_1y":     p_1y,
        "perf_3y":     p_3y,
        "perf_5y":     p_5y,
        "vol_1y":      v,
        "sharpe_1y":   _sharpe(p_1y, v),
        "max_dd":      _maxdd(),
        "perf_dates":  dates_h,
        "perf_vals":   vals_h,
    }


def build_cmp_data():
    from cli_analyze import _fetch_real_sector_data

    print("Computing stats S&P 500 (^GSPC)...")
    sa = _compute_stats("^GSPC")
    print(f"  perf_1y={sa.get('perf_1y'):.1%}, vol={sa.get('vol_1y'):.1f}%, sharpe={sa.get('sharpe_1y'):.2f}")

    print("Computing stats CAC 40 (^FCHI)...")
    sb = _compute_stats("^FCHI")
    print(f"  perf_1y={sb.get('perf_1y'):.1%}, vol={sb.get('vol_1y'):.1f}%, sharpe={sb.get('sharpe_1y'):.2f}")

    print("Fetching sector tickers S&P 500 for PE/DivYield...")
    ta_tech = _fetch_real_sector_data("Technology", "S&P 500", max_tickers=5)
    ta_ind  = _fetch_real_sector_data("Industrials", "S&P 500", max_tickers=5)
    tickers_a = ta_tech + ta_ind

    print("Fetching sector tickers CAC 40 for PE/DivYield...")
    tb_tech = _fetch_real_sector_data("Technology", "CAC 40", max_tickers=5)
    tb_ind  = _fetch_real_sector_data("Industrials", "CAC 40", max_tickers=5)
    tickers_b = tb_tech + tb_ind
    if not tickers_b:
        print("  No CAC40 tickers -- using proxy data")

    def _med_field(tickers, field):
        vals = [t.get(field) for t in tickers if t.get(field) is not None]
        return med(vals) if vals else None

    def _top5(tickers):
        s = sorted(tickers, key=lambda x: x.get("score_global") or 0, reverse=True)[:5]
        return [(t.get("company", t["ticker"]), t["ticker"],
                 round(100/len(tickers), 1) if tickers else None,
                 t.get("sector", "")) for t in s]

    def _sector_cmp(ta, tb):
        secs_a = {}
        for t in ta:
            secs_a[t.get("sector","Autre")] = secs_a.get(t.get("sector","Autre"), 0) + 1
        secs_b = {}
        for t in tb:
            secs_b[t.get("sector","Autre")] = secs_b.get(t.get("sector","Autre"), 0) + 1
        all_secs = set(secs_a) | set(secs_b)
        n_a, n_b = max(len(ta), 1), max(len(tb), 1)
        return [(s, round(secs_a.get(s,0)/n_a*100,1), round(secs_b.get(s,0)/n_b*100,1))
                for s in all_secs]

    # Build perf_history
    dates_a, vals_a = sa.get("perf_dates"), sa.get("perf_vals")
    dates_b, vals_b = sb.get("perf_dates"), sb.get("perf_vals")
    ph = None
    if dates_a and dates_b:
        # Align on common length
        n = min(len(dates_a), len(dates_b))
        ph = {
            "dates":    dates_a[:n],
            "indice_a": vals_a[:n],
            "indice_b": vals_b[:n],
        }

    # CAC 40 Top 5 hardcoded (yfinance ne retourne pas les tickers CAC 40 par secteur)
    _TOP5_CAC40 = [
        ("LVMH Moet Hennessy",  "MC.PA",  11.5, "Consumer Discretionary"),
        ("TotalEnergies SE",    "TTE.PA",  8.3, "Energy"),
        ("Hermes International","RMS.PA",  7.8, "Consumer Discretionary"),
        ("Sanofi",              "SAN.PA",  6.2, "Healthcare"),
        ("Schneider Electric",  "SU.PA",   5.9, "Industrials"),
    ]

    cmp_data = {
        "name_a":  "S&P 500",
        "name_b":  "CAC 40",
        "date":    str(date.today()),
        # Signal & Score
        "signal_a": "Positif",
        "signal_b": "Neutre",
        "score_a":  68,
        "score_b":  54,
        # Perf
        "perf_ytd_a": sa.get("perf_ytd"),
        "perf_ytd_b": sb.get("perf_ytd"),
        "perf_1y_a":  sa.get("perf_1y"),
        "perf_1y_b":  sb.get("perf_1y"),
        "perf_3y_a":  sa.get("perf_3y"),
        "perf_3y_b":  sb.get("perf_3y"),
        "perf_5y_a":  sa.get("perf_5y"),
        "perf_5y_b":  sb.get("perf_5y"),
        # Risk
        "vol_1y_a":     sa.get("vol_1y"),
        "vol_1y_b":     sb.get("vol_1y"),
        "sharpe_1y_a":  sa.get("sharpe_1y"),
        "sharpe_1y_b":  sb.get("sharpe_1y"),
        "max_dd_a":     sa.get("max_dd"),
        "max_dd_b":     sb.get("max_dd"),
        # Valorisation
        "pe_fwd_a":    _med_field(tickers_a, "pe_ratio"),
        "pe_fwd_b":    None,  # CAC40 tickers absent via yfinance sector
        "div_yield_a": _med_field(tickers_a, "div_yield"),
        "div_yield_b": None,
        # Perf history
        "perf_history": ph,
        # Top5
        "top5_a": _top5(tickers_a),
        "top5_b": _TOP5_CAC40,
        # Secteurs
        "sector_comparison": _sector_cmp(tickers_a, tickers_b) if tickers_b else [],
        # LLM
        "llm": {},
    }
    return cmp_data


if __name__ == "__main__":
    cmp_data = build_cmp_data()

    print("\nGenerating PPTX...")
    from outputs.cmp_indice_pptx_writer import CmpIndicePPTXWriter
    out_pptx = "outputs/generated/cli_tests/audit_icmp_sp500_cac40.pptx"
    b = CmpIndicePPTXWriter.generate(cmp_data, output_path=out_pptx)
    print(f"PPTX OK: {len(b)} bytes -> {out_pptx}")

    print("Generating PDF...")
    from outputs.cmp_indice_pdf_writer import CmpIndicePDFWriter
    out_pdf = "outputs/generated/cli_tests/audit_icmp_sp500_cac40.pdf"
    pdf_b = CmpIndicePDFWriter.generate_bytes(cmp_data)
    Path(out_pdf).write_bytes(pdf_b)
    print(f"PDF OK: {len(pdf_b)} bytes -> {out_pdf}")

    print("\nDone.")