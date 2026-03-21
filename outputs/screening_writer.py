# =============================================================================
# FinSight IA — Screening Writer
# outputs/screening_writer.py
#
# Genere un fichier Excel multi-feuilles style IB a partir de tickers_data.
# Structure : DASHBOARD / COMPARABLES / RATIOS DETAILLES / PAR SECTEUR / DONNEES BRUTES
# Zero LLM. Pure openpyxl.
# =============================================================================

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any, Optional

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side,
)
from openpyxl.utils import get_column_letter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Palette couleurs (IB style)
# ---------------------------------------------------------------------------
_NAVY   = "1B2A4A"
_DARK   = "2C3E50"
_LGRAY  = "F4F6F7"
_MGRAY  = "BDC3C7"
_WHITE  = "FFFFFF"
_GREEN  = "1a7a52"
_RED    = "C0392B"
_GOLD   = "B8922A"
_BLACK  = "111111"

_FILL_NAVY  = PatternFill("solid", fgColor=_NAVY)
_FILL_DARK  = PatternFill("solid", fgColor=_DARK)
_FILL_LGRAY = PatternFill("solid", fgColor=_LGRAY)
_FILL_MGRAY = PatternFill("solid", fgColor="D5D8DC")
_FILL_GOLD  = PatternFill("solid", fgColor="F0D080")

_FONT_HDR   = Font(name="Calibri", bold=True, color=_WHITE, size=10)
_FONT_SHDR  = Font(name="Calibri", bold=True, color=_WHITE, size=9)
_FONT_TITLE = Font(name="Calibri", bold=True, color=_WHITE, size=11)
_FONT_BOLD  = Font(name="Calibri", bold=True, color=_BLACK, size=9)
_FONT_BODY  = Font(name="Calibri", color=_BLACK, size=9)
_FONT_SMALL = Font(name="Calibri", color="5D6D7E", size=8, italic=True)
_FONT_POS   = Font(name="Calibri", color=_GREEN, size=9, bold=True)
_FONT_NEG   = Font(name="Calibri", color=_RED,   size=9, bold=True)

_ALIGN_C = Alignment(horizontal="center", vertical="center", wrap_text=False)
_ALIGN_L = Alignment(horizontal="left",   vertical="center")
_ALIGN_R = Alignment(horizontal="right",  vertical="center")

_THIN = Side(style="thin", color=_MGRAY)
_BORDER_THIN = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

_CCY = {"USD": "$", "EUR": "\u20ac", "GBP": "\u00a3", "CHF": "CHF ", "JPY": "\u00a5"}

# ---------------------------------------------------------------------------
# Helpers formatage
# ---------------------------------------------------------------------------

def _sym(ccy: Optional[str]) -> str:
    return _CCY.get(ccy or "USD", "$")


def _na(v: Any, fallback: str = "\u2014") -> str:
    return fallback if v is None else str(v)


def _fmt_price(v: Any, ccy: str = "USD") -> str:
    if v is None:
        return "\u2014"
    try:
        return f"{_sym(ccy)}{float(v):,.2f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_mds(v: Any, ccy: str = "USD") -> str:
    if v is None:
        return "\u2014"
    try:
        return f"{_sym(ccy)}{float(v):,.1f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_mult(v: Any) -> str:
    if v is None:
        return "\u2014"
    try:
        return f"{float(v):.1f}x"
    except (ValueError, TypeError):
        return str(v)


def _fmt_pct(v: Any, sign: bool = True) -> str:
    if v is None:
        return "\u2014"
    try:
        f = float(v)
        prefix = "+" if sign and f >= 0 else ""
        return f"{prefix}{f:.1f}%"
    except (ValueError, TypeError):
        return str(v)


def _fmt_score(v: Any) -> str:
    if v is None:
        return "N/A"
    try:
        return f"{int(float(v))}/100"
    except (ValueError, TypeError):
        return str(v)


def _fmt_z(v: Any) -> str:
    if v is None:
        return "\u2014"
    try:
        return f"{float(v):.2f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_cov(v: Any) -> str:
    if v is None:
        return "\u2014"
    if str(v).lower() in ("n/a", "none", "inf"):
        return "n/a"
    try:
        return f"{float(v):.0f}"
    except (ValueError, TypeError):
        return str(v)


def _sector_short(s: str) -> str:
    MAP = {
        "Consumer Discretionary": "Consumer Disc.",
        "Consumer Staples":       "Consumer Staples",
        "Information Technology": "Technology",
        "Communication Services": "Comm. Services",
        "Health Care":            "Healthcare",
        "Healthcare":             "Healthcare",
    }
    if not s:
        return ""
    return MAP.get(s, s)


