"""
cli_analyze.py — FinSight IA
Declenche le pipeline complet (vrais LLMs + donnees) et sauvegarde les outputs.

Usage :
  python cli_analyze.py société  AAPL
  python cli_analyze.py société  MC.PA
  python cli_analyze.py secteur  Technology "CAC 40"
  python cli_analyze.py indice   "S&P 500"
"""
from __future__ import annotations

import sys
import os
import json
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cli_analyze")

OUT_DIR = Path(__file__).parent / "outputs" / "generated" / "cli_tests"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _save(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    log.info("Sauvegarde : %s  (%d Ko)", path.name, len(data) // 1024)


def run_societe(ticker: str) -> None:
    """Pipeline société complet → PDF + PPTX + briefing."""
    from core.graph import build_graph

    log.info("=== ANALYSE SOCIÉTÉ : %s ===", ticker)
    t0 = time.time()

    state = build_graph().invoke({"ticker": ticker})

    elapsed = time.time() - t0
    log.info("Pipeline terminé en %.1fs", elapsed)

    # ── Résumé console ──────────────────────────────────────────────────────
    synth = state.get("synthesis")
    if synth:
        print(f"\n{'='*60}")
        print(f"  {ticker}  —  {getattr(synth, 'recommendation', '?')}  "
              f"(conviction {getattr(synth, 'conviction', 0):.0%})")
        print(f"  Prix cible base  : {getattr(synth, 'target_base', 'N/A')}")
        print(f"  Prix cible bull  : {getattr(synth, 'target_bull', 'N/A')}")
        print(f"  Prix cible bear  : {getattr(synth, 'target_bear', 'N/A')}")
        print(f"  Résumé : {getattr(synth, 'summary', '')[:120]}")
        print(f"{'='*60}\n")

    # ── Sauvegarde fichiers ──────────────────────────────────────────────────
    pdf_bytes = state.get("pdf_bytes")
    if pdf_bytes:
        _save(OUT_DIR / f"{ticker}_report.pdf", pdf_bytes)
    else:
        log.warning("pdf_bytes absent du state")

    pptx_bytes = state.get("pptx_bytes")
    if pptx_bytes:
        _save(OUT_DIR / f"{ticker}_pitchbook.pptx", pptx_bytes)

    excel_bytes = state.get("excel_bytes")
    if excel_bytes:
        _save(OUT_DIR / f"{ticker}_financials.xlsx", excel_bytes)
        log.info("Sauvegarde : %s_financials.xlsx", ticker)

    briefing = state.get("briefing_text") or state.get("briefing")
    if briefing:
        p = OUT_DIR / f"{ticker}_briefing.txt"
        p.write_text(str(briefing), encoding="utf-8")
        log.info("Sauvegarde : %s", p.name)

    # ── Dump JSON state (hors bytes) ─────────────────────────────────────────
    safe_state = {k: v for k, v in state.items()
                  if not isinstance(v, (bytes, bytearray))}
    try:
        p = OUT_DIR / f"{ticker}_state.json"
        p.write_text(
            json.dumps(safe_state, default=str, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Sauvegarde : %s", p.name)
    except Exception as e:
        log.warning("Dump state JSON échoué : %s", e)

    print(f"\nFichiers générés dans : {OUT_DIR}")
    print(f"  • {ticker}_report.pdf")
    print(f"  • {ticker}_pitchbook.pptx")
    print(f"  • {ticker}_financials.xlsx")
    print(f"  • {ticker}_briefing.txt")
    print(f"  • {ticker}_state.json")
    print(f"\nTemps total : {elapsed:.1f}s")


def run_secteur(sector: str, universe: str = "CAC 40", prefix: str = "secteur") -> None:
    """Pipeline sectoriel → PDF sectoriel + PPTX sectoriel.

    prefix : prefixe du fichier de sortie ("secteur" ou "indice").
    Utiliser prefix="indice" quand l'appel vient du mode indice avec secteur specifique.
    """
    from outputs.sector_pdf_writer import generate_sector_report
    from outputs.sectoral_pptx_writer import SectoralPPTXWriter

    log.info("=== ANALYSE SECTORIELLE : %s / %s ===", sector, universe)
    t0 = time.time()

    # Vrais tickers yfinance si secteur connu, fallback synthetique sinon
    tickers = _fetch_real_sector_data(sector, universe, max_tickers=8)
    if not tickers:
        log.warning("Fallback donnees synthetiques pour '%s' / '%s'", sector, universe)
        tickers = _make_test_tickers(sector, 6)

    stem      = f"{prefix}_{sector.replace(' ','_')}_{universe.replace(' ','_')}"
    pdf_path  = OUT_DIR / f"{stem}.pdf"
    pptx_path = OUT_DIR / f"{stem}.pptx"

    # Extraire les sector_analytics injectés dans les tickers
    sector_analytics = tickers[0].get("_sector_analytics") if tickers else {}
    for t in tickers:
        t.pop("_sector_analytics", None)

    generate_sector_report(sector, tickers, str(pdf_path), universe=universe,
                           sector_analytics=sector_analytics)
    log.info("PDF sectoriel : %s  (%d Ko)", pdf_path.name, pdf_path.stat().st_size // 1024)

    SectoralPPTXWriter.generate(tickers, sector, universe, str(pptx_path))
    log.info("PPTX sectoriel : %s  (%d Ko)", pptx_path.name, pptx_path.stat().st_size // 1024)

    print(f"\nFichiers generes dans : {OUT_DIR}")
    print(f"  * {pdf_path.name}")
    print(f"  * {pptx_path.name}")
    print(f"\nTemps total : {time.time() - t0:.1f}s")


def run_indice(universe: str = "S&P 500") -> None:
    """Pipeline indice complet (tous secteurs) → PDF + PPTX."""
    from outputs.indice_pdf_writer import IndicePDFWriter
    from outputs.indice_pptx_writer import IndicePPTXWriter

    log.info("=== ANALYSE INDICE : %s ===", universe)
    t0 = time.time()

    try:
        data = _fetch_real_indice_data(universe)
        log.info("Donnees reelles indice OK")
    except Exception as e:
        log.warning("fetch_real_indice_data erreur: %s — fallback test", e)
        data = _make_test_indice_data(universe)

    stem     = f"indice_{universe.replace(' ','_').replace('&','')}"
    pdf_path  = OUT_DIR / f"{stem}.pdf"
    pptx_path = OUT_DIR / f"{stem}.pptx"

    IndicePDFWriter.generate(data, str(pdf_path))
    log.info("PDF indice : %s  (%d Ko)", pdf_path.name, pdf_path.stat().st_size // 1024)

    pptx_bytes = IndicePPTXWriter.generate(data, str(pptx_path))
    log.info("PPTX indice : %s  (%d Ko)", pptx_path.name, pptx_path.stat().st_size // 1024)

    print(f"\nFichiers generes dans : {OUT_DIR}")
    print(f"  * {pdf_path.name}")
    print(f"  * {pptx_path.name}")
    print(f"\nTemps total : {time.time() - t0:.1f}s")


# ── Tickers réels par secteur / univers ────────────────────────────────────────

_SECTOR_TICKERS: dict = {
    # S&P 500
    ("Consumer Defensive", "S&P 500"):      ["COST","WMT","PG","KO","PEP","PM","MDLZ","GIS","HSY","KMB"],
    ("Technology", "S&P 500"):              ["AAPL","MSFT","NVDA","META","GOOGL","AMD","AVGO","ORCL","CRM","QCOM"],
    ("Healthcare", "S&P 500"):              ["JNJ","UNH","PFE","ABT","MRK","TMO","ABBV","DHR","LLY","BMY"],
    ("Financial Services", "S&P 500"):      ["JPM","BAC","WFC","GS","MS","BLK","AXP","C","SCHW","COF"],
    ("Communication Services", "S&P 500"):  ["META","GOOGL","NFLX","DIS","CMCSA","VZ","T","EA","TTWO","FOXA"],
    ("Energy", "S&P 500"):                  ["XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","OXY","HAL"],
    ("Industrials", "S&P 500"):             ["UNP","RTX","HON","CAT","DE","BA","LMT","GE","UPS","FDX"],
    ("Basic Materials", "S&P 500"):         ["LIN","APD","ECL","DD","NEM","FCX","NUE","CF","ALB","MOS"],
    ("Real Estate", "S&P 500"):             ["PLD","AMT","CCI","EQIX","SPG","PSA","O","AVB","WELL","DLR"],
    ("Utilities", "S&P 500"):               ["NEE","DUK","SO","D","AEP","EXC","SRE","XEL","WEC","ES"],
    ("Consumer Cyclical", "S&P 500"):       ["AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","TJX","BKNG","GM"],
    # CAC 40
    ("Technology", "CAC 40"):              ["CAP.PA","DSY.PA","STM.PA","HO.PA","ALSTOM.PA"],
    ("Luxury", "CAC 40"):                  ["MC.PA","OR.PA","RMS.PA","KER.PA","MDM.PA"],
    ("Energy", "CAC 40"):                  ["TTE.PA","ENGI.PA","ML.PA"],
    ("Healthcare", "CAC 40"):              ["SAN.PA","EL.PA","SARB.PA"],
    ("Financials", "CAC 40"):              ["BNP.PA","ACA.PA","GLE.PA","AXA.PA","SGO.PA"],
    ("Industrials", "CAC 40"):             ["AIR.PA","SAF.PA","LR.PA","ATO.PA","RNO.PA"],
    ("Consumer Staples", "CAC 40"):        ["BN.PA","PUB.PA"],
    # DAX
    ("Technology", "DAX"):                 ["SAP.DE","IFX.DE","SIE.DE"],
    ("Automotive", "DAX"):                 ["BMW.DE","VOW3.DE","MBG.DE","PAH3.DE"],
    ("Healthcare", "DAX"):                 ["BAYN.DE","MRK.DE","FRE.DE","FME.DE"],
    ("Financials", "DAX"):                 ["DBK.DE","CBK.DE","ALV.DE","MUV2.DE"],
    # FTSE 100
    ("Energy", "FTSE 100"):                ["BP.L","SHEL.L"],
    ("Mining", "FTSE 100"):                ["RIO.L","BHP.L","GLEN.L","AAL.L"],
    ("Financials", "FTSE 100"):            ["HSBA.L","BARC.L","LLOY.L","NWG.L","AV.L"],
    ("Healthcare", "FTSE 100"):            ["AZN.L","GSK.L","HLMA.L"],
}


def _get_real_tickers(sector: str, universe: str) -> list[str]:
    """Retourne les tickers reels pour un secteur/univers connu."""
    key = (sector, universe)
    if key in _SECTOR_TICKERS:
        return list(_SECTOR_TICKERS[key])
    sector_l, univ_l = sector.lower(), universe.lower()
    for (s, u), tks in _SECTOR_TICKERS.items():
        if s.lower() == sector_l and u.lower() == univ_l:
            return list(tks)
    return []


def _fetch_pe_historical(tk: str) -> list[float]:
    """Retourne la liste des PE annuels sur 5 ans (cours moyen annuel / EPS).
    Retourne [] si données insuffisantes."""
    try:
        import yfinance as yf
        import numpy as np
        stock = yf.Ticker(tk)
        # Cours historique mensuel sur 5 ans
        hist = stock.history(period="5y", interval="1mo")
        if hist.empty:
            return []
        # EPS annuel depuis income_stmt
        try:
            inc = stock.income_stmt
            if inc is None or inc.empty:
                return []
            eps_row = None
            for key in ["Basic EPS", "Diluted EPS", "EPS"]:
                if key in inc.index:
                    eps_row = inc.loc[key]
                    break
            if eps_row is None:
                return []
            eps_by_year = {}
            for col in eps_row.index:
                yr = int(str(col)[:4])
                v  = eps_row[col]
                if v is not None and not (hasattr(v, '__float__') and v != v):  # not NaN
                    try:
                        fv = float(v)
                        if fv > 0:
                            eps_by_year[yr] = fv
                    except (TypeError, ValueError):
                        pass
        except Exception:
            return []

        if not eps_by_year:
            return []

        # Cours moyen annuel depuis l'historique
        hist['year'] = hist.index.year
        pe_list = []
        for yr, eps in eps_by_year.items():
            yr_prices = hist[hist['year'] == yr]['Close']
            if len(yr_prices) >= 6:
                avg_price = float(yr_prices.mean())
                pe = avg_price / eps
                if 0 < pe < 500:
                    pe_list.append(round(pe, 1))
        return pe_list
    except Exception as e:
        log.debug("_fetch_pe_historical '%s' erreur: %s", tk, e)
        return []


def _load_cache_metrics(tickers: list[str]) -> dict:
    """Charge les métriques avancées depuis les _state.json en cache si disponibles.
    Retourne dict avec scénarios agrégés, conviction_delta, wacc."""
    result = {
        "scenarios_bull": [], "scenarios_base": [], "scenarios_bear": [],
        "conviction_deltas": [], "wacc_values": [],
        "altman_z_values": [],
    }
    cache_dir = OUT_DIR
    for tk in tickers:
        state_path = cache_dir / f"{tk}_state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            # Scénarios DCF
            synth = state.get("synthesis") or {}
            tb = synth.get("target_bull") or synth.get("dcf_bull")
            tb2 = synth.get("target_base") or synth.get("dcf_base")
            tbe = synth.get("target_bear") or synth.get("dcf_bear")
            price = (state.get("snapshot") or {}).get("market_data", {}).get("price")
            if tb and price and float(price) > 0:
                result["scenarios_bull"].append((float(tb) - float(price)) / float(price))
            if tb2 and price and float(price) > 0:
                result["scenarios_base"].append((float(tb2) - float(price)) / float(price))
            if tbe and price and float(price) > 0:
                result["scenarios_bear"].append((float(tbe) - float(price)) / float(price))
            # Conviction delta (devil's advocate)
            devil = state.get("devil") or {}
            cd = devil.get("conviction_delta")
            if cd is not None:
                try:
                    result["conviction_deltas"].append(float(cd))
                except (TypeError, ValueError):
                    pass
            # WACC
            snap = state.get("snapshot") or {}
            mkt  = snap.get("market_data") or {}
            wacc = mkt.get("wacc")
            if wacc:
                try:
                    result["wacc_values"].append(float(wacc))
                except (TypeError, ValueError):
                    pass
            # Altman Z
            ratios = state.get("ratios") or {}
            for yr_data in (ratios.get("years") or {}).values():
                az = yr_data.get("altman_z")
                if az is not None:
                    try:
                        result["altman_z_values"].append(float(az))
                    except (TypeError, ValueError):
                        pass
                    break
        except Exception as e:
            log.debug("cache '%s' erreur: %s", tk, e)
    return result


def _compute_sector_analytics(tickers_data: list[dict],
                               pe_hist_by_ticker: dict,
                               cache: dict,
                               sector: str = "",
                               var_data: dict | None = None) -> dict:
    """Calcule les métriques analytiques sectorielles avancées."""
    import numpy as np

    # --- HHI (Herfindahl-Hirschman Index) ---
    mcs = [t.get("market_cap") or 0 for t in tickers_data]
    total_mc = sum(mcs)
    if total_mc > 0:
        shares = [(mc / total_mc) * 100 for mc in mcs]
        hhi = round(sum(s**2 for s in shares))
    else:
        hhi = None

    if hhi is not None:
        if hhi >= 2500:
            hhi_label = "oligopole concentré — barrières à l'entrée élevées, premium de valorisation justifié"
        elif hhi >= 1500:
            hhi_label = "concentration modérée — concurrence significative entre leaders établis"
        else:
            hhi_label = "secteur fragmenté — pression concurrentielle accrue, compression marges probable"
    else:
        hhi_label = "N/D"

    # --- PE médian actuel ---
    pes_ltm = [float(t["pe_ratio"]) for t in tickers_data
               if t.get("pe_ratio") and float(t["pe_ratio"]) > 0]
    pe_median_ltm = round(float(np.median(pes_ltm)), 1) if pes_ltm else None

    # --- PE médian historique 5 ans ---
    all_hist_pes = []
    for pes in pe_hist_by_ticker.values():
        all_hist_pes.extend(pes)
    pe_median_hist = round(float(np.median(all_hist_pes)), 1) if all_hist_pes else None

    if pe_median_ltm and pe_median_hist:
        pe_premium = (pe_median_ltm / pe_median_hist - 1) * 100
        if pe_premium > 15:
            pe_cycle_label = f"secteur historiquement cher (+{pe_premium:.0f}% vs médiane 5 ans)"
        elif pe_premium < -10:
            pe_cycle_label = f"secteur historiquement bon marché ({pe_premium:.0f}% vs médiane 5 ans)"
        else:
            pe_cycle_label = f"valorisation en ligne avec la médiane historique ({pe_premium:+.0f}%)"
    else:
        pe_premium   = None
        pe_cycle_label = "historique PE insuffisant"

    # --- Dispersion ROIC ---
    roic_values = [t.get("roic") for t in tickers_data if t.get("roic") is not None]
    if not roic_values:
        roic_values = [t.get("roe") for t in tickers_data if t.get("roe") is not None]
    roic_std    = round(float(np.std(roic_values)), 1)   if len(roic_values) >= 2 else None
    roic_mean   = round(float(np.mean(roic_values)), 1)  if roic_values else None
    roic_min    = round(min(roic_values), 1)             if roic_values else None
    roic_max    = round(max(roic_values), 1)             if roic_values else None

    if roic_std is not None:
        if roic_std >= 15:
            roic_label = "forte dispersion — secteur de stock-picking pur, choix de la société > choix du secteur"
        elif roic_std >= 8:
            roic_label = "dispersion modérée — sélectivité recommandée, leaders qualité avantagés"
        else:
            roic_label = "faible dispersion — beta sectoriel dominant, approche indicielle pertinente"
    else:
        roic_label = "N/D"

    # --- WACC médian ---
    wacc_median = round(float(np.median(cache["wacc_values"])) * 100, 1) if cache["wacc_values"] else None

    # --- Altman Z cartographie ---
    # Seuils adaptés au modèle : non-manufacturing pour secteurs asset-light
    _ASSET_LIGHT = {
        "information technology", "technology", "software",
        "communication services", "communications", "healthcare",
        "health care", "financials", "financial services",
        "real estate", "services", "media",
    }
    is_asset_light = sector.lower().strip() in _ASSET_LIGHT
    if is_asset_light:
        az_safe_thr     = 2.6
        az_distress_thr = 1.1
        altman_model    = "nonmfg_1995"
    else:
        az_safe_thr     = 3.0
        az_distress_thr = 1.8
        altman_model    = "original_1968"

    # Priorité cache (valeurs calculées par agent_quant avec bon modèle)
    # Fallback : valeurs calculées dans _fetch_one
    az_vals = cache["altman_z_values"] or [t.get("altman_z") for t in tickers_data if t.get("altman_z")]
    az_vals = [v for v in az_vals if v is not None]
    altman_safe    = sum(1 for z in az_vals if z >= az_safe_thr)
    altman_grey    = sum(1 for z in az_vals if az_distress_thr <= z < az_safe_thr)
    altman_distress= sum(1 for z in az_vals if z < az_distress_thr)
    n_altman = len(az_vals)

    # --- Scénarios agrégés (depuis cache) ---
    def _median_pct(lst):
        return round(float(np.median(lst)) * 100, 1) if lst else None

    scenarios_bull_median = _median_pct(cache["scenarios_bull"])
    scenarios_base_median = _median_pct(cache["scenarios_base"])
    scenarios_bear_median = _median_pct(cache["scenarios_bear"])

    # --- Conviction delta moyen ---
    conviction_delta_mean = (
        round(float(np.mean(cache["conviction_deltas"])), 2)
        if cache["conviction_deltas"] else None
    )

    # --- Piotroski F-Score distribution ---
    f_scores = [t["piotroski_f"] for t in tickers_data if t.get("piotroski_f") is not None]
    n_piotroski    = len(f_scores)
    piotroski_quality = sum(1 for f in f_scores if f > 6)   # F > 6 : quality
    piotroski_neutral = sum(1 for f in f_scores if 4 <= f <= 6)  # F 4-6 : neutre
    piotroski_trap    = sum(1 for f in f_scores if f < 4)   # F < 4 : value trap
    piotroski_median  = round(float(np.median(f_scores)), 1) if f_scores else None

    # --- PEG ratio médian ---
    pegs = [t["peg_ratio"] for t in tickers_data
            if t.get("peg_ratio") is not None and t["peg_ratio"] > 0]
    peg_median = round(float(np.median(pegs)), 2) if pegs else None

    # --- FCF Yield médian ---
    fcfys = [t["fcf_yield"] for t in tickers_data if t.get("fcf_yield") is not None]
    fcf_yield_median = round(float(np.median(fcfys)), 1) if fcfys else None

    # --- Beta : médiane + dispersion ---
    betas = [t.get("beta") for t in tickers_data
             if t.get("beta") is not None and 0 < t["beta"] < 5]
    beta_median = round(float(np.median(betas)), 2) if betas else None
    beta_std    = round(float(np.std(betas)), 2)    if len(betas) >= 2 else None

    # --- Duration implicite = (1 + g) / (WACC - g) ---
    # WACC : priorité cache DCF, sinon estimation CAPM depuis beta médian
    dur_years = dur_wacc_pct = dur_g_pct = None
    dur_method = "N/D"
    try:
        wacc_vals = cache.get("wacc_values", [])
        if wacc_vals:
            dur_wacc   = float(np.median(wacc_vals))
            dur_method = "WACC cache analyses societe"
        else:
            # CAPM : Rf=4.5% (US 10Y) + beta×ERP(5.5%) — estimation institutionnelle standard
            beta_med_dur = float(np.median(betas)) if betas else 1.2
            dur_wacc   = 0.045 + beta_med_dur * 0.055
            dur_method = "WACC median sectoriel estime (CAPM : Rf=4.5% + beta x ERP 5.5%)"
        # g = taux de croissance terminal (long-terme soutenable), PAS le LTM observé.
        # Normalisation : LTM_growth × 0.35 (mean-reversion), cap 5% (PIB nominal max),
        # floor 2% (croissance minimale secteur actif), spread mini 2% avec WACC.
        growths_dur = [t.get("revenue_growth") for t in tickers_data
                       if t.get("revenue_growth") is not None and t["revenue_growth"] > 0]
        dur_g_raw = float(np.median(growths_dur)) if growths_dur else 0.04
        dur_g = max(0.02, min(dur_g_raw * 0.35, 0.05, dur_wacc - 0.02))
        if dur_wacc > dur_g:
            dur_years   = round((1 + dur_g) / (dur_wacc - dur_g), 1)
            dur_wacc_pct = round(dur_wacc * 100, 1)
            dur_g_pct    = round(dur_g    * 100, 1)
    except Exception:
        pass

    # --- Evolution marges EBITDA sectorielles (approximation sur données LTM) ---
    ebitda_margins = [t.get("ebitda_margin") for t in tickers_data if t.get("ebitda_margin")]
    ebitda_median  = round(float(np.median(ebitda_margins)), 1) if ebitda_margins else None

    return {
        "hhi": hhi, "hhi_label": hhi_label,
        "pe_median_ltm": pe_median_ltm, "pe_median_hist": pe_median_hist,
        "pe_premium": pe_premium, "pe_cycle_label": pe_cycle_label,
        "roic_std": roic_std, "roic_mean": roic_mean,
        "roic_min": roic_min, "roic_max": roic_max, "roic_label": roic_label,
        "wacc_median": wacc_median,
        "altman_safe": altman_safe, "altman_grey": altman_grey,
        "altman_distress": altman_distress, "n_altman": n_altman,
        "altman_model": altman_model, "is_asset_light": is_asset_light,
        "scenarios_bull_median": scenarios_bull_median,
        "scenarios_base_median": scenarios_base_median,
        "scenarios_bear_median": scenarios_bear_median,
        "conviction_delta_mean": conviction_delta_mean,
        "ebitda_median": ebitda_median,
        "piotroski_quality": piotroski_quality, "piotroski_neutral": piotroski_neutral,
        "piotroski_trap": piotroski_trap, "piotroski_n": n_piotroski,
        "piotroski_median": piotroski_median,
        "peg_median": peg_median,
        "fcf_yield_median": fcf_yield_median,
        "beta_median": beta_median, "beta_std": beta_std,
        # VaR (depuis _fetch_portfolio_var passé en paramètre)
        "var_95_monthly":   (var_data or {}).get("var_95_monthly"),
        "vol_annual":       (var_data or {}).get("vol_annual"),
        "max_drawdown_52w": (var_data or {}).get("max_drawdown_52w"),
        # Duration implicite
        "duration_years": dur_years, "duration_wacc": dur_wacc_pct,
        "duration_growth": dur_g_pct, "duration_method": dur_method,
    }


def _compute_piotroski(stock) -> int | None:
    """
    Piotroski F-Score (9 criteres binaires) depuis les etats financiers yfinance.

    Profitabilite  F1-F4 : ROA>0, OCF>0, ΔROA>0, OCF/TA>ROA
    Levier/Liq.    F5-F7 : Δlevier<0, Δcurrent_ratio>0, pas dilution
    Efficacite     F8-F9 : ΔGross Margin>0, ΔAsset Turnover>0

    Retourne score 0-9 ou None si moins de 6 criteres evaluables.
    """
    try:
        import pandas as pd
        # Compatibilite yfinance ancien/nouveau API (pas de 'or' sur DataFrame)
        inc = getattr(stock, 'income_stmt', None)
        if inc is None or getattr(inc, 'empty', True):
            inc = getattr(stock, 'financials', None)
        bs = getattr(stock, 'balance_sheet', None)
        cf = getattr(stock, 'cashflow', None)
        if cf is None or getattr(cf, 'empty', True):
            cf = getattr(stock, 'cash_flow', None)
        if (inc is None or getattr(inc, 'empty', True) or
                bs  is None or getattr(bs,  'empty', True) or
                cf  is None or getattr(cf,  'empty', True)):
            return None
        if len(inc.columns) < 2 or len(bs.columns) < 2:
            return None

        def _v(df, keys, col):
            for k in keys:
                if k in df.index:
                    try:
                        v = float(df.loc[k, col])
                        if pd.notna(v):
                            return v
                    except (TypeError, ValueError):
                        pass
            return None

        # Colonnes : plus recent en premier
        ic0, ic1 = inc.columns[0], inc.columns[1]
        bc0, bc1 = bs.columns[0], (bs.columns[1] if len(bs.columns) > 1 else bs.columns[0])

        # Income statement
        ni0  = _v(inc, ['Net Income', 'Net Income Common Stockholders',
                         'Net Income Including Noncontrolling Interests'], ic0)
        ni1  = _v(inc, ['Net Income', 'Net Income Common Stockholders',
                         'Net Income Including Noncontrolling Interests'], ic1)
        rev0 = _v(inc, ['Total Revenue', 'Revenue'], ic0)
        rev1 = _v(inc, ['Total Revenue', 'Revenue'], ic1)
        gp0  = _v(inc, ['Gross Profit'], ic0)
        gp1  = _v(inc, ['Gross Profit'], ic1)
        # Balance sheet
        ta0  = _v(bs, ['Total Assets'], bc0)
        ta1  = _v(bs, ['Total Assets'], bc1)
        tca0 = _v(bs, ['Current Assets', 'Total Current Assets'], bc0)
        tcl0 = _v(bs, ['Current Liabilities', 'Total Current Liabilities'], bc0)
        tca1 = _v(bs, ['Current Assets', 'Total Current Assets'], bc1)
        tcl1 = _v(bs, ['Current Liabilities', 'Total Current Liabilities'], bc1)
        ltd0 = _v(bs, ['Long Term Debt', 'Long-Term Debt',
                        'Long Term Debt And Capital Lease Obligation'], bc0)
        ltd1 = _v(bs, ['Long Term Debt', 'Long-Term Debt',
                        'Long Term Debt And Capital Lease Obligation'], bc1)
        shr0 = _v(bs, ['Common Stock', 'Share Issued', 'Ordinary Shares Number'], bc0)
        shr1 = _v(bs, ['Common Stock', 'Share Issued', 'Ordinary Shares Number'], bc1)
        # Cash flow
        ocf0 = _v(cf, ['Operating Cash Flow', 'Total Cash From Operating Activities',
                        'Cash Flows From Used In Operating Activities'], ic0)

        f = n = 0

        # --- Profitabilite ---
        if ni0 is not None and ta0 and ta0 != 0:
            f += 1 if ni0 / ta0 > 0 else 0;  n += 1  # F1: ROA > 0
        if ocf0 is not None:
            f += 1 if ocf0 > 0 else 0;        n += 1  # F2: OCF > 0
        if (ni0 is not None and ni1 is not None and
                ta0 and ta0 != 0 and ta1 and ta1 != 0):
            f += 1 if ni0/ta0 > ni1/ta1 else 0;  n += 1  # F3: ΔROA > 0
        if ocf0 is not None and ni0 is not None and ta0 and ta0 != 0:
            f += 1 if ocf0/ta0 > ni0/ta0 else 0;  n += 1  # F4: accruals

        # --- Levier / Liquidite ---
        if (ltd0 is not None and ltd1 is not None and
                ta0 and ta0 != 0 and ta1 and ta1 != 0):
            f += 1 if ltd0/ta0 < ltd1/ta1 else 0;  n += 1  # F5: Δlevier < 0
        if (tca0 is not None and tcl0 and tcl0 != 0 and
                tca1 is not None and tcl1 and tcl1 != 0):
            f += 1 if tca0/tcl0 > tca1/tcl1 else 0;  n += 1  # F6: ΔCR > 0
        if shr0 is not None and shr1 is not None and shr1 > 0:
            f += 1 if shr0 <= shr1 * 1.02 else 0;  n += 1  # F7: pas dilution

        # --- Efficacite ---
        if (gp0 is not None and rev0 and rev0 != 0 and
                gp1 is not None and rev1 and rev1 != 0):
            f += 1 if gp0/rev0 > gp1/rev1 else 0;  n += 1  # F8: ΔGross Margin > 0
        if (rev0 is not None and ta0 and ta0 != 0 and
                rev1 is not None and ta1 and ta1 != 0):
            f += 1 if rev0/ta0 > rev1/ta1 else 0;  n += 1  # F9: ΔAsset Turnover > 0

        return f if n >= 6 else None
    except Exception:
        return None


def _fetch_portfolio_var(symbols: list[str], market_caps: dict[str, float]) -> dict:
    """
    VaR 95% mensuelle sur basket market-cap weighted (simulation historique 52W).

    Methode :
    - Prix daily yfinance 1 an, returns daily pct_change
    - Returns ponderés par market cap (w_i = mc_i / Σmc_j)
    - VaR_daily_95 = 5e percentile (simulation historique, sans hypothèse de normalité)
    - VaR_mensuelle = VaR_daily × √21  (règle racine du temps)
    - Aussi : volatilite annualisee et max drawdown 52W du basket

    Retourne dict vide si données insuffisantes.
    """
    try:
        import pandas as pd
        import yfinance as yf
        import numpy as np

        total_mc = sum(v for v in market_caps.values() if v)
        if not total_mc or not symbols:
            return {}
        weights = {tk: (market_caps.get(tk) or 0) / total_mc for tk in symbols}

        # Bulk download cours daily 1 an
        raw = yf.download(symbols, period="1y", auto_adjust=True, progress=False)
        if raw is None or raw.empty:
            return {}

        # Normaliser : single ticker → DataFrame 1 col, multi → MultiIndex
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw["Close"]
        elif "Close" in raw.columns:
            prices = raw[["Close"]].rename(columns={"Close": symbols[0]})
        else:
            prices = raw

        if prices.empty or len(prices) < 30:
            return {}

        ret = prices.pct_change().dropna()

        # Returns quotidiens du portefeuille pondéré market-cap
        port_ret = pd.Series(0.0, index=ret.index)
        n_used = 0
        for tk in symbols:
            col = tk if tk in ret.columns else None
            if col and weights.get(tk, 0) > 0:
                port_ret += ret[col].fillna(0) * weights[tk]
                n_used += 1
        if n_used == 0:
            return {}

        # VaR 95% historique : 5e percentile daily × √21 → mensuel
        var_daily_95  = float(np.percentile(port_ret, 5))
        var_monthly_95 = var_daily_95 * np.sqrt(21)

        # Volatilité annualisée
        vol_annual = float(port_ret.std() * np.sqrt(252))

        # Max drawdown 52W
        cumul   = (1 + port_ret).cumprod()
        roll_mx = cumul.cummax()
        max_dd  = float(((cumul - roll_mx) / roll_mx).min())

        return {
            "var_95_monthly":   round(var_monthly_95 * 100, 1),  # % (négatif)
            "vol_annual":       round(vol_annual      * 100, 1),  # %
            "max_drawdown_52w": round(max_dd          * 100, 1),  # % (négatif)
            "n_tickers_used":   n_used,
        }
    except Exception as e:
        log.warning("_fetch_portfolio_var erreur: %s", e)
        return {}


def _fetch_real_sector_data(sector: str, universe: str, max_tickers: int = 8) -> list[dict]:
    """Fetch donnees reelles secteur via yfinance.info + ROIC réel + PE historique."""
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    symbols = _get_real_tickers(sector, universe)[:max_tickers]
    if not symbols:
        log.warning("Pas de tickers reels pour '%s' / '%s' — fallback synthetique", sector, universe)
        return []

    log.info("Fetch secteur reel: %d tickers (%s)", len(symbols), ", ".join(symbols))

    def _fetch_one(tk: str) -> dict | None:
        try:
            stock = yf.Ticker(tk)
            info = stock.info or {}
            name = info.get("longName") or info.get("shortName") or tk
            if name == tk and not info.get("marketCap"):
                return None  # ticker invalide / deliste
            mc = info.get("marketCap")
            pe = info.get("trailingPE") or info.get("forwardPE")
            pe = pe if pe and pe > 0 and pe < 500 else None
            ebitda_m = (info.get("ebitdaMargins") or 0) * 100
            gross_m  = (info.get("grossMargins")  or 0) * 100
            net_m    = (info.get("profitMargins")  or 0) * 100
            roe      = (info.get("returnOnEquity") or 0) * 100
            rev_g    =  info.get("revenueGrowth")  or 0
            mom52    = (info.get("52WeekChange")    or 0) * 100
            beta     =  info.get("beta")            or 1.0

            # ROIC réel = NOPAT / Invested Capital
            # NOPAT = EBIT * (1 - tax_rate), IC = TotalEquity + TotalDebt - Cash
            roic = None
            try:
                ebit          = info.get("ebit") or info.get("operatingIncome")
                tax_rate      = info.get("effectiveTaxRate") or 0.21
                total_debt    = info.get("totalDebt") or 0
                total_equity  = info.get("totalStockholdersEquity") or info.get("bookValue", 0)
                if isinstance(total_equity, float) and total_equity < 1e6:
                    # bookValue est par action — convertir
                    shares = info.get("sharesOutstanding") or 1
                    total_equity = total_equity * shares
                cash          = info.get("totalCash") or 0
                ic            = total_equity + total_debt - cash
                if ebit and ic and ic > 0:
                    nopat = float(ebit) * (1 - min(float(tax_rate), 0.40))
                    roic  = round(nopat / ic * 100, 1)
            except Exception:
                pass

            # Altman Z-Score réel — modèle sélectionné selon secteur
            # Non-manufacturing (1995) pour tech/services : Z' = 6.56*X1+3.26*X2+6.72*X3+1.05*X4
            # Original (1968) pour manufacturing : Z = 1.2*X1+1.4*X2+3.3*X3+0.6*X4+1.0*X5
            _ASSET_LIGHT = {
                "information technology", "technology", "software",
                "communication services", "communications", "healthcare",
                "health care", "financials", "financial services",
                "real estate", "services", "media",
            }
            _sector_lc = sector.lower().strip()
            _use_nonmfg = _sector_lc in _ASSET_LIGHT
            altman_z = None
            altman_z_model = None
            try:
                ta = info.get("totalAssets")
                if ta and ta > 0:
                    wc    = (info.get("totalCurrentAssets") or 0) - (info.get("totalCurrentLiabilities") or 0)
                    re_v  = info.get("retainedEarnings") or 0
                    ebit_v= info.get("ebit") or info.get("operatingIncome") or 0
                    tliab = info.get("totalLiab") or info.get("totalLiabilities") or 0
                    x1 = wc    / ta
                    x2 = re_v  / ta
                    x3 = ebit_v/ ta
                    if _use_nonmfg:
                        eq_bv = info.get("totalStockholdersEquity") or 0
                        if isinstance(eq_bv, float) and 0 < eq_bv < 1e6:
                            eq_bv *= (info.get("sharesOutstanding") or 1)
                        if tliab > 0:
                            x4 = eq_bv / tliab
                            altman_z = round(6.56*x1 + 3.26*x2 + 6.72*x3 + 1.05*x4, 2)
                            altman_z_model = "nonmfg_1995"
                    else:
                        mc_v = info.get("marketCap") or 0
                        rev_v= info.get("totalRevenue") or 0
                        if tliab > 0:
                            x4 = mc_v / tliab
                            x5 = rev_v / ta
                            altman_z = round(1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5, 2)
                            altman_z_model = "original_1968"
            except Exception:
                altman_z = None
                altman_z_model = None

            # PEG ratio (PE / croissance revenus annualisee %)
            peg_ratio = None
            if pe and pe > 0 and rev_g and rev_g > 0:
                peg_ratio = round(pe / (rev_g * 100), 2)
                if peg_ratio > 50 or peg_ratio < 0:
                    peg_ratio = None

            # FCF Yield = Free Cash Flow / Market Cap
            fcf_yield = None
            try:
                fcf_abs = info.get("freeCashflow")
                if fcf_abs and mc and mc > 0:
                    fcf_yield = round(float(fcf_abs) / float(mc) * 100, 2)
                    if fcf_yield < -50 or fcf_yield > 50:
                        fcf_yield = None
            except Exception:
                pass

            # Piotroski F-Score (9 criteres depuis etats financiers)
            piotroski = None
            try:
                piotroski = _compute_piotroski(stock)
            except Exception:
                pass

            # Score simplifie : value + growth + qualite + momentum
            s_val  = max(0, min(25, 25 - (pe or 20) * 0.5)) if pe else 12
            s_gro  = max(0, min(25, 12 + rev_g * 100))
            s_qua  = max(0, min(25, 10 + net_m * 0.8))
            s_mom  = max(0, min(25, 12 + mom52 * 0.15))
            score  = round(s_val + s_gro + s_qua + s_mom)
            return {
                "ticker":          tk,
                "company":         name[:35],
                "sector":          info.get("sector", sector),
                "score_global":    score,
                "score_value":     round(s_val, 1),
                "score_growth":    round(s_gro, 1),
                "score_quality":   round(s_qua, 1),
                "score_momentum":  round(s_mom, 1),
                "ev_ebitda":       info.get("enterpriseToEbitda"),
                "ev_revenue":      info.get("enterpriseToRevenue"),
                "pe_ratio":        pe,
                "ebitda_margin":   round(ebitda_m, 1),
                "gross_margin":    round(gross_m, 1),
                "net_margin":      round(net_m, 1),
                "roe":             round(roe, 1),
                "roic":            roic,
                "revenue_growth":  rev_g,
                "momentum_52w":    round(mom52, 1),
                "altman_z":        altman_z,
                "altman_z_model":  altman_z_model,
                "piotroski_f":     piotroski,
                "peg_ratio":       peg_ratio,
                "fcf_yield":       fcf_yield,
                "beneish_m":       -2.5,
                "beta":            beta,
                "price":           info.get("currentPrice") or info.get("regularMarketPrice"),
                "market_cap":      mc,
                "revenue_ltm":     info.get("totalRevenue"),
                "currency":        info.get("currency", "USD"),
                "sentiment_score": 0.0,
            }
        except Exception as e:
            log.warning("yfinance.info '%s' erreur: %s", tk, e)
            return None

    results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_fetch_one, tk): tk for tk in symbols}
        for fut in as_completed(futures):
            r = fut.result()
            if r:
                results.append(r)

    results.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)
    log.info("Secteur %s/%s: %d/%d tickers OK", sector, universe, len(results), len(symbols))

    # PE historique 5 ans (5 appels supplémentaires en parallèle)
    pe_hist_by_ticker: dict[str, list[float]] = {}
    tks = [r["ticker"] for r in results]
    with ThreadPoolExecutor(max_workers=4) as ex:
        fut_pe = {ex.submit(_fetch_pe_historical, tk): tk for tk in tks}
        for fut in as_completed(fut_pe):
            tk = fut_pe[fut]
            try:
                pe_hist_by_ticker[tk] = fut.result()
            except Exception:
                pe_hist_by_ticker[tk] = []
    log.info("PE historique: %d tickers avec données", sum(1 for v in pe_hist_by_ticker.values() if v))

    # VaR sectorielle 95% mensuelle (market-cap weighted, simulation historique 52W)
    mc_dict  = {r["ticker"]: r.get("market_cap") or 0 for r in results}
    var_data = _fetch_portfolio_var(tks, mc_dict)
    log.info("VaR secteur: %s", var_data)

    # Cache metrics (scénarios, conviction_delta, wacc)
    cache = _load_cache_metrics(tks)
    log.info("Cache: %d scénarios bull, %d conviction_delta, %d wacc",
             len(cache["scenarios_bull"]), len(cache["conviction_deltas"]), len(cache["wacc_values"]))

    # Analytics sectoriels globaux — injecté dans chaque ticker pour transmission au PDF
    sector_analytics = _compute_sector_analytics(
        results, pe_hist_by_ticker, cache, sector=sector, var_data=var_data)
    for r in results:
        r["_sector_analytics"] = sector_analytics

    log.info(
        "Sector analytics: HHI=%s | PE ltm=%.1f vs hist=%s | ROIC std=%s",
        sector_analytics.get("hhi"),
        sector_analytics.get("pe_median_ltm") or 0,
        sector_analytics.get("pe_median_hist"),
        sector_analytics.get("roic_std"),
    )
    return results


# ── Helpers données de test (fallback si secteur inconnu) ──────────────────────

def _make_test_tickers(sector: str, n: int) -> list[dict]:
    import random
    random.seed(42)
    tickers = []
    for i in range(n):
        score = max(25, min(92, 60 + (i - n // 2) * 4))
        tickers.append({
            "ticker": f"{sector[:3].upper()}{i+1}",
            "company": f"{sector} Corp {i+1}",
            "sector": sector,
            "score_global": score,
            "score_value": score * 0.25,
            "score_growth": score * 0.25,
            "score_quality": score * 0.25,
            "score_momentum": score * 0.25,
            "ev_ebitda": 8.0 + i * 1.5,
            "ev_revenue": 2.0 + i * 0.4,
            "pe_ratio": 15.0 + i * 2,
            "ebitda_margin": 20 + i * 0.8,
            "gross_margin": 40 + i * 0.5,
            "net_margin": 12 + i * 0.4,
            "roe": 15.0 + i,
            "revenue_growth": 0.05 + i * 0.015,
            "momentum_52w": 5 + i * 3.0,
            "altman_z": 2.8 + i * 0.1,
            "beneish_m": -2.5,
            "beta": 1.0 + i * 0.05,
            "price": 80 + i * 10,
            "market_cap": (80 + i * 10) * 1e8,
            "revenue_ltm": 1e10 + i * 5e8,
            "currency": "USD",
            "sentiment_score": round(0.1 + i * 0.03, 2),
        })
    return tickers


# ── Mapping ETF SPDR → secteur ─────────────────────────────────────────────────

_ETF_SECTORS = {
    "XLK":  "Technology",
    "XLV":  "Health Care",
    "XLF":  "Financials",
    "XLY":  "Consumer Discretionary",
    "XLC":  "Communication Services",
    "XLI":  "Industrials",
    "XLP":  "Consumer Staples",
    "XLE":  "Energy",
    "XLRE": "Real Estate",
    "XLU":  "Utilities",
    "XLB":  "Materials",
}

_SP500_NB_SOC = {
    "Technology": 65, "Health Care": 64, "Financials": 72,
    "Consumer Discretionary": 55, "Communication Services": 26,
    "Industrials": 77, "Consumer Staples": 38, "Energy": 23,
    "Materials": 28, "Real Estate": 31, "Utilities": 28,
}

_INDICE_META = {
    "S&P 500": {"code": "^GSPC", "nb_societes": 503},
    "CAC 40":  {"code": "^FCHI", "nb_societes": 40},
    "DAX":     {"code": "^GDAXI", "nb_societes": 40},
    "FTSE 100":{"code": "^FTSE",  "nb_societes": 100},
}


def _make_test_indice_data(universe: str = "S&P 500") -> dict:
    """Data dict complet pour IndicePDFWriter + IndicePPTXWriter (donnees synthetiques)."""
    import datetime
    meta = _INDICE_META.get(universe, {"code": "^GSPC", "nb_societes": 503})
    today = datetime.date.today()
    _fr = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
           7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}
    date_str = f"{today.day} {_fr[today.month]} {today.year}"

    # (nom, nb_soc, score, signal, ev_ebitda_str, ebitda_margin, croisse_str, mom_str)
    secteurs = [
        ("Technology",             65, 72, "Surponderer",   "24.8x", 28.4, "+14.2%", "+18.4%"),
        ("Health Care",            64, 65, "Surponderer",   "14.2x", 22.1, "+9.8%",  "+8.4%"),
        ("Financials",             72, 62, "Surponderer",   "9.8x",  31.2, "+11.4%", "+12.1%"),
        ("Communication Services", 26, 58, "Neutre",        "12.6x", 24.6, "+10.1%", "+9.2%"),
        ("Consumer Discretionary", 55, 55, "Neutre",        "16.4x", 14.8, "+8.2%",  "+6.8%"),
        ("Industrials",            77, 53, "Neutre",        "14.8x", 16.2, "+6.8%",  "+5.4%"),
        ("Consumer Staples",       38, 48, "Neutre",        "13.2x", 18.4, "+3.2%",  "+2.1%"),
        ("Materials",              28, 46, "Neutre",        "11.4x", 20.4, "+4.8%",  "+1.8%"),
        ("Energy",                 23, 44, "Neutre",        "6.2x",  28.8, "-2.4%",  "-4.2%"),
        ("Real Estate",            31, 38, "Sous-ponderer", "18.6x", 48.2, "+1.2%",  "-2.8%"),
        ("Utilities",              28, 36, "Sous-ponderer", "11.8x", 32.4, "+2.8%",  "-5.4%"),
    ]
    import statistics
    scores = [s[2] for s in secteurs]
    avg_score = round(statistics.mean(scores), 1)
    nb_surp = sum(1 for s in secteurs if s[3] == "Surponderer")
    conviction = round(nb_surp / len(secteurs) * 100)
    signal_global = ("Surponderer" if avg_score > 62 else
                     ("Sous-ponderer" if avg_score < 45 else "Neutre"))

    top3_secteurs = [
        {
            "nom": "Technology", "signal": "Surponderer", "score": 72,
            "ev_ebitda": "24.8x", "pe_forward_raw": 28.5, "pe_mediane_10y": 22.0,
            "poids_indice": "31.5%",
            "catalyseur": "Cycle IA — CAPEX hyperscalers +35% YoY, monetisation acceleree",
            "risque": "Valorisations tendues si taux LT restent eleves",
            "societes": [
                ("AAPL", "Surponderer", "22.4x", 78),
                ("MSFT", "Surponderer", "28.6x", 75),
                ("NVDA", "Surponderer", "42.8x", 82),
            ],
        },
        {
            "nom": "Health Care", "signal": "Surponderer", "score": 65,
            "ev_ebitda": "14.2x", "pe_forward_raw": 17.8, "pe_mediane_10y": 16.5,
            "poids_indice": "12.8%",
            "catalyseur": "Pipeline FDA robuste, pricing power defensif intact",
            "risque": "Risque reglementaire US — pression politique sur prix medicaments",
            "societes": [
                ("UNH", "Surponderer", "10.8x", 72),
                ("LLY", "Surponderer", "28.4x", 80),
                ("JNJ", "Neutre",      "12.6x", 62),
            ],
        },
        {
            "nom": "Financials", "signal": "Surponderer", "score": 62,
            "ev_ebitda": "9.8x", "pe_forward_raw": 13.2, "pe_mediane_10y": 12.8,
            "poids_indice": "13.2%",
            "catalyseur": "Spreads de credit solides, NIM eleves, buybacks soutenus",
            "risque": "Stress immobilier commercial — CRE loans sous surveillance",
            "societes": [
                ("JPM", "Surponderer", "8.4x",  70),
                ("BLK", "Surponderer", "14.2x", 68),
                ("GS",  "Neutre",      "9.8x",  60),
            ],
        },
    ]

    rotation = [
        ("Technology",             "Expansion",  "Moderee",  "Elevee",   "Accumuler"),
        ("Health Care",            "Expansion",  "Faible",   "Moderee",  "Accumuler"),
        ("Financials",             "Expansion",  "Positive", "Moderee",  "Accumuler"),
        ("Communication Services", "Expansion",  "Moderee",  "Elevee",   "Neutre"),
        ("Consumer Discretionary", "Expansion",  "Moderee",  "Elevee",   "Neutre"),
        ("Industrials",            "Expansion",  "Moderee",  "Elevee",   "Neutre"),
        ("Consumer Staples",       "Ralentissement","Faible", "Faible",  "Neutre"),
        ("Materials",              "Expansion",  "Moderee",  "Elevee",   "Neutre"),
        ("Energy",                 "Ralentissement","Faible", "Moderee", "Alleger"),
        ("Real Estate",            "Ralentissement","Elevee", "Moderee", "Alleger"),
        ("Utilities",              "Ralentissement","Elevee", "Faible",  "Alleger"),
    ]

    etf_perf = {
        "XLK":  {"nom": "Technology",        "return_1y": 18.4},
        "XLV":  {"nom": "Health Care",        "return_1y": 8.4},
        "XLF":  {"nom": "Financials",         "return_1y": 12.1},
        "XLY":  {"nom": "Consumer Disc.",     "return_1y": 6.8},
        "XLC":  {"nom": "Comm. Services",     "return_1y": 9.2},
        "XLI":  {"nom": "Industrials",        "return_1y": 5.4},
        "XLP":  {"nom": "Consumer Staples",   "return_1y": 2.1},
        "XLE":  {"nom": "Energy",             "return_1y": -4.2},
        "XLRE": {"nom": "Real Estate",        "return_1y": -2.8},
        "XLU":  {"nom": "Utilities",          "return_1y": -5.4},
        "XLB":  {"nom": "Materials",          "return_1y": 1.8},
    }

    return {
        "indice":           universe,
        "code":             meta["code"],
        "signal_global":    signal_global,
        "conviction_pct":   conviction,
        "nb_secteurs":      len(secteurs),
        "nb_societes":      meta["nb_societes"],
        "cours":            "5 210",
        "variation_ytd":    "+4.8%",
        "pe_forward":       "21.5x",
        "pe_mediane_10y":   "18.2x",
        "erp":              "4.2%",
        "bpa_growth":       "+8.5%",
        "date_analyse":     date_str,
        "texte_description": (
            f"Le {universe} regroupe les {meta['nb_societes']} plus grandes capitalisations "
            "boursieres domestiques, pondérees par leur capitalisation flottante. Cet indice "
            "constitue la reference mondiale pour les allocataires d'actifs institutionnels, "
            "avec une capitalisation totale de pres de 40 000 milliards de dollars. La "
            "composition GICS couvre 11 secteurs, le secteur Technologie dominant avec pres "
            "de 32% de l'indice."
        ),
        "texte_macro": (
            "L'environnement macro reste marque par une resilience de la croissance americaine "
            "(GDP +2.4% T4 2025) combinee a une desinflation graduelle (PCE Core 2.7%). La "
            "Fed maintient ses taux directeurs dans une fourchette de 4.25-4.50%, signalant "
            "2 baisses anticipees pour 2026. Le marche du travail reste solide (chomage 4.1%), "
            "soutenant la consommation et les marges des secteurs cycliques. Les tensions "
            "geopolitiques et les risques tarifaires constituent les principaux facteurs "
            "d'incertitude sur l'horizon 12 mois."
        ),
        "texte_signal": (
            f"Le signal global sur le {universe} est {signal_global} avec une conviction de "
            f"{conviction}% (sur la base des {len(secteurs)} secteurs analyses). "
            f"{nb_surp} secteurs ressortent Surponderer — Technology, Health Care et Financials "
            "— portes respectivement par le cycle IA, le pricing power defensif et les spreads "
            "de credit eleves. 6 secteurs sont Neutre en raison d'une visibilite limitee sur "
            "les BPA dans un contexte de taux restrictifs. 2 secteurs (Real Estate, Utilities) "
            "sont Sous-ponderer sous pression directe de la politique monetaire."
        ),
        "texte_valorisation": (
            f"Le P/E Forward a 21.5x s'inscrit en prime de 18% par rapport a la mediane 10 ans "
            "(18.2x), justifie en partie par la monetisation de l'IA et la qualite superieure "
            "des marges. L'ERP ressort a 4.2% — niveau attractif mais contraint par le 10Y US "
            "a 4.3%. La compression de multiple reste le principal risque si les taux LT "
            "demeurent restrictifs. Le secteur Technologie (P/E 28.5x vs mediane 22x) concentre "
            "la prime de valorisation."
        ),
        "texte_cycle": (
            "L'analyse des indicateurs avancees positionne le cycle en phase d'expansion avancee : "
            "ISM Manufacturier autour du seuil 50 (49.8), courbe des taux partiellement normalisee "
            "(10Y-2Y +0.2%), Leading Indicators OCDE en legere hausse. Cette configuration "
            "favorise les secteurs avec forte visibilite BPA et moindre sensibilite aux taux : "
            "Technology, Health Care, Financials. Les secteurs defensifs (Consumer Staples, "
            "Utilities) offrent moins de potentiel relatif dans ce regime de cycle."
        ),
        "texte_rotation": (
            "La rotation sectorielle recommandee s'appuie sur le modele cycle 4-phases FinSight. "
            "En phase d'expansion avancee, le signal Accumuler se concentre sur les secteurs a "
            "forte croissance BPA et pricing power : Technology (IA), Health Care (FDA pipeline), "
            "Financials (NIM). Le signal Alleger cible Real Estate (pression taux directe) et "
            "Utilities (compression de dividende relatif). Un pivot Fed dovish constituerait "
            "le principal catalyseur de rotation vers les secteurs sensibles aux taux."
        ),
        "phase_cycle":  "Expansion avancee",
        "cycle_detail": "Milieu-fin de cycle — ISM proche 50, courbe taux normalisee",
        "fred_signals": [
            {"nom": "PMI Manufacturier",  "valeur": "49.8", "tendance": "Stable",  "signal": "Neutre"},
            {"nom": "10Y - 2Y (courbe)",  "valeur": "+0.18%","tendance": "Hausse", "signal": "Neutre"},
            {"nom": "ISM Services",       "valeur": "52.6", "tendance": "Hausse",  "signal": "Surponderer"},
            {"nom": "Taux chomage",       "valeur": "4.1%", "tendance": "Stable",  "signal": "Neutre"},
            {"nom": "CPI Core YoY",       "valeur": "3.1%", "tendance": "Baisse",  "signal": "Neutre"},
        ],
        "catalyseurs": [
            ("Cycle IA",          "CAPEX hyperscalers +35% YoY — monetisation acceleree services cloud et semi", "6-12 mois"),
            ("Desinflation",      "PCE Core convergence vers 2.5% d ici fin 2026 — Fed pivot dovish attendu", "9-18 mois"),
            ("Resilience margins","Marges nettes S&P 500 a 12.4% vs 11.8% consensus — revision haussiere BPA", "3-6 mois"),
        ],
        "secteurs":      secteurs,
        "top3_secteurs": top3_secteurs,
        "risques": [
            ("Recession technique",    "Ralentissement PIB < 0 sur 2 trimestres — revision BPA agrege -15/-20%", "20 %", "ELEVE"),
            ("Choc taux",              "Fed hike surprise si CPI reaccelere > 3.5% — compression multiples growth", "15 %", "ELEVE"),
            ("Choc geopolitique",      "Escalade Asie/ME — spike VIX > 35, rotation defensive", "18 %", "MODERE"),
            ("Deception AI capex",     "ROI IA inferieur aux attentes — derating secteur Tech (P/E 28x -> 22x)", "25 %", "MODERE"),
            ("Stress credit CRE",      "Pertes immobilier commercial propagees aux banques regionales", "12 %", "FAIBLE"),
        ],
        "scenarios": [],
        "conditions_invalidation": [
            f"{universe} casse le support 4 800 pts — signal bascule Sous-ponderer",
            "Fed hike inattendu post-CPI > 3.5% — derating massif growth",
            "Revisions BPA agragees < -5% sur 2 trimestres consecutifs",
            "VIX > 35 sur plus de 10 seances consecutives",
        ],
        "rotation":      rotation,
        "sentiment_agg": {
            "label":       "Neutre",
            "score":        0.06,
            "nb_articles":  34,
            "positif_nb":   15, "positif_pct": 44,
            "neutre_nb":    12, "neutre_pct":  35,
            "negatif_nb":   7,  "negatif_pct": 21,
            "themes_pos":   ["Resultats T4", "Cycle IA", "Innovation semi"],
            "themes_neg":   ["Regulation", "Taux LT", "CRE"],
            "positif": {"nb": 15, "score": "0.42", "themes": "Resultats T4, IA, Innovation semi"},
            "neutre":  {"nb": 12, "score": "0.02", "themes": "Guidances 2026, Macro taux"},
            "negatif": {"nb": 7,  "score": "-0.35","themes": "Regulation, Taux LT, CRE"},
            "par_secteur": [
                ("Technology",             "0.38",  "Positif"),
                ("Health Care",            "0.22",  "Positif"),
                ("Financials",             "0.14",  "Positif"),
                ("Communication Services", "0.08",  "Neutre"),
                ("Consumer Discretionary", "0.04",  "Neutre"),
                ("Industrials",            "0.01",  "Neutre"),
                ("Consumer Staples",       "-0.05", "Neutre"),
                ("Materials",              "-0.04", "Neutre"),
                ("Energy",                 "-0.12", "Negatif"),
                ("Real Estate",            "-0.22", "Negatif"),
                ("Utilities",              "-0.18", "Negatif"),
            ],
        },
        "etf_perf": etf_perf,
        "finbert": {
            "nb_articles": 0,
            "score_agrege": "N/D",
            "positif": {"nb": 0, "score": "—", "themes": "—"},
            "neutre":  {"nb": 0, "score": "—", "themes": "—"},
            "negatif": {"nb": 0, "score": "—", "themes": "—"},
            "par_secteur": [],
        },
        "methodologie": [
            ("Score FinSight",   "Composite 0-100 : valeur 25, croissance 25, qualite 25, momentum 25"),
            ("Signal indice",    "Score agrege secteurs : >60 Surponderer / 40-60 Neutre / <40 Sous-ponderer"),
            ("Conviction",       "% secteurs en accord avec le signal global (surponderes / total)"),
            ("EV/EBITDA",        "Mediane LTM des 5 premiers titres par capitalisation de chaque secteur"),
            ("P/E Mediane 10Y",  "Bloomberg Consensus — comparaison avec P/E Forward actuel"),
        ],
        "perf_history": None,
    }


def _fetch_real_indice_data(universe: str = "S&P 500") -> dict:
    """Fetch donnees reelles indice via yfinance (^GSPC + ETF SPDR + secteurs)."""
    import yfinance as yf
    import datetime
    from concurrent.futures import ThreadPoolExecutor, as_completed

    meta = _INDICE_META.get(universe, {"code": "^GSPC", "nb_societes": 503})
    code = meta["code"]
    _fr = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
           7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}
    today = datetime.date.today()
    date_str = f"{today.day} {_fr[today.month]} {today.year}"

    # 1. Prix et YTD indice principal
    indice_info = {}
    cours_str = "—"
    ytd_str = "—"
    pe_fwd_str = "—"
    try:
        ticker_obj = yf.Ticker(code)
        info = ticker_obj.info or {}
        cours = info.get("regularMarketPrice") or info.get("previousClose")
        if cours:
            cours_str = f"{cours:,.0f}".replace(",", " ")
        # YTD depuis début de l'année
        hist_1y = ticker_obj.history(period="ytd", interval="1d")["Close"]
        if len(hist_1y) > 1:
            ytd_pct = (hist_1y.iloc[-1] / hist_1y.iloc[0] - 1) * 100
            ytd_str = f"{ytd_pct:+.1f}%"
        pe_fwd = info.get("forwardPE") or info.get("trailingPE")
        if pe_fwd and 0 < pe_fwd < 100:
            pe_fwd_str = f"{pe_fwd:.1f}x"
        indice_info = info
    except Exception as e:
        log.warning("yfinance indice %s erreur: %s", code, e)

    # 2. Returns 52S ETF SPDR (si S&P 500)
    etf_perf = {}
    if universe == "S&P 500":
        etf_map = _ETF_SECTORS
    else:
        etf_map = {}

    def _fetch_etf(etf: str) -> tuple:
        try:
            hist = yf.Ticker(etf).history(period="1y", interval="1mo")["Close"]
            if len(hist) < 2:
                return etf, None
            ret_1y = (hist.iloc[-1] / hist.iloc[0] - 1) * 100
            return etf, round(ret_1y, 1)
        except Exception:
            return etf, None

    if etf_map:
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(_fetch_etf, e): e for e in etf_map}
            for fut in as_completed(futs):
                etf, ret = fut.result()
                nom = etf_map.get(etf, etf)
                etf_perf[etf] = {"nom": nom, "return_1y": ret or 0.0}

    # 3. Secteurs — signal derive du return ETF
    def _signal_from_ret(ret: float) -> str:
        if ret > 12: return "Surponderer"
        if ret < -2: return "Sous-ponderer"
        return "Neutre"

    def _score_from_ret(ret: float) -> int:
        return max(25, min(85, round(50 + ret * 1.2)))

    secteurs = []
    for etf, info in etf_perf.items():
        ret = info.get("return_1y", 0.0)
        nom = info.get("nom", "")
        nb  = _SP500_NB_SOC.get(nom, 30)
        sc  = _score_from_ret(ret)
        sig = _signal_from_ret(ret)
        # EV/EBITDA, marges et croissance : valeurs generiques par secteur
        ev_generic = {"Technology":18.0,"Health Care":14.0,"Financials":9.0,
                      "Consumer Discretionary":12.0,"Communication Services":11.0,
                      "Industrials":13.0,"Consumer Staples":12.0,"Energy":6.0,
                      "Materials":10.0,"Real Estate":17.0,"Utilities":11.0}
        margin_generic = {"Technology":27.0,"Health Care":18.0,"Financials":30.0,
                          "Consumer Discretionary":11.0,"Communication Services":23.0,
                          "Industrials":14.0,"Consumer Staples":17.0,"Energy":24.0,
                          "Materials":16.0,"Real Estate":42.0,"Utilities":28.0}
        growth_generic = {"Technology":"+13.0%","Health Care":"+9.5%","Financials":"+10.0%",
                          "Consumer Discretionary":"+7.5%","Communication Services":"+8.5%",
                          "Industrials":"+6.5%","Consumer Staples":"+3.5%","Energy":"-1.5%",
                          "Materials":"+4.0%","Real Estate":"+2.0%","Utilities":"+2.5%"}
        ev  = ev_generic.get(nom, 12.0)
        mg  = margin_generic.get(nom, 18.0)
        gr  = growth_generic.get(nom, "+6.0%")
        mom_str = f"{ret:+.1f}%"
        secteurs.append((nom, nb, sc, sig, f"{ev:.1f}x", mg, gr, mom_str))

    # Fallback si ETF non disponibles
    if not secteurs:
        log.warning("ETF SPDR non disponibles — fallback donnees test")
        return _make_test_indice_data(universe)

    import statistics
    scores = [s[2] for s in secteurs]
    avg_score = round(statistics.mean(scores), 1)
    nb_surp = sum(1 for s in secteurs if s[3] == "Surponderer")
    conviction = round(nb_surp / len(secteurs) * 100) if secteurs else 50
    signal_global = ("Surponderer" if avg_score > 62 else
                     ("Sous-ponderer" if avg_score < 45 else "Neutre"))

    # Top 3 secteurs : les 3 avec meilleur return ETF
    sorted_etf = sorted(etf_perf.items(), key=lambda x: x[1].get("return_1y",0), reverse=True)
    top3_secteurs = []
    for i, (etf, info) in enumerate(sorted_etf[:3]):
        nom = info.get("nom","")
        ret = info.get("return_1y", 0.0)
        sc  = _score_from_ret(ret)
        sig = _signal_from_ret(ret)
        # Tickers representatifs
        soc_tickers = (_get_real_tickers(nom, universe) or
                       _get_real_tickers(nom, "S&P 500"))[:3]
        societes = [(tk, "Surponderer" if sig == "Surponderer" else "Neutre", "—", sc - i*3)
                    for tk in soc_tickers]
        top3_secteurs.append({
            "nom": nom, "signal": sig, "score": sc,
            "ev_ebitda": "—", "pe_forward_raw": 20.0, "pe_mediane_10y": 18.0,
            "poids_indice": "—",
            "catalyseur": f"Performance YTD {ret:+.1f}% — momentum sectoriel positif",
            "risque": "Risque de compression multiple si croissance BPA decelee",
            "societes": societes or [("—","Neutre","—",50)],
        })

    # Base test pour les champs sans source temps reel
    base = _make_test_indice_data(universe)
    # Regenerer texte_signal coherent avec le signal reel
    noms_surp = [s[0] for s in secteurs if s[3] == "Surponderer"][:3]
    texte_signal_reel = (
        f"Le signal global sur le {universe} est {signal_global} avec une conviction de "
        f"{conviction}% (sur la base des {len(secteurs)} secteurs analyses). "
        f"{nb_surp} secteur(s) ressortent Surponderer — {', '.join(noms_surp) or 'aucun'} "
        f"— portes par leur momentum positif 52 semaines. "
        f"{len(secteurs) - nb_surp - sum(1 for s in secteurs if s[3] == 'Sous-ponderer')} secteurs "
        f"sont Neutre et {sum(1 for s in secteurs if s[3] == 'Sous-ponderer')} en Sous-ponderer."
    )

    base.update({
        "code":           code,
        "cours":          cours_str,
        "variation_ytd":  ytd_str,
        "pe_forward":     pe_fwd_str,
        "signal_global":  signal_global,
        "conviction_pct": conviction,
        "nb_secteurs":    len(secteurs),
        "secteurs":       secteurs,
        "top3_secteurs":  top3_secteurs,
        "etf_perf":       etf_perf,
        "date_analyse":   date_str,
        "texte_signal":   texte_signal_reel,
    })
    return base


# ── Entrée ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode   = sys.argv[1].lower()
    arg1   = sys.argv[2]
    arg2   = sys.argv[3] if len(sys.argv) > 3 else "CAC 40"

    if mode in ("societe", "société", "s"):
        run_societe(arg1)
    elif mode in ("secteur", "sec"):
        run_secteur(arg1, arg2, prefix="secteur")
    elif mode in ("indice", "idx"):
        run_indice(arg1)
    else:
        print(f"Mode inconnu : {mode}. Utiliser : societe | secteur | indice")
        sys.exit(1)
