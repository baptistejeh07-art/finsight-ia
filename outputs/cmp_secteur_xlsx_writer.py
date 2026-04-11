"""
cmp_secteur_xlsx_writer.py — FinSight IA
Writer XLSX comparatif sectoriel (secteur A vs secteur B).

Complement aux writers existants :
  - cmp_secteur_pdf_writer.py (rapport A4)
  - cmp_secteur_pptx_writer.py (pitchbook)

Usage :
    from outputs.cmp_secteur_xlsx_writer import generate_cmp_secteur_xlsx
    xlsx_bytes = generate_cmp_secteur_xlsx(
        tickers_a, sector_a, universe_a,
        tickers_b, sector_b, universe_b,
    )
"""
from __future__ import annotations

import io
import logging
from datetime import date
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        fv = float(v)
        if fv != fv:  # NaN check
            return None
        return fv
    except Exception:
        return None


def _median(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    vals.sort()
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _mean(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _pct_to_100(v):
    """Convert fraction (0.15) or already-% (15) to %."""
    fv = _safe_float(v)
    if fv is None:
        return None
    return fv * 100 if abs(fv) <= 2.0 else fv


def _agg_sector(tickers, key):
    """Retourne (Médian, mean, min, max) pour une cle numerique."""
    vals = [_safe_float(t.get(key)) for t in tickers]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None, None, None
    vals_sorted = sorted(vals)
    n = len(vals_sorted)
    med = vals_sorted[n // 2] if n % 2 else (vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) / 2
    mean = sum(vals) / n
    return med, mean, min(vals), max(vals)


# ---------------------------------------------------------------------------
# Génération XLSX
# ---------------------------------------------------------------------------
def generate_cmp_secteur_xlsx(
    tickers_a: list,
    sector_a: str,
    universe_a: str,
    tickers_b: list,
    sector_b: str,
    universe_b: str,
) -> bytes:
    """
    Genere un fichier XLSX comparatif sectoriel en memoire.

    Structure :
      - Feuille 1 "SYNTHÈSE"   : KPIs comparatifs des 2 secteurs
      - Feuille 2 "AGRÉGATS"   : mediane / moyenne / min / max par secteur
      - Feuille 3 "TOP_A"      : top valeurs du secteur A (score, PE, marge...)
      - Feuille 4 "TOP_B"      : top valeurs du secteur B
      - Feuille 5 "DATA_RAW_A" : toutes les donnees brutes du secteur A
      - Feuille 6 "DATA_RAW_B" : toutes les donnees brutes du secteur B
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError as _ie:
        raise RuntimeError(f"openpyxl manquant : {_ie}")

    wb = openpyxl.Workbook()

    # === Styles ===
    NAVY         = "FF1B3A6B"
    NAVY_LIGHT   = "FFEEF3FA"
    GREY_LIGHT   = "FFF5F7FA"
    WHITE        = "FFFFFFFF"
    GREEN        = "FF1A7A4A"
    GREEN_LIGHT  = "FFEAF4EF"
    GOLD         = "FFC9A227"
    GOLD_LIGHT   = "FFFBF3DC"
    GREY_RULE    = "FFD0D5DD"
    BLACK        = "FF1A1A1A"

    font_title     = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    font_sub_title = Font(name="Calibri", size=11, bold=True, color="FF555555", italic=True)
    font_header    = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_body      = Font(name="Calibri", size=10, color="FF1A1A1A")
    font_body_bold = Font(name="Calibri", size=10, bold=True, color="FF1A1A1A")
    font_label     = Font(name="Calibri", size=9, color="FF555555")

    fill_navy   = PatternFill("solid", fgColor=NAVY)
    fill_alt    = PatternFill("solid", fgColor=GREY_LIGHT)
    fill_A      = PatternFill("solid", fgColor=NAVY_LIGHT)
    fill_B      = PatternFill("solid", fgColor=GOLD_LIGHT)

    align_l = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    align_c = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_r = Alignment(horizontal="right",  vertical="center")

    thin = Side(border_style="thin", color=GREY_RULE)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # === Feuille 1 : SYNTHÈSE ===
    ws = wb.active
    ws.title = "SYNTHÈSE"

    # Header
    ws.merge_cells("A1:E1")
    ws["A1"] = f"FinSight IA  -  Comparatif Sectoriel : {sector_a} vs {sector_b}"
    ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FF1B3A6B")
    ws["A1"].alignment = align_c

    ws.merge_cells("A2:E2")
    ws["A2"] = (f"{universe_a}  vs  {universe_b}  |  "
                f"{len(tickers_a)} valeurs vs {len(tickers_b)} valeurs  |  "
                f"{date.today().strftime('%d.%m.%Y')}")
    ws["A2"].font = font_sub_title
    ws["A2"].alignment = align_c

    # Ligne en-tête tableau (row 4)
    headers = ["Indicateur", sector_a, sector_b, "Écart", "Commentaire"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=4, column=i, value=h)
        c.font = font_header
        c.fill = fill_navy
        c.alignment = align_c
        c.border = border

    # Lignes de metriques
    def _row_metric(lbl, val_a, val_b, fmt="num", commentary=""):
        """Ajouté une ligne et retourne le dict pour post-traitement."""
        fa = _safe_float(val_a)
        fb = _safe_float(val_b)
        if fmt == "pct":
            sa = f"{_pct_to_100(val_a):.1f}%" if fa is not None else "—"
            sb = f"{_pct_to_100(val_b):.1f}%" if fb is not None else "—"
            delta = (_pct_to_100(val_a) - _pct_to_100(val_b)) if (fa is not None and fb is not None) else None
            sd = f"{delta:+.1f}pts" if delta is not None else "—"
        elif fmt == "x":
            sa = f"{fa:.1f}x" if fa is not None else "—"
            sb = f"{fb:.1f}x" if fb is not None else "—"
            delta = (fa - fb) if (fa is not None and fb is not None) else None
            sd = f"{delta:+.1f}x" if delta is not None else "—"
        else:
            sa = f"{fa:.0f}" if fa is not None else "—"
            sb = f"{fb:.0f}" if fb is not None else "—"
            delta = (fa - fb) if (fa is not None and fb is not None) else None
            sd = f"{delta:+.0f}" if delta is not None else "—"
        return [lbl, sa, sb, sd, commentary]

    # Agrégats
    score_a_med, _, _, _ = _agg_sector(tickers_a, "score_global")
    score_b_med, _, _, _ = _agg_sector(tickers_b, "score_global")
    mg_a_med, _, _, _    = _agg_sector(tickers_a, "ebitda_margin")
    mg_b_med, _, _, _    = _agg_sector(tickers_b, "ebitda_margin")
    pe_a_med, _, _, _    = _agg_sector(tickers_a, "pe_ratio")
    if pe_a_med is None:
        pe_a_med, _, _, _ = _agg_sector(tickers_a, "pe")
    pe_b_med, _, _, _    = _agg_sector(tickers_b, "pe_ratio")
    if pe_b_med is None:
        pe_b_med, _, _, _ = _agg_sector(tickers_b, "pe")
    ev_a_med, _, _, _    = _agg_sector(tickers_a, "ev_ebitda")
    ev_b_med, _, _, _    = _agg_sector(tickers_b, "ev_ebitda")
    roe_a_med, _, _, _   = _agg_sector(tickers_a, "roe")
    roe_b_med, _, _, _   = _agg_sector(tickers_b, "roe")
    rev_a_med, _, _, _   = _agg_sector(tickers_a, "revenue_growth")
    rev_b_med, _, _, _   = _agg_sector(tickers_b, "revenue_growth")

    rows_data = [
        _row_metric("Nombre de valeurs", len(tickers_a), len(tickers_b), "num",
                    "Taille de l'echantillon"),
        _row_metric("Score FinSight Médian", score_a_med, score_b_med, "num",
                    "Qualité fondamentale agregee (0-100)"),
        _row_metric("Marge EBITDA Médiane", mg_a_med, mg_b_med, "pct",
                    "Profitabilite opérationnelle"),
        _row_metric("P/E Médian", pe_a_med, pe_b_med, "x",
                    "Valorisation relative"),
        _row_metric("EV/EBITDA Médian", ev_a_med, ev_b_med, "x",
                    "Valorisation hors structure financière"),
        _row_metric("ROE Médian", roe_a_med, roe_b_med, "pct",
                    "Rentabilité des fonds propres"),
        _row_metric("Croissance revenus Médiane", rev_a_med, rev_b_med, "pct",
                    "Dynamique commerciale"),
    ]

    for ri, row in enumerate(rows_data, start=5):
        for ci, val in enumerate(row, start=1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.font = font_body_bold if ci == 1 else font_body
            c.alignment = align_l if ci in (1, 5) else align_c
            c.border = border
            if ri % 2 == 0:
                c.fill = fill_alt

    # Largeurs colonnes
    for col, w in zip("ABCDE", [34, 18, 18, 14, 42]):
        ws.column_dimensions[col].width = w

    # === Feuille 2 : AGRÉGATS ===
    ws2 = wb.create_sheet("AGRÉGATS")
    ws2.merge_cells("A1:F1")
    ws2["A1"] = f"Agrégats statistiques par secteur"
    ws2["A1"].font = Font(name="Calibri", size=14, bold=True, color="FF1B3A6B")
    ws2["A1"].alignment = align_c

    ws2.merge_cells("A2:F2")
    ws2["A2"] = f"{sector_a} vs {sector_b}  |  Médiane / Moyenne / Min / Max"
    ws2["A2"].font = font_sub_title
    ws2["A2"].alignment = align_c

    hdr2 = ["Secteur", "Indicateur", "Médiane", "Moyenne", "Min", "Max"]
    for i, h in enumerate(hdr2, start=1):
        c = ws2.cell(row=4, column=i, value=h)
        c.font = font_header
        c.fill = fill_navy
        c.alignment = align_c
        c.border = border

    def _fmt_agg(v, mode):
        if v is None: return "—"
        if mode == "pct":
            return f"{_pct_to_100(v):.1f}%"
        if mode == "x":
            return f"{v:.1f}x"
        return f"{v:.0f}" if abs(v) > 1 else f"{v:.2f}"

    metrics_cfg = [
        ("Score FinSight", "score_global", "num"),
        ("Marge EBITDA", "ebitda_margin", "pct"),
        ("P/E", "pe_ratio", "x"),
        ("EV/EBITDA", "ev_ebitda", "x"),
        ("ROE", "roe", "pct"),
        ("Croissance revenus", "revenue_growth", "pct"),
    ]

    row_idx = 5
    for sector_lbl, tickers, fill_col in [
        (sector_a, tickers_a, fill_A),
        (sector_b, tickers_b, fill_B),
    ]:
        for lbl, key, mode in metrics_cfg:
            med, mean, mn, mx = _agg_sector(tickers, key)
            # fallback pe_ratio -> pe
            if med is None and key == "pe_ratio":
                med, mean, mn, mx = _agg_sector(tickers, "pe")
            vals = [sector_lbl, lbl, _fmt_agg(med, mode), _fmt_agg(mean, mode),
                    _fmt_agg(mn, mode), _fmt_agg(mx, mode)]
            for ci, v in enumerate(vals, start=1):
                c = ws2.cell(row=row_idx, column=ci, value=v)
                c.font = font_body_bold if ci == 1 else font_body
                c.alignment = align_l if ci in (1, 2) else align_c
                c.border = border
                if ci == 1:
                    c.fill = fill_col
            row_idx += 1
        row_idx += 1  # ligne vide entre les 2 secteurs

    for col, w in zip("ABCDEF", [22, 26, 14, 14, 14, 14]):
        ws2.column_dimensions[col].width = w

    # === Feuille 3 et 4 : TOP valeurs par secteur ===
    for idx_sheet, (sector_lbl, tickers) in enumerate(
        [(sector_a, tickers_a), (sector_b, tickers_b)], start=1
    ):
        ws_top = wb.create_sheet(f"TOP_{'A' if idx_sheet == 1 else 'B'}")
        ws_top.merge_cells("A1:G1")
        ws_top["A1"] = f"Top valeurs — {sector_lbl}"
        ws_top["A1"].font = Font(name="Calibri", size=14, bold=True, color="FF1B3A6B")
        ws_top["A1"].alignment = align_c

        hdr = ["Ticker", "Société", "Score", "P/E", "EV/EBITDA", "Mg EBITDA", "Reco"]
        for i, h in enumerate(hdr, start=1):
            c = ws_top.cell(row=3, column=i, value=h)
            c.font = font_header
            c.fill = fill_navy
            c.alignment = align_c
            c.border = border

        # Tri par score decroissant
        sorted_tks = sorted(
            tickers, key=lambda t: _safe_float(t.get("score_global")) or 0, reverse=True
        )

        for ri, tk in enumerate(sorted_tks[:20], start=4):
            pe_val = _safe_float(tk.get("pe_ratio")) or _safe_float(tk.get("pe"))
            row_vals = [
                tk.get("ticker", ""),
                (tk.get("company") or "")[:40],
                f"{_safe_float(tk.get('score_global')) or 0:.0f}"
                    if _safe_float(tk.get("score_global")) is not None else "—",
                f"{pe_val:.1f}x" if pe_val is not None else "—",
                f"{_safe_float(tk.get('ev_ebitda')):.1f}x"
                    if _safe_float(tk.get("ev_ebitda")) is not None else "—",
                f"{_pct_to_100(tk.get('ebitda_margin')):.1f}%"
                    if _pct_to_100(tk.get("ebitda_margin")) is not None else "—",
                tk.get("recommendation", "—"),
            ]
            for ci, v in enumerate(row_vals, start=1):
                c = ws_top.cell(row=ri, column=ci, value=v)
                c.font = font_body_bold if ci == 1 else font_body
                c.alignment = align_l if ci in (1, 2) else align_c
                c.border = border
                if ri % 2 == 0:
                    c.fill = fill_alt

        for col, w in zip("ABCDEFG", [10, 32, 10, 10, 12, 12, 12]):
            ws_top.column_dimensions[col].width = w

    # === Feuille 5 et 6 : DATA_RAW (toutes les données brutes) ===
    for idx_sheet, (sector_lbl, tickers) in enumerate(
        [(sector_a, tickers_a), (sector_b, tickers_b)], start=1
    ):
        ws_raw = wb.create_sheet(f"DATA_RAW_{'A' if idx_sheet == 1 else 'B'}")
        ws_raw.merge_cells("A1:H1")
        ws_raw["A1"] = f"Données brutes — {sector_lbl}"
        ws_raw["A1"].font = Font(name="Calibri", size=12, bold=True, color="FF1B3A6B")
        ws_raw["A1"].alignment = align_c

        hdr_raw = ["Ticker", "Société", "Score", "PE", "EV/EBITDA",
                   "Marge EBITDA", "ROE", "Croiss. rev."]
        for i, h in enumerate(hdr_raw, start=1):
            c = ws_raw.cell(row=3, column=i, value=h)
            c.font = font_header
            c.fill = fill_navy
            c.alignment = align_c
            c.border = border

        for ri, tk in enumerate(tickers, start=4):
            pe_val = _safe_float(tk.get("pe_ratio")) or _safe_float(tk.get("pe"))
            row_vals = [
                tk.get("ticker", ""),
                (tk.get("company") or "")[:40],
                _safe_float(tk.get("score_global")),
                pe_val,
                _safe_float(tk.get("ev_ebitda")),
                _pct_to_100(tk.get("ebitda_margin")),
                _pct_to_100(tk.get("roe")),
                _pct_to_100(tk.get("revenue_growth")),
            ]
            for ci, v in enumerate(row_vals, start=1):
                c = ws_raw.cell(row=ri, column=ci, value=v if v is not None else "—")
                c.font = font_body
                c.alignment = align_l if ci in (1, 2) else align_r
                c.border = border
                if ri % 2 == 0:
                    c.fill = fill_alt

        for col, w in zip("ABCDEFGH", [10, 32, 10, 10, 12, 14, 10, 14]):
            ws_raw.column_dimensions[col].width = w

    # Sauvegarde en memoire
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