def _signal(score: Optional[float]) -> str:
    if score is None:
        return "Neutre"
    s = float(score)
    if s >= 75:
        return "Surpond\u00e9rer"
    if s >= 55:
        return "Neutre"
    return "Sous-pond\u00e9rer"


def _dominant_ccy(data: list[dict]) -> str:
    from collections import Counter
    c = Counter(t.get("currency", "USD") or "USD" for t in data)
    return c.most_common(1)[0][0] if c else "USD"


# ---------------------------------------------------------------------------
# Helpers openpyxl
# ---------------------------------------------------------------------------

def _w(ws, row: int, col: int, value: Any,
       font=None, fill=None, align=None, border=None, num_fmt: str = None):
    cell = ws.cell(row=row, column=col, value=value)
    if font:   cell.font   = font
    if fill:   cell.fill   = fill
    if align:  cell.alignment = align
    if border: cell.border = border
    if num_fmt: cell.number_format = num_fmt
    return cell


def _hdr(ws, row: int, col: int, value: str, span: int = 1,
         fill=None, font=None):
    """Cellule header avec merge optionnel."""
    cell = _w(ws, row, col, value,
              font=font or _FONT_HDR,
              fill=fill or _FILL_NAVY,
              align=_ALIGN_C)
    if span > 1:
        ws.merge_cells(
            start_row=row, start_column=col,
            end_row=row, end_column=col + span - 1,
        )
    return cell


def _title(ws, row: int, value: str, ncols: int, date_str: str = ""):
    txt = f"{value}  \u2022  {date_str}" if date_str else value
    _hdr(ws, row, 1, txt, span=ncols,
         font=_FONT_TITLE, fill=_FILL_NAVY)
    ws.row_dimensions[row].height = 22


def _section(ws, row: int, value: str, ncols: int):
    _hdr(ws, row, 1, f"  {value}", span=ncols,
         font=_FONT_SHDR, fill=_FILL_DARK)
    ws.row_dimensions[row].height = 16


def _set_col_widths(ws, widths: list[float]):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _freeze(ws, row: int, col: int):
    from openpyxl.utils import get_column_letter
    ws.freeze_panes = f"{get_column_letter(col)}{row}"


# ---------------------------------------------------------------------------
# SHEET 1 — DASHBOARD
# ---------------------------------------------------------------------------

def _build_dashboard(wb: Workbook, data: list[dict],
                     universe_name: str, date_str: str):
    ws = wb.create_sheet("DASHBOARD")
    N = len(data)
    ccy = _dominant_ccy(data)
    NCOLS = 20

    # --- Titre ---
    _title(ws, 1, f"FinSight IA  \u2022  Screening {N} soci\u00e9t\u00e9s  \u2022  {universe_name}",
           NCOLS, date_str)
    _w(ws, 2, 1,
       f"Pipeline : Supabase Cache \u2192 Calculs Python/NumPy \u2192 Cours temps r\u00e9el yfinance"
       f"  \u2022  Usage confidentiel  \u2022  FinSight IA v1.0",
       font=_FONT_SMALL, fill=_FILL_DARK,
       align=Alignment(horizontal="left", vertical="center"))
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=NCOLS)
    ws.row_dimensions[2].height = 14

    # --- KPIs row ---
    best = max(data, key=lambda x: x.get("score_global") or 0)
    sectors = [t.get("sector") or "" for t in data]
    dominant_sector = max(set(sectors), key=sectors.count) if sectors else ""

    kpi_labels = [
        ("Univers analys\u00e9", f"{N} soci\u00e9t\u00e9s",   1),
        ("Meilleur score global",
         f"{best['ticker']} \u2192 {_fmt_score(best.get('score_global'))}",  5),
        ("Secteur dominant", _sector_short(dominant_sector),  9),
        ("Date d'analyse", date_str, 13),
    ]
    for label, val, col in kpi_labels:
        _w(ws, 4, col, val,   font=_FONT_BOLD, align=_ALIGN_C, fill=_FILL_GOLD)
        ws.merge_cells(start_row=4, start_column=col, end_row=4, end_column=col+3)
        _w(ws, 5, col, label, font=_FONT_SMALL, align=_ALIGN_C)
        ws.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col+3)

    ws.row_dimensions[4].height = 20
    ws.row_dimensions[5].height = 14

    # --- Top 5 par categorie ---
    row = 7
    cats = [
        ("TOP 5  \u2022  VALUE",    "score_value",    "EV/EBITDA",   "ev_ebitda", _fmt_mult, 1),
        ("TOP 5  \u2022  GROWTH",   "score_growth",   "Cro. Rev.",   "revenue_growth", _fmt_pct, 5),
        ("TOP 5  \u2022  QUALITY",  "score_quality",  "Altman Z",    "altman_z",  _fmt_z,  10),
        ("TOP 5  \u2022  MOMENTUM", "score_momentum", "Perf. 52W",   "momentum_52w", _fmt_pct, 15),
    ]
    for label, score_key, metric_label, metric_key, fmt_fn, col in cats:
        _hdr(ws, row, col, label, span=4, fill=_FILL_NAVY)
        _w(ws, row+1, col,   "Rang",     font=_FONT_BOLD, fill=_FILL_LGRAY, align=_ALIGN_C)
        _w(ws, row+1, col+1, "Ticker",   font=_FONT_BOLD, fill=_FILL_LGRAY, align=_ALIGN_C)
        _w(ws, row+1, col+2, "Soci\u00e9t\u00e9", font=_FONT_BOLD, fill=_FILL_LGRAY, align=_ALIGN_C)
        _w(ws, row+1, col+3, metric_label, font=_FONT_BOLD, fill=_FILL_LGRAY, align=_ALIGN_C)

        top5 = sorted(
            [t for t in data if t.get(score_key) is not None],
            key=lambda x: x[score_key], reverse=True
        )[:5]

        for i, t in enumerate(top5, 1):
            r = row + 1 + i
            fill = _FILL_LGRAY if i % 2 == 0 else None
            _w(ws, r, col,   i,                  font=_FONT_BODY, fill=fill, align=_ALIGN_C)
            _w(ws, r, col+1, t.get("ticker",""),  font=_FONT_BOLD, fill=fill, align=_ALIGN_C)
            _w(ws, r, col+2, t.get("company",""), font=_FONT_BODY, fill=fill, align=_ALIGN_L)
            _w(ws, r, col+3, fmt_fn(t.get(metric_key)), font=_FONT_BODY, fill=fill, align=_ALIGN_R)

    ws.row_dimensions[row].height = 16
    ws.row_dimensions[row+1].height = 14

    # --- Top 10 global ---
    row = 14
    _section(ws, row, "TOP 10  \u2022  CLASSEMENT GLOBAL  \u2022  Score composite Value / Growth / Quality / Momentum", NCOLS)
    hdrs10 = ["Rang","Ticker","Soci\u00e9t\u00e9","Secteur","Score Global",
              "Score Value","Score Growth","Score Quality","Score Mom.",
              f"Cours ({_sym(ccy)})","Mkt Cap (Mds)",
              "EV/EBITDA","P/E","Marge EBITDA","Cro. Rev.","Mom. 52W",
              "Altman Z","Next Earnings"]
    for j, h in enumerate(hdrs10, 1):
        _w(ws, row+1, j, h, font=_FONT_BOLD, fill=_FILL_MGRAY, align=_ALIGN_C)

    top10 = sorted(
        [t for t in data if t.get("score_global") is not None],
        key=lambda x: x["score_global"], reverse=True
    )[:10]

    for i, t in enumerate(top10, 1):
        r = row + 1 + i
        fill = _FILL_LGRAY if i % 2 == 0 else None
        tccy = t.get("currency", ccy) or ccy
        vals = [
            i,
            t.get("ticker",""),
            t.get("company",""),
            _sector_short(t.get("sector") or "") or "\u2014",
            _fmt_score(t.get("score_global")),
            _fmt_score(t.get("score_value")),
            _fmt_score(t.get("score_growth")),
            _fmt_score(t.get("score_quality")),
            _fmt_score(t.get("score_momentum")),
            _fmt_price(t.get("price"), tccy),
            _fmt_mds(t.get("market_cap"), tccy),
            _fmt_mult(t.get("ev_ebitda")),
            _fmt_mult(t.get("pe")),
            _fmt_pct(t.get("ebitda_margin"), sign=False),
            _fmt_pct(t.get("revenue_growth")),
            _fmt_pct(t.get("momentum_52w")),
            _fmt_z(t.get("altman_z")),
            _na(t.get("next_earnings")),
        ]
        for j, v in enumerate(vals, 1):
            _w(ws, r, j, v, font=_FONT_BODY, fill=fill,
               align=_ALIGN_C if j in (1,2,5,6,7,8,9,10,11,12,13,18) else _ALIGN_L)

    _set_col_widths(ws, [4,8,22,16,11,10,10,10,10,10,11,9,8,12,10,9,8,12,10,10])
    _freeze(ws, 2, 1)
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# SHEET 2 — COMPARABLES
# ---------------------------------------------------------------------------

def _build_comparables(wb: Workbook, data: list[dict], date_str: str):
    ws = wb.create_sheet("COMPARABLES")
    NCOLS = 16
    ccy = _dominant_ccy(data)
    sym = _sym(ccy)

    _title(ws, 1,
           f"FinSight IA  \u2022  Analyse Comparable  \u2022  Style IB",
           NCOLS, date_str)

    # Header colonnes
    hdrs = ["#","Ticker","Soci\u00e9t\u00e9","Secteur",
            f"Cours ({sym})",f"EV ({sym}Mds)",f"Rev. LTM ({sym}Mds)",
            f"EBITDA LTM ({sym}Mds)","EV/EBITDA (x)","EV/Revenue (x)",
            "EBITDA Gr. NTM (%)","EPS LTM","P/E (x)",
            "Marge Brute","Marge EBITDA","Altman Z"]
    for j, h in enumerate(hdrs, 1):
        _w(ws, 3, j, h, font=_FONT_BOLD, fill=_FILL_MGRAY, align=_ALIGN_C,
           border=_BORDER_THIN)

    # Trier par score_global desc
    sorted_data = sorted(data, key=lambda x: x.get("score_global") or 0, reverse=True)

    for i, t in enumerate(sorted_data, 1):
        r = i + 3
        fill = _FILL_LGRAY if i % 2 == 0 else None
        tccy = t.get("currency", ccy) or ccy
        row_vals = [
            i,
            t.get("ticker",""),
            t.get("company",""),
            _sector_short(t.get("sector") or "") or "\u2014",
            _fmt_price(t.get("price"), tccy),
            _fmt_mds(t.get("ev"), tccy),
            _fmt_mds(t.get("revenue_ltm"), tccy),
            _fmt_mds(t.get("ebitda_ltm"), tccy),
            _fmt_mult(t.get("ev_ebitda")),
            _fmt_mult(t.get("ev_revenue")),
            _fmt_pct(t.get("ebitda_ntm_growth")),
            _fmt_price(t.get("eps"), tccy),
            _fmt_mult(t.get("pe")),
            _fmt_pct(t.get("gross_margin"), sign=False),
            _fmt_pct(t.get("ebitda_margin"), sign=False),
            _fmt_z(t.get("altman_z")),
        ]
        for j, v in enumerate(row_vals, 1):
            _w(ws, r, j, v, font=_FONT_BODY, fill=fill,
               align=_ALIGN_C if j in (1,2,9,10,11,12,13,16) else
               _ALIGN_L if j in (3,4) else _ALIGN_R,
               border=_BORDER_THIN)

    # --- Stats ---
    stat_row = len(sorted_data) + 5
    _section(ws, stat_row, "STATISTIQUES \u2022 M\u00e9diane, Moyenne, Min, Max", NCOLS)

    def _stats_row(label: str, key: str, fmt_fn, r: int):
        vals = [t.get(key) for t in sorted_data if t.get(key) is not None]
        _w(ws, r, 1, label, font=_FONT_BOLD, align=_ALIGN_L, fill=_FILL_LGRAY)
        for col_idx, fn in [(9, median), (10, lambda x: sum(x)/len(x)),
                             (9, max), (9, min)]:
            pass  # overridden below
        # EV/EBITDA col 9, P/E col 13
        for col_i, k2 in [(9, "ev_ebitda"), (13, "pe")]:
            v2 = [t.get(k2) for t in sorted_data if t.get(k2) is not None]
            if v2:
                stat_map = {"M\u00e9diane": median, "Moyenne": lambda x: sum(x)/len(x),
                            "Maximum": max, "Minimum": min}
                fn = stat_map.get(label)
                if fn:
                    try:
                        _w(ws, r, col_i, fmt_fn(fn(v2)),
                           font=_FONT_BODY, fill=_FILL_LGRAY, align=_ALIGN_R)
                    except Exception:
                        pass

    for r_off, lbl in enumerate(["M\u00e9diane","Moyenne","Maximum","Minimum"], 1):
        _stats_row(lbl, "ev_ebitda", _fmt_mult, stat_row + r_off)

    # --- Valorisation implicite (dernier ticker tri\u00e9 par score) ---
    val_row = stat_row + 6
    ref = sorted_data[-1] if sorted_data else {}
    ref_name = ref.get("company", "")
    ref_ticker = ref.get("ticker", "")
    ref_ccy = ref.get("currency", ccy) or ccy

    ev_ebitda_vals = [t.get("ev_ebitda") for t in sorted_data if t.get("ev_ebitda")]
    pe_vals        = [t.get("pe")         for t in sorted_data if t.get("pe")]
    med_ev_ebitda  = median(ev_ebitda_vals) if ev_ebitda_vals else None
    med_pe         = median(pe_vals)        if pe_vals else None

    ref_ebitda = ref.get("ebitda_ltm")
    ref_rev    = ref.get("revenue_ltm")
    ref_nd     = ref.get("net_debt_ebitda")
    ref_nd_abs = (ref_nd * ref_ebitda) if (ref_nd and ref_ebitda) else None
    ref_shares_mc = ref.get("market_cap")
    ref_price     = ref.get("price")
    ref_shares    = (ref_shares_mc / ref_price) if (ref_shares_mc and ref_price and ref_price != 0) else None

    _section(ws, val_row,
             f"VALORISATION IMPLICITE  \u2022  {ref_ticker} vs m\u00e9diane comparables", NCOLS)

    def _val_row(r: int, mult_label: str, mult_val: Optional[float],
                 base_label: str, base_val: Optional[float]):
        if mult_val is None or base_val is None:
            return
        ev_impl = mult_val * base_val
        eq_val  = ev_impl - (ref_nd_abs or 0)
        price_impl = (eq_val * 1e9 / ref_shares) if ref_shares else None
        _w(ws, r, 1,  mult_label,                  font=_FONT_BODY, align=_ALIGN_L)
        _w(ws, r, 2,  _fmt_mult(mult_val),          font=_FONT_BOLD, align=_ALIGN_C)
        _w(ws, r, 3,  f"{base_label} ({ref_ticker})",font=_FONT_BODY, align=_ALIGN_L)
        _w(ws, r, 4,  _fmt_mds(base_val, ref_ccy),  font=_FONT_BODY, align=_ALIGN_R)
        _w(ws, r, 5,  "EV implicite",                font=_FONT_BODY, align=_ALIGN_L)
        _w(ws, r, 6,  _fmt_mds(ev_impl, ref_ccy),   font=_FONT_BOLD, align=_ALIGN_R)
        _w(ws, r, 7,  "\u00b1 Dette nette",           font=_FONT_BODY, align=_ALIGN_L)
        _w(ws, r, 8,  _fmt_mds(ref_nd_abs, ref_ccy) if ref_nd_abs else "\u2014",
           font=_FONT_BODY, align=_ALIGN_R)
        _w(ws, r, 9,  "Equity Value",                font=_FONT_BODY, align=_ALIGN_L)
        _w(ws, r, 10, _fmt_mds(eq_val, ref_ccy),    font=_FONT_BOLD, align=_ALIGN_R)
        _w(ws, r, 11, "Prix/action",                 font=_FONT_BODY, align=_ALIGN_L)
        _w(ws, r, 12,
           _fmt_price(price_impl, ref_ccy) if price_impl else "\u2014",
           font=_FONT_BOLD, align=_ALIGN_R)

    _val_row(val_row+1, "EV/EBITDA M\u00e9diane peers",  med_ev_ebitda,
             "EBITDA LTM", ref_ebitda)
    _val_row(val_row+2, "EV/Revenue M\u00e9diane peers", med_ev_ebitda,
             "Revenue LTM", ref_rev)

    _set_col_widths(ws, [4,8,24,16,10,9,10,10,9,9,11,9,8,11,12,9])
    _freeze(ws, 4, 3)
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# SHEET 3 — RATIOS DETAILLES
# ---------------------------------------------------------------------------

def _build_ratios_detailles(wb: Workbook, data: list[dict], date_str: str):
    ws = wb.create_sheet("RATIOS DETAILLES")
    tickers = [t["ticker"] for t in data]
    N = len(tickers)
    NCOLS = N + 2  # categorie + tickers + mediane

    _title(ws, 1, "FinSight IA  \u2022  Ratios Financiers D\u00e9taill\u00e9s", NCOLS, date_str)

    # Header tickers
    _w(ws, 3, 1, "Cat\u00e9gorie / Ratio", font=_FONT_BOLD, fill=_FILL_MGRAY, align=_ALIGN_L)
    for j, t in enumerate(data, 2):
        _w(ws, 3, j, t["ticker"], font=_FONT_BOLD, fill=_FILL_MGRAY, align=_ALIGN_C)
    _w(ws, 3, N+2, "M\u00e9diane", font=_FONT_BOLD, fill=_FILL_GOLD, align=_ALIGN_C)

    # Helper : \u00e9crire une ligne de ratio
    def _ratio_row(r: int, label: str, key: str, fmt_fn,
                   section: bool = False, positive_good: bool = True):
        if section:
            _section(ws, r, label, NCOLS)
            return r

        fill_row = _FILL_LGRAY if r % 2 == 0 else None
        _w(ws, r, 1, f"  {label}", font=_FONT_BODY, fill=fill_row, align=_ALIGN_L)
        vals_raw = []
        for j, t in enumerate(data, 2):
            v = t.get(key)
            txt = fmt_fn(v)
            f = _FONT_BODY
            if v is not None:
                try:
                    fv = float(v)
                    vals_raw.append(fv)
                    if key in ("revenue_growth","ebitda_ntm_growth","roe","roa","momentum_52w"):
                        f = _FONT_POS if fv >= 0 else _FONT_NEG
                except (ValueError, TypeError):
                    pass
            _w(ws, r, j, txt, font=f, fill=fill_row, align=_ALIGN_R)
        # mediane
        if vals_raw:
            try:
                med = median(vals_raw)
                _w(ws, r, N+2, fmt_fn(med), font=_FONT_BOLD, fill=_FILL_GOLD, align=_ALIGN_R)
            except Exception:
                _w(ws, r, N+2, "\u2014", font=_FONT_BODY, fill=_FILL_GOLD, align=_ALIGN_C)
        else:
            _w(ws, r, N+2, "\u2014", font=_FONT_BODY, fill=_FILL_GOLD, align=_ALIGN_C)
        return r

    rows = [
        ("  VALORISATION", None, None, True),
        ("EV/EBITDA",          "ev_ebitda",       _fmt_mult, False),
        ("EV/Revenue",         "ev_revenue",       _fmt_mult, False),
        ("P/E",                "pe",               _fmt_mult, False),
        ("EPS",                "eps",              lambda v: _fmt_price(v), False),
        ("  RENTABILIT\u00c9", None, None, True),
        ("Marge Brute",        "gross_margin",     lambda v: _fmt_pct(v, sign=False), False),
        ("Marge EBITDA",       "ebitda_margin",    lambda v: _fmt_pct(v, sign=False), False),
        ("Marge Nette",        "net_margin",       lambda v: _fmt_pct(v, sign=False), False),
        ("ROE",                "roe",              _fmt_pct, False),
        ("ROA",                "roa",              _fmt_pct, False),
        ("  LIQUIDIT\u00c9 & SOLVABILIT\u00c9", None, None, True),
        ("Current Ratio",      "current_ratio",    lambda v: _fmt_z(v), False),
        ("Net Debt/EBITDA",    "net_debt_ebitda",  _fmt_mult, False),
        ("Interest Coverage",  "interest_coverage",_fmt_cov, False),
        ("  CROISSANCE",       None, None, True),
        ("Croissance Rev. YoY","revenue_growth",   _fmt_pct, False),
        ("Croissance EBITDA NTM","ebitda_ntm_growth",_fmt_pct, False),
        ("  QUALIT\u00c9",     None, None, True),
        ("Altman Z-Score",     "altman_z",         _fmt_z, False),
        ("Beneish M-Score",    "beneish_m",        _fmt_z, False),
        ("Momentum 52W (%)",   "momentum_52w",     _fmt_pct, False),
        ("Score Global",       "score_global",     _fmt_score, False),
    ]

    r = 4
    for item in rows:
        label, key, fmt_fn, is_section = item
        if is_section:
            _section(ws, r, label, NCOLS)
        else:
            _ratio_row(r, label, key, fmt_fn)
        r += 1

    # Largeurs : col1 large, tickers etroits
    col_widths = [22] + [9] * N + [9]
    _set_col_widths(ws, col_widths)
    _freeze(ws, 4, 2)
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# SHEET 4 — PAR SECTEUR
# ---------------------------------------------------------------------------

def _build_par_secteur(wb: Workbook, data: list[dict], date_str: str):
    ws = wb.create_sheet("PAR SECTEUR")
    NCOLS = 16

    _title(ws, 1, "FinSight IA  \u2022  Vue Sectorielle & Composition", NCOLS, date_str)
    _section(ws, 3,
             "ANALYSE PAR SECTEUR  \u2022  Score, Ratios cl\u00e9s, Signal", NCOLS)

    hdrs = ["Secteur","Nb Soc.","Poids Mkt Cap","Score Moyen","Top Soci\u00e9t\u00e9",
            "EV/EBITDA M\u00e9d.","Marge EBITDA M\u00e9d.","Croissance M\u00e9d.",
            "Altman Z M\u00e9d.","Signal"]
    for j, h in enumerate(hdrs, 1):
        _w(ws, 4, j, h, font=_FONT_BOLD, fill=_FILL_MGRAY, align=_ALIGN_C)

    # Grouper par secteur
    sectors: dict[str, list[dict]] = defaultdict(list)
    for t in data:
        sec = _sector_short(t.get("sector") or "") or "Autres"
        sectors[sec].append(t)

    total_mc = sum(
        t.get("market_cap") or 0 for t in data
    )

    def _med(lst, key):
        vals = [t.get(key) for t in lst if t.get(key) is not None]
        try:
            return median(vals) if vals else None
        except Exception:
            return None

    r = 5
    for sec, tlist in sorted(sectors.items(), key=lambda x: -sum((t.get("market_cap") or 0) for t in x[1])):
        sec_mc = sum(t.get("market_cap") or 0 for t in tlist)
        poids  = (sec_mc / total_mc * 100) if total_mc else None
        avg_sc = _med(tlist, "score_global")
        top    = max(tlist, key=lambda x: x.get("score_global") or 0)
        med_ev = _med(tlist, "ev_ebitda")
        med_mg = _med(tlist, "ebitda_margin")
        med_gr = _med(tlist, "revenue_growth")
        med_z  = _med(tlist, "altman_z")
        sig    = _signal(avg_sc)

        fill = _FILL_LGRAY if r % 2 == 0 else None
        vals = [
            sec,
            len(tlist),
            _fmt_pct(poids, sign=False),
            _fmt_score(avg_sc),
            top.get("company",""),
            _fmt_mult(med_ev),
            _fmt_pct(med_mg, sign=False),
            _fmt_pct(med_gr),
            _fmt_z(med_z),
            sig,
        ]
        for j, v in enumerate(vals, 1):
            _w(ws, r, j, v, font=_FONT_BODY, fill=fill,
               align=_ALIGN_L if j in (1,5,10) else _ALIGN_C)
        r += 1

    # --- Composition ---
    r += 1
    _section(ws, r, "COMPOSITION SECTORIELLE  \u2022  Donn\u00e9es pour graphique", NCOLS)
    hdrs2 = ["Secteur","Nb Soci\u00e9t\u00e9s","Poids Mkt Cap (%)",
             "Mkt Cap Total (Mds)","Score Moyen","Nb Soc. score>70",
             "Nb Soc. score<50","Tendance"]
    for j, h in enumerate(hdrs2, 1):
        _w(ws, r+1, j, h, font=_FONT_BOLD, fill=_FILL_MGRAY, align=_ALIGN_C)

    total_row = r + 2
    ccy = _dominant_ccy(data)
    for sec, tlist in sorted(sectors.items(), key=lambda x: -sum((t.get("market_cap") or 0) for t in x[1])):
        sec_mc  = sum(t.get("market_cap") or 0 for t in tlist)
        poids   = (sec_mc / total_mc * 100) if total_mc else 0
        avg_sc  = _med(tlist, "score_global")
        nb_buy  = sum(1 for t in tlist if (t.get("score_global") or 0) >= 70)
        nb_sell = sum(1 for t in tlist if (t.get("score_global") or 0) < 50)
        tend    = "\u2191 Positif" if (avg_sc or 0) >= 60 else ("\u2193 N\u00e9gatif" if (avg_sc or 0) < 45 else "\u2192 Neutre")

        fill = _FILL_LGRAY if total_row % 2 == 0 else None
        for j, v in enumerate([
            sec, len(tlist), round(poids,1), round(sec_mc,1),
            _fmt_score(avg_sc), nb_buy, nb_sell, tend
        ], 1):
            _w(ws, total_row, j, v, font=_FONT_BODY, fill=fill,
               align=_ALIGN_L if j in (1,8) else _ALIGN_C)
        total_row += 1

    # Total
    _w(ws, total_row, 1, "TOTAL", font=_FONT_BOLD, align=_ALIGN_L)
    _w(ws, total_row, 2, len(data), font=_FONT_BOLD, align=_ALIGN_C)
    _w(ws, total_row, 3, "100.0%", font=_FONT_BOLD, align=_ALIGN_C)
    _w(ws, total_row, 4, round(total_mc, 1), font=_FONT_BOLD, align=_ALIGN_C)

    _set_col_widths(ws, [20,8,12,14,24,10,11,12,10,14,10,10,10,10,10,10])
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# SHEET 5 — DONNEES BRUTES
# ---------------------------------------------------------------------------

def _build_donnees_brutes(wb: Workbook, data: list[dict], date_str: str):
    ws = wb.create_sheet("DONNEES BRUTES")
    ccy = _dominant_ccy(data)

    HEADERS = [
        "Ticker","Soci\u00e9t\u00e9","Secteur","Pays",
        f"Cours ({_sym(ccy)})","Mkt Cap","EV","Rev.LTM","EBITDA LTM",
        "EV/EBITDA","EV/Rev","P/E","EPS",
        "Mg.Brute","Mg.EBITDA","Mg.Nette","Cro.Rev",
        "ROE","ROA","Current R.","ND/EBITDA","Int.Cov",
        "Altman Z","Beneish M","Mom.52W",
        "Score Val","Score Gr","Score Qual","Score Mom","Score Global",
        "Next Earn","EBITDA NTM Gr","WACC","TGR",
    ]

    _w(ws, 1, 1,
       f"DONN\u00c9ES BRUTES  \u2022  Source de v\u00e9rit\u00e9  \u2022  {date_str}",
       font=_FONT_TITLE, fill=_FILL_NAVY, align=_ALIGN_L)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(HEADERS))

    for j, h in enumerate(HEADERS, 1):
        _w(ws, 2, j, h, font=_FONT_BOLD, fill=_FILL_MGRAY, align=_ALIGN_C,
           border=_BORDER_THIN)

    for i, t in enumerate(data, 1):
        r = i + 2
        fill = _FILL_LGRAY if i % 2 == 0 else None
        tccy = t.get("currency", ccy) or ccy

        row_vals = [
            t.get("ticker",""),
            t.get("company",""),
            _sector_short(t.get("sector") or "") or "\u2014",
            t.get("country",""),
            _fmt_price(t.get("price"), tccy),
            _fmt_mds(t.get("market_cap"), tccy),
            _fmt_mds(t.get("ev"), tccy),
            _fmt_mds(t.get("revenue_ltm"), tccy),
            _fmt_mds(t.get("ebitda_ltm"), tccy),
            _fmt_mult(t.get("ev_ebitda")),
            _fmt_mult(t.get("ev_revenue")),
            _fmt_mult(t.get("pe")),
            _fmt_price(t.get("eps"), tccy),
            _fmt_pct(t.get("gross_margin"),   sign=False),
            _fmt_pct(t.get("ebitda_margin"),  sign=False),
            _fmt_pct(t.get("net_margin"),     sign=False),
            _fmt_pct(t.get("revenue_growth")),
            _fmt_pct(t.get("roe")),
            _fmt_pct(t.get("roa")),
            _fmt_z(t.get("current_ratio")),
            _fmt_mult(t.get("net_debt_ebitda")),
            _fmt_cov(t.get("interest_coverage")),
            _fmt_z(t.get("altman_z")),
            _fmt_z(t.get("beneish_m")),
            _fmt_pct(t.get("momentum_52w")),
            t.get("score_value"),
            t.get("score_growth"),
            t.get("score_quality"),
            t.get("score_momentum"),
            t.get("score_global"),
            _na(t.get("next_earnings")),
            _fmt_pct(t.get("ebitda_ntm_growth")),
            _fmt_pct(t.get("wacc"), sign=False),
            _fmt_pct(t.get("tgr"), sign=False),
        ]
        for j, v in enumerate(row_vals, 1):
            _w(ws, r, j, v, font=_FONT_BODY, fill=fill,
               align=_ALIGN_L if j in (2,3,4) else _ALIGN_C,
               border=_BORDER_THIN)

    col_w = [8,22,18,6,9,10,10,10,10,9,8,8,8,9,10,9,9,8,8,9,10,8,8,9,9,8,8,9,8,10,10,11,7,6]
    _set_col_widths(ws, col_w)
    _freeze(ws, 3, 2)
    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# Classe publique
# ---------------------------------------------------------------------------

class ScreeningWriter:
    """
    Genere un fichier Excel de screening style IB.

    Usage :
        path = ScreeningWriter.generate(tickers_data, "CAC40", "outputs/generated/screening_cac40.xlsx")

    tickers_data : liste de dicts avec les champs definis dans le brief.
    """

    @staticmethod
    def generate(
        tickers_data: list[dict],
        universe_name: str,
        output_path: str,
    ) -> str:
        if not tickers_data:
            raise ValueError("tickers_data est vide")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        date_str = date.today().strftime("%d/%m/%Y")

        wb = Workbook()
        wb.remove(wb.active)  # supprimer feuille par defaut

        _build_dashboard(wb, tickers_data, universe_name, date_str)
        _build_comparables(wb, tickers_data, date_str)
        _build_ratios_detailles(wb, tickers_data, date_str)
        _build_par_secteur(wb, tickers_data, date_str)
        _build_donnees_brutes(wb, tickers_data, date_str)

        wb.save(str(out))
        log.info(f"[ScreeningWriter] {out.name} genere ({len(tickers_data)} tickers, 5 feuilles)")
        return str(out)
