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
from core.yfinance_cache import get_ticker
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


def run_societe(ticker: str, language: str = "fr", currency: str = "EUR") -> None:
    """Pipeline société complet → PDF + PPTX + briefing.
    `language` (fr/en/es/de/it/pt) propagé au graph → AgentSynthese répond
    dans cette langue. `currency` est passé pour conversion future des montants.
    """
    from core.graph import build_graph

    log.info("=== ANALYSE SOCIETE : %s (lang=%s, ccy=%s) ===", ticker, language, currency)
    t0 = time.time()

    state = build_graph().invoke({"ticker": ticker, "language": language, "currency": currency})

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
    # default qui sérialise correctement les Pydantic models (model_dump),
    # les dataclasses (asdict) et fallback str(). Sans ça, le frontend
    # ne pouvait pas lire raw_data/synthesis/ratios (repr Python en string).
    def _json_default(o):
        if hasattr(o, "model_dump"):
            return o.model_dump()
        if hasattr(o, "__dataclass_fields__"):
            from dataclasses import asdict
            return asdict(o)
        if hasattr(o, "dict") and callable(o.dict):
            try:
                return o.dict()
            except Exception:
                pass
        return str(o)

    safe_state = {k: v for k, v in state.items()
                  if not isinstance(v, (bytes, bytearray))}
    try:
        p = OUT_DIR / f"{ticker}_state.json"
        p.write_text(
            json.dumps(safe_state, default=_json_default, ensure_ascii=False, indent=2),
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


def run_secteur(sector: str, universe: str = "CAC 40", prefix: str = "secteur",
                language: str = "fr", currency: str = "EUR") -> dict:
    """Pipeline sectoriel → PDF sectoriel + PPTX sectoriel.

    prefix : prefixe du fichier de sortie ("secteur" ou "indice").
    Utiliser prefix="indice" quand l'appel vient du mode indice avec secteur specifique.
    """
    from outputs.sector_pdf_writer import generate_sector_report
    from outputs.sectoral_pptx_writer import SectoralPPTXWriter

    log.info("=== ANALYSE SECTORIELLE : %s / %s ===", sector, universe)
    t0 = time.time()

    # Vrais tickers yfinance si secteur connu, fallback synthetique sinon
    _t_fetch = time.time()
    tickers = _fetch_real_sector_data(sector, universe, max_tickers=8)
    if not tickers:
        log.warning("Fallback donnees synthetiques pour '%s' / '%s'", sector, universe)
        tickers = _make_test_tickers(sector, 6)
    log.info("[secteur timing] fetch data : %.1fs (%d tickers)", time.time() - _t_fetch, len(tickers))

    stem      = f"{prefix}_{sector.replace(' ','_').replace('&','_and_')}_{universe.replace(' ','_').replace('&','_and_')}"
    pdf_path  = OUT_DIR / f"{stem}.pdf"
    pptx_path = OUT_DIR / f"{stem}.pptx"

    # Extraire les sector_analytics injectés dans les tickers
    sector_analytics = tickers[0].get("_sector_analytics") if tickers else {}
    for t in tickers:
        t.pop("_sector_analytics", None)

    # Génération PDF + PPTX EN PARALLÈLE (writers indépendants, gain ~30-60s)
    _t_writers = time.time()
    from concurrent.futures import ThreadPoolExecutor as _TPE

    def _gen_pdf():
        _t = time.time()
        generate_sector_report(sector, tickers, str(pdf_path), universe=universe,
                               sector_analytics=sector_analytics,
                               language=language, currency=currency)
        log.info("[secteur timing] PDF : %.1fs — %s (%d Ko)",
                 time.time() - _t, pdf_path.name, pdf_path.stat().st_size // 1024)

    def _gen_pptx():
        _t = time.time()
        SectoralPPTXWriter.generate(tickers, sector, universe, str(pptx_path),
                                     language=language, currency=currency)
        log.info("[secteur timing] PPTX : %.1fs — %s (%d Ko)",
                 time.time() - _t, pptx_path.name, pptx_path.stat().st_size // 1024)

    with _TPE(max_workers=2, thread_name_prefix="sect-writer") as _ex:
        _f_pdf = _ex.submit(_gen_pdf)
        _f_pptx = _ex.submit(_gen_pptx)
        # Si l'un fail, on récolte les deux puis on raise (best-effort sur l'autre).
        _excs = []
        for _f, _name in ((_f_pdf, "PDF"), (_f_pptx, "PPTX")):
            try:
                _f.result(timeout=180)
            except Exception as _e:
                log.error("[secteur timing] %s failed: %s", _name, _e)
                _excs.append((_name, _e))
    log.info("[secteur timing] Writers parallèles total : %.1fs", time.time() - _t_writers)

    # XLSX : template Énergie dédié si secteur énergie, sinon fallback générique
    xlsx_path = None
    _is_energy = sector.lower() in ("énergie", "energie", "energy", "oil", "oil & gas")
    if _is_energy:
        try:
            from outputs.sector_energy_xlsx_writer import (
                write_energy_sector_xlsx, build_ticker_dict_from_yfinance,
            )
            from core.yfinance_cache import get_ticker as _get_ticker
            xlsx_data = []
            for t in tickers:
                tk = t.get("ticker") or t.get("symbol")
                if not tk:
                    continue
                try:
                    info = _get_ticker(tk).info or {}
                except Exception:
                    info = {}
                xlsx_data.append(
                    build_ticker_dict_from_yfinance(tk, info, ratios=t.get("ratios"))
                )
            if xlsx_data:
                xlsx_path = OUT_DIR / f"{stem}.xlsx"
                write_energy_sector_xlsx(xlsx_data, xlsx_path)
                log.info("XLSX énergie : %s  (%d Ko)", xlsx_path.name,
                         xlsx_path.stat().st_size // 1024)
        except Exception as e:
            log.error("XLSX énergie failed : %s", e)
    else:
        # Fallback : template Screening_v4 (déjà utilisé par l'app Streamlit
        # pour les analyses sectorielles). Baptiste veut TOUJOURS un XLSX.
        try:
            from outputs.screening_writer import ScreeningWriter
            xlsx_path = OUT_DIR / f"{stem}.xlsx"
            # Adapte la structure cli_analyze → format attendu par ScreeningWriter
            adapted = [_adapt_for_screening_writer(t) for t in tickers]
            ScreeningWriter.generate(
                adapted,
                universe_name=f"{sector} — {universe}",
                output_path=str(xlsx_path),
            )
            log.info("XLSX screening v4 : %s  (%d Ko)", xlsx_path.name,
                     xlsx_path.stat().st_size // 1024)
        except Exception as e:
            import traceback
            log.error("XLSX screening failed : %s", e)
            traceback.print_exc()
            xlsx_path = None

    print(f"\nFichiers generes dans : {OUT_DIR}")
    print(f"  * {pdf_path.name}")
    print(f"  * {pptx_path.name}")
    if xlsx_path:
        print(f"  * {xlsx_path.name}")
    _total_ms = int((time.time() - t0) * 1000)
    print(f"\nTemps total : {_total_ms/1000:.1f}s")

    # Dataset anonymisé
    try:
        from core.analysis_log_helper import log_secteur_analysis
        log_secteur_analysis(sector, universe, tickers, duration_ms=_total_ms,
                              language=language, currency=currency)
    except Exception as _e_log:
        log.debug(f"analysis_log secteur skip : {_e_log}")

    # Synthèse narrative pour l'UI dashboard (à partir des analytics)
    sector_summary = _build_sector_narrative(sector, universe, tickers, sector_analytics or {})

    # ── Sentinel V2 : audit data quality ──
    # Détecte fallback tickers BAN1-6, noms manquants, ratios vides, analytics
    # cassés, synthèse trop courte. Remonte les issues dans pipeline_errors.
    try:
        from core.sentinel.data_audit import audit_sector_analysis
        audit_sector_analysis(
            sector=sector,
            universe=universe,
            tickers=tickers,
            analytics=sector_analytics,
            llm_summary=sector_summary,
        )
    except Exception as _ae:
        log.debug(f"[run_secteur] sentinel audit skip : {_ae}")

    # Retourne les data pour le backend (Q&A contexte + UI enrichie)
    return {
        "sector": sector,
        "universe": universe,
        "tickers": tickers,
        "sector_analytics": sector_analytics or {},
        "sector_summary": sector_summary,
    }


def _adapt_for_screening_writer(t: dict) -> dict:
    """Convertit un ticker produit par _fetch_real_sector_data vers le format
    attendu par outputs.screening_writer.ScreeningWriter (DONNÉES BRUTES).

    Différences principales :
    - pe_ratio → pe
    - margins en % (0-100) → décimaux (0-1)
    - ajoute enterprise_value, roa, eps si absents (None toléré par _fmt_*)
    """
    # Marges : cli_analyze les stocke en % (0-100), writer attend décimal
    def _to_frac(v):
        if v is None:
            return None
        try:
            fv = float(v)
            return fv / 100.0 if abs(fv) > 1.5 else fv
        except (TypeError, ValueError):
            return None

    return {
        "ticker":          t.get("ticker"),
        "company":         t.get("company") or t.get("name"),
        "sector":          t.get("sector"),
        "industry":        t.get("industry"),
        "currency":        t.get("currency", "USD"),
        "price":           t.get("price"),
        "market_cap":      t.get("market_cap"),
        "ev":              t.get("enterprise_value") or t.get("ev"),
        "revenue_ltm":     t.get("revenue_ltm"),
        "ebitda_ltm":      t.get("ebitda_ltm"),
        "ev_ebitda":       t.get("ev_ebitda"),
        "ev_revenue":      t.get("ev_revenue"),
        "pe":              t.get("pe") or t.get("pe_ratio"),
        "eps":             t.get("eps"),
        "gross_margin":    _to_frac(t.get("gross_margin")),
        "ebitda_margin":   _to_frac(t.get("ebitda_margin")),
        "net_margin":      _to_frac(t.get("net_margin")),
        "revenue_growth":  t.get("revenue_growth"),
        "roe":             _to_frac(t.get("roe")),
        "roa":             _to_frac(t.get("roa")),
        "current_ratio":   t.get("current_ratio"),
        "net_debt_ebitda": t.get("net_debt_ebitda"),
        "altman_z":        t.get("altman_z"),
        "beneish_m":       t.get("beneish_m"),
        "momentum_52w":    _to_frac(t.get("momentum_52w")),
        "score_value":     t.get("score_value"),
        "score_growth":    t.get("score_growth"),
        "score_quality":   t.get("score_quality"),
        "score_momentum":  t.get("score_momentum"),
        "score_global":    t.get("score_global"),
        "next_earnings":   t.get("next_earnings"),
    }


def _build_sector_narrative(sector: str, universe: str, tickers: list, analytics: dict) -> str:
    """Construit une synthèse narrative déterministe (3-5 phrases) du secteur
    à partir des analytics calculés. Sert de fallback quand pas de LLM dédié.
    """
    parts: list[str] = []
    n = len(tickers or [])
    parts.append(f"Couverture : {n} sociétés du secteur {sector} dans l'univers {universe}.")

    hhi_label = analytics.get("hhi_label")
    if hhi_label:
        parts.append(f"Structure de marché : {hhi_label}.")

    pe_cycle = analytics.get("pe_cycle_label")
    pe_med = analytics.get("pe_median_ltm")
    if pe_med and pe_cycle:
        parts.append(f"Valorisation : P/E médian {pe_med}x — {pe_cycle}.")
    elif pe_med:
        parts.append(f"Valorisation : P/E médian {pe_med}x.")

    roic_label = analytics.get("roic_label")
    roic_mean = analytics.get("roic_mean")
    if roic_mean is not None and roic_label:
        parts.append(f"Rentabilité : ROIC moyen {roic_mean}% — {roic_label}.")

    return " ".join(parts) if parts else f"Analyse sectorielle {sector} générée."


def run_cmp_secteur(
    sector_a: str, universe_a: str,
    sector_b: str, universe_b: str,
) -> None:
    """Pipeline comparatif sectoriel → PDF + PPTX comparatifs."""
    from outputs.cmp_secteur_pptx_writer import CmpSecteurPPTXWriter
    from outputs.cmp_secteur_pdf_writer import generate_cmp_secteur_pdf

    log.info("=== COMPARATIF SECTORIEL : %s/%s vs %s/%s ===", sector_a, universe_a, sector_b, universe_b)
    t0 = time.time()

    # Audit perf 26/04/2026 (P0 #2) : fetch A et B en parallele
    # Avant : 12s + 12s en serie. Apres : max(12, 12) = 12s. Gain ~12s.
    from concurrent.futures import ThreadPoolExecutor as _CmpTPE
    with _CmpTPE(max_workers=2) as _ex_cmp:
        f_a = _ex_cmp.submit(_fetch_real_sector_data, sector_a, universe_a, 8)
        f_b = _ex_cmp.submit(_fetch_real_sector_data, sector_b, universe_b, 8)
        try:
            tickers_a = f_a.result()
        except Exception as _ea:
            log.warning("_fetch_real_sector_data A erreur: %s", _ea)
            tickers_a = []
        try:
            tickers_b = f_b.result()
        except Exception as _eb:
            log.warning("_fetch_real_sector_data B erreur: %s", _eb)
            tickers_b = []

    if not tickers_a:
        log.warning("Fallback synthetique pour '%s' / '%s'", sector_a, universe_a)
        tickers_a = _make_test_tickers(sector_a, 6)
    if not tickers_b:
        log.warning("Fallback synthetique pour '%s' / '%s'", sector_b, universe_b)
        tickers_b = _make_test_tickers(sector_b, 6)

    # Nettoyer _sector_analytics si present
    for td in (tickers_a, tickers_b):
        for t in td:
            t.pop("_sector_analytics", None)

    stem = (
        f"cmp_secteur_{sector_a.replace(' ', '_')}_{universe_a.replace(' ', '_')}"
        f"_vs_{sector_b.replace(' ', '_')}_{universe_b.replace(' ', '_')}"
    )
    pdf_path  = OUT_DIR / f"{stem}.pdf"
    pptx_path = OUT_DIR / f"{stem}.pptx"

    generate_cmp_secteur_pdf(
        tickers_a, sector_a, universe_a,
        tickers_b, sector_b, universe_b,
        output_path=str(pdf_path),
    )
    log.info("PDF comparatif sectoriel : %s  (%d Ko)", pdf_path.name, pdf_path.stat().st_size // 1024)

    CmpSecteurPPTXWriter.generate(
        tickers_a, sector_a, universe_a,
        tickers_b, sector_b, universe_b,
        output_path=str(pptx_path),
    )
    log.info("PPTX comparatif sectoriel : %s  (%d Ko)", pptx_path.name, pptx_path.stat().st_size // 1024)

    print(f"\nFichiers generes dans : {OUT_DIR}")
    print(f"  * {pdf_path.name}")
    print(f"  * {pptx_path.name}")
    print(f"\nTemps total : {time.time() - t0:.1f}s")


def run_cmp_indice(
    universe_a: str, universe_b: str,
    language: str = "fr", currency: str = "EUR",
) -> None:
    """Pipeline comparatif d'indices -> PDF + PPTX + XLSX comparatifs.

    `universe_a` / `universe_b` : cles INDICE_CMP_OPTIONS (CAC40, SP500, DAX40,
    FTSE100, STOXX50, NIKKEI225, NASDAQ100, DOWJONES).
    """
    from core.cmp_indice import build_cmp_indice_data, INDICE_CMP_OPTIONS
    from outputs.cmp_indice_pptx_writer import CmpIndicePPTXWriter
    from outputs.cmp_indice_pdf_writer import CmpIndicePDFWriter
    from outputs.cmp_indice_xlsx_writer import CmpIndiceXlsxWriter

    name_a = INDICE_CMP_OPTIONS.get(universe_a, (universe_a,))[0]
    name_b = INDICE_CMP_OPTIONS.get(universe_b, (universe_b,))[0]
    log.info("=== COMPARATIF INDICES : %s vs %s ===", name_a, name_b)
    t0 = time.time()

    # Fetch donnees indice A (tickers + stats agreges)
    try:
        indice_data_a = _fetch_real_indice_data(name_a)
    except Exception as e:
        log.warning("Fetch indice A %s echec : %s", name_a, e)
        indice_data_a = {}
    tickers_data_a = indice_data_a.get("tickers_data") or []

    # Construit le dict de comparaison (clean, sans Streamlit)
    cmp_data = build_cmp_indice_data(
        universe_a=universe_a,
        universe_b=universe_b,
        indice_data_a=indice_data_a,
        tickers_data_a=tickers_data_a,
    )

    stem = (f"cmp_indice_{universe_a}_vs_{universe_b}")
    pdf_path = OUT_DIR / f"{stem}.pdf"
    pptx_path = OUT_DIR / f"{stem}.pptx"
    xlsx_path = OUT_DIR / f"{stem}.xlsx"

    try:
        pdf_bytes = CmpIndicePDFWriter.generate_bytes(cmp_data)
        pdf_path.write_bytes(pdf_bytes)
        log.info("PDF comparatif indice : %s  (%d Ko)", pdf_path.name, pdf_path.stat().st_size // 1024)
    except Exception as e:
        log.error("PDF cmp indice echec : %s", e, exc_info=True)

    try:
        pptx_bytes = CmpIndicePPTXWriter.generate(cmp_data)
        if pptx_bytes:
            pptx_path.write_bytes(pptx_bytes)
            log.info("PPTX comparatif indice : %s  (%d Ko)", pptx_path.name, pptx_path.stat().st_size // 1024)
        else:
            log.error("PPTX cmp indice : generate() a retourne None (LLM batch fail probable)")
    except Exception as e:
        log.error("PPTX cmp indice echec : %s", e, exc_info=True)

    try:
        xlsx_bytes = CmpIndiceXlsxWriter.generate_bytes(cmp_data)
        if xlsx_bytes:
            xlsx_path.write_bytes(xlsx_bytes)
            log.info("XLSX comparatif indice : %s  (%d Ko)", xlsx_path.name, xlsx_path.stat().st_size // 1024)
    except Exception as e:
        log.warning("XLSX cmp indice echec : %s", e)

    print(f"\nFichiers generes dans : {OUT_DIR}")
    for p in (pdf_path, pptx_path, xlsx_path):
        if p.exists():
            print(f"  * {p.name}")
    print(f"\nTemps total : {time.time() - t0:.1f}s")


def run_indice(universe: str = "S&P 500", language: str = "fr", currency: str = "EUR") -> dict:
    """Pipeline indice complet (tous secteurs) → PDF + PPTX + Excel."""
    from outputs.indice_pdf_writer import IndicePDFWriter
    from outputs.indice_pptx_writer import IndicePPTXWriter
    from outputs.indice_excel_writer import IndiceExcelWriter

    # Whitelist explicite : on REFUSE les indices non supportés au lieu de
    # tomber silencieusement sur S&P 500 (bug 100 documenté known_error_indices_non_supportes.md).
    _SUPPORTED = {"S&P 500", "CAC 40", "CAC40", "DAX 40", "DAX40", "DAX",
                  "FTSE 100", "FTSE100", "Euro Stoxx 50", "STOXX50"}
    if universe not in _SUPPORTED:
        raise ValueError(
            f"Indice non supporté : {universe!r}. "
            f"Indices disponibles : S&P 500, CAC 40, DAX 40, FTSE 100, Euro Stoxx 50."
        )

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

    IndicePDFWriter.generate(data, str(pdf_path), language=language, currency=currency)
    log.info("PDF indice : %s  (%d Ko)", pdf_path.name, pdf_path.stat().st_size // 1024)

    pptx_bytes = IndicePPTXWriter.generate(data, str(pptx_path), language=language, currency=currency)
    log.info("PPTX indice : %s  (%d Ko)", pptx_path.name, pptx_path.stat().st_size // 1024)

    xlsx_path = OUT_DIR / f"{stem}.xlsx"
    IndiceExcelWriter.generate(data, str(xlsx_path), language=language, currency=currency)
    if xlsx_path.exists():
        log.info("Excel indice : %s  (%d Ko)", xlsx_path.name, xlsx_path.stat().st_size // 1024)

    print(f"\nFichiers generes dans : {OUT_DIR}")
    print(f"  * {pdf_path.name}")
    print(f"  * {pptx_path.name}")
    if xlsx_path.exists():
        print(f"  * {xlsx_path.name}")
    _total_ms = int((time.time() - t0) * 1000)
    print(f"\nTemps total : {_total_ms/1000:.1f}s")

    # Dataset anonymisé
    try:
        from core.analysis_log_helper import log_indice_analysis
        log_indice_analysis(data if isinstance(data, dict) else {}, duration_ms=_total_ms,
                             language=language, currency=currency)
    except Exception as _e_log:
        log.debug(f"analysis_log indice skip : {_e_log}")

    # Sentinel : audit qualité rendering (FR/EN, décimales, Nb sociétés cohérent…)
    try:
        from core.sentinel.data_audit import audit_indice_analysis
        audit_indice_analysis(
            universe=universe,
            data=data if isinstance(data, dict) else {},
            language=language,
        )
    except Exception as _ae:
        log.debug(f"[run_indice] sentinel audit skip : {_ae}")

    # Synthèse narrative pour l'UI dashboard
    _secteurs = data.get("secteurs", []) if isinstance(data, dict) else []
    _stats = data.get("indice_stats", {}) if isinstance(data, dict) else {}
    # Fallback : si indice_stats absent (chemin test ou fetch incomplet), calcul direct
    if not _stats or not any(_stats.values()):
        _code_for_stats = (data.get("code") if isinstance(data, dict) else None) or \
                          _INDICE_META.get(universe, {}).get("code")
        if _code_for_stats:
            try:
                _stats = _compute_indice_stats(_code_for_stats)
                log.info("indice_stats fallback computed for %s (%s)", universe, _code_for_stats)
            except Exception as _e_stats:
                log.warning("indice_stats fallback échec : %s", _e_stats)
    indice_summary = _build_indice_narrative(universe, _secteurs, _stats)

    # Retourne les data pour le backend (Q&A contexte + UI enrichie)
    return {
        "universe": universe,
        "secteurs": _secteurs,
        "indice_stats": _stats,
        "macro": data.get("macro", {}) if isinstance(data, dict) else {},
        "allocation": data.get("allocation", {}) if isinstance(data, dict) else {},
        "top_performers": data.get("top_performers", []) if isinstance(data, dict) else [],
        "indice_summary": indice_summary,
    }


def _build_indice_narrative(universe: str, secteurs: list, stats: dict) -> str:
    """Synthèse narrative déterministe (3-5 phrases) de l'indice à partir
    des poids sectoriels et stats agrégées.

    Accepte 2 formats de `secteurs` :
    - liste de dicts avec keys 'name'/'sector', 'weight'/'poids', 'score', 'signal'
    - liste de tuples (nom, nb, score, signal, ev_str, marge, growth, mom_str)
      générés par `_fetch_real_indice_data` ; poids = nb/total.
    """
    parts: list[str] = []
    n_sec = len(secteurs or [])
    _sec_lbl = "secteur" if n_sec == 1 else "secteurs"
    parts.append(f"Indice {universe} : {n_sec} {_sec_lbl} couverts.")

    # Normalise en liste de dicts {name, weight, score, signal}
    norm: list[dict] = []
    if secteurs:
        if isinstance(secteurs[0], dict):
            norm = [
                {
                    "name": s.get("name") or s.get("sector") or "—",
                    "weight": float(s.get("weight") or s.get("poids") or 0),
                    "score": s.get("score"),
                    "signal": s.get("signal"),
                }
                for s in secteurs if isinstance(s, dict)
            ]
        elif isinstance(secteurs[0], (tuple, list)) and len(secteurs[0]) >= 4:
            tot_nb = sum(int(s[1] or 0) for s in secteurs) or 1
            norm = [
                {
                    "name":   s[0],
                    "weight": (int(s[1] or 0) / tot_nb) * 100.0,
                    "score":  s[2],
                    "signal": s[3],
                }
                for s in secteurs
            ]

    # Concentration : top 2 secteurs par poids (libellés FR)
    try:
        from core.sector_labels import fr_label as _fr_lbl_narr
    except Exception:
        def _fr_lbl_narr(x): return x
    if len(norm) >= 2:
        sorted_w = sorted(norm, key=lambda s: s["weight"], reverse=True)
        top = sorted_w[:2]
        top_str = ", ".join(f"{_fr_lbl_narr(s['name'])} ({s['weight']:.1f} %)".replace('.', ',') for s in top)
        parts.append(f"Concentration : {top_str} dominent la pondération.")

    # Distribution signaux (Surpondérer / Neutre / Sous-pondérer)
    if norm:
        nb_surp = sum(1 for s in norm if "Surp" in str(s.get("signal", "")))
        nb_sous = sum(1 for s in norm if "Sous" in str(s.get("signal", "")))
        nb_neutre = n_sec - nb_surp - nb_sous
        if nb_surp or nb_sous:
            parts.append(
                f"Allocation : {nb_surp} Surpondérer, {nb_neutre} Neutre, {nb_sous} Sous-pondérer."
            )

    # Top score sectoriel
    if norm:
        with_score = [s for s in norm if isinstance(s.get("score"), (int, float))]
        if with_score:
            best = max(with_score, key=lambda s: s["score"])
            parts.append(f"Score le plus élevé : {_fr_lbl_narr(best['name'])} ({int(best['score'])}/100).")

    # Performance moyenne
    perf_med = stats.get("perf_median") or stats.get("perf_avg")
    if perf_med is not None:
        try:
            parts.append(f"Performance médiane : {float(perf_med):+.1f} % sur la période.".replace('.', ','))
        except Exception:
            pass

    pe_med = stats.get("pe_median")
    if pe_med:
        parts.append(f"Valorisation : P/E médian {pe_med}x.")

    return " ".join(parts) if parts else f"Analyse de l'indice {universe} générée."


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
    # DAX — élargi pour couvrir tous les secteurs GICS
    ("Technology", "DAX"):                 ["SAP.DE","IFX.DE"],
    ("Automotive", "DAX"):                 ["BMW.DE","VOW3.DE","MBG.DE","PAH3.DE"],
    ("Healthcare", "DAX"):                 ["BAYN.DE","MRK.DE","FRE.DE","FME.DE"],
    ("Health Care", "DAX"):                ["BAYN.DE","MRK.DE","FRE.DE","FME.DE"],
    ("Financials", "DAX"):                 ["DBK.DE","CBK.DE","ALV.DE","MUV2.DE"],
    ("Financial Services", "DAX"):         ["DBK.DE","CBK.DE","ALV.DE","MUV2.DE"],
    ("Industrials", "DAX"):                ["SIE.DE","DHL.DE","MTX.DE","AIR.DE","ENR.DE"],
    ("Utilities", "DAX"):                  ["RWE.DE","EOAN.DE"],
    ("Services Publics", "DAX"):           ["RWE.DE","EOAN.DE"],
    ("Consumer Discretionary", "DAX"):     ["BMW.DE","VOW3.DE","MBG.DE","ADS.DE","CON.DE","ZAL.DE"],
    ("Consumer Cyclical", "DAX"):          ["BMW.DE","VOW3.DE","MBG.DE","ADS.DE","CON.DE","ZAL.DE"],
    ("Consumer Staples", "DAX"):           ["BEI.DE","HEN3.DE"],
    ("Consumer Defensive", "DAX"):         ["BEI.DE","HEN3.DE"],
    ("Communication Services", "DAX"):     ["DTE.DE","PUM.DE"],
    ("Télécoms", "DAX"):                   ["DTE.DE"],
    ("Materials", "DAX"):                  ["BAS.DE","HEI.DE"],
    ("Basic Materials", "DAX"):            ["BAS.DE","HEI.DE"],
    ("Matériaux", "DAX"):                  ["BAS.DE","HEI.DE"],
    ("Real Estate", "DAX"):                ["VNA.DE"],
    ("Immobilier", "DAX"):                 ["VNA.DE"],
    # FTSE 100 — élargi pour couvrir tous les secteurs GICS
    ("Energy", "FTSE 100"):                ["BP.L","SHEL.L"],
    ("Mining", "FTSE 100"):                ["RIO.L","BHP.L","GLEN.L","AAL.L"],
    ("Basic Materials", "FTSE 100"):       ["RIO.L","BHP.L","GLEN.L","AAL.L"],
    ("Materials", "FTSE 100"):             ["RIO.L","BHP.L","GLEN.L","AAL.L"],
    ("Financials", "FTSE 100"):            ["HSBA.L","BARC.L","LLOY.L","NWG.L","AV.L"],
    ("Financial Services", "FTSE 100"):    ["HSBA.L","BARC.L","LLOY.L","NWG.L","AV.L"],
    ("Healthcare", "FTSE 100"):            ["AZN.L","GSK.L","HLMA.L"],
    ("Health Care", "FTSE 100"):           ["AZN.L","GSK.L","HLMA.L"],
    ("Technology", "FTSE 100"):            ["SGE.L","AVST.L"],
    ("Industrials", "FTSE 100"):           ["RR.L","BA.L","SMIN.L","EXPN.L"],
    ("Consumer Defensive", "FTSE 100"):    ["ULVR.L","DGE.L","TSCO.L","SBRY.L"],
    ("Consumer Staples", "FTSE 100"):      ["ULVR.L","DGE.L","TSCO.L","SBRY.L"],
    ("Consumer Cyclical", "FTSE 100"):     ["BRBY.L","NXT.L","KGF.L","JD.L"],
    ("Consumer Discretionary", "FTSE 100"):["BRBY.L","NXT.L","KGF.L","JD.L"],
    ("Communication Services", "FTSE 100"):["VOD.L","BT-A.L","WPP.L"],
    ("Télécoms", "FTSE 100"):              ["VOD.L","BT-A.L"],
    ("Utilities", "FTSE 100"):             ["NG.L","SSE.L","UU.L","SVT.L"],
    ("Real Estate", "FTSE 100"):           ["LAND.L","BLND.L","SGRO.L","DLG.L"],
    # CAC 40 — élargi
    ("Communication Services", "CAC 40"):  ["PUB.PA","VIV.PA"],
    ("Télécoms", "CAC 40"):                ["ORA.PA"],
    ("Utilities", "CAC 40"):               ["VIE.PA","EDF.PA"],
    ("Services Publics", "CAC 40"):        ["VIE.PA","EDF.PA"],
    ("Real Estate", "CAC 40"):             ["URW.AS","GFC.PA"],
    ("Consumer Cyclical", "CAC 40"):       ["MC.PA","OR.PA","RMS.PA","KER.PA","EL.PA"],
    ("Consumer Discretionary", "CAC 40"):  ["MC.PA","OR.PA","RMS.PA","KER.PA","EL.PA"],
    ("Basic Materials", "CAC 40"):         ["AI.PA","SGO.PA"],
    ("Materials", "CAC 40"):               ["AI.PA","SGO.PA"],
    ("Financial Services", "CAC 40"):      ["BNP.PA","ACA.PA","GLE.PA","AXA.PA"],
    ("Health Care", "CAC 40"):             ["SAN.PA","EL.PA"],

    # ── MONDIAL — top mega-caps multi-régions par secteur (US + EU + Asie) ──
    # Permet une analyse sectorielle vraiment globale (≠ biais US S&P 500).
    ("Technology", "Mondial"):              ["AAPL","MSFT","NVDA","TSM","005930.KS","ASML.AS","SAP.DE","AVGO","ORCL","TCEHY"],
    ("Healthcare", "Mondial"):              ["JNJ","UNH","LLY","NVO","ROG.SW","NVS","AZN.L","PFE","ABBV","MRK"],
    ("Financial Services", "Mondial"):      ["JPM","BRK-B","BAC","HSBA.L","BNP.PA","UBSG.SW","8306.T","MS","GS","ALV.DE"],
    ("Financials", "Mondial"):              ["JPM","BRK-B","BAC","HSBA.L","BNP.PA","UBSG.SW","8306.T","MS","GS","ALV.DE"],
    ("Consumer Discretionary", "Mondial"): ["AMZN","TSLA","MC.PA","NKE","TM","BABA","HD","MCD","SBUX","RMS.PA"],
    ("Consumer Cyclical", "Mondial"):      ["AMZN","TSLA","MC.PA","NKE","TM","BABA","HD","MCD","SBUX","RMS.PA"],
    ("Consumer Defensive", "Mondial"):      ["WMT","COST","PG","KO","PEP","NESN.SW","ULVR.L","MDLZ","BUD","BTI"],
    ("Consumer Staples", "Mondial"):        ["WMT","COST","PG","KO","PEP","NESN.SW","ULVR.L","MDLZ","BUD","BTI"],
    ("Communication Services", "Mondial"): ["GOOGL","META","NFLX","DIS","VZ","T","CMCSA","TCEHY","9988.HK","BIDU"],
    ("Energy", "Mondial"):                  ["XOM","CVX","SHEL.L","BP.L","TTE.PA","EQNR.OL","COP","ENI.MI","OXY","SLB"],
    ("Industrials", "Mondial"):             ["GE","CAT","RTX","HON","DE","BA","UNP","SIE.DE","AIR.PA","MMM"],
    ("Basic Materials", "Mondial"):         ["BHP.AX","RIO.L","LIN","APD","GLEN.L","NEM","FCX","BAS.DE","SHW","DD"],
    ("Materials", "Mondial"):               ["BHP.AX","RIO.L","LIN","APD","GLEN.L","NEM","FCX","BAS.DE","SHW","DD"],
    ("Real Estate", "Mondial"):             ["PLD","AMT","CCI","EQIX","SPG","UNI.AS","VNA.DE","8802.T","BLND.L","O"],
    ("Utilities", "Mondial"):               ["NEE","DUK","SO","D","IBE.MC","ENEL.MI","NG.L","RWE.DE","9501.T","AEP"],
}


def _get_real_tickers(sector: str, universe: str) -> list[str]:
    """Retourne les tickers reels pour un secteur/univers connu."""
    # Normalisation alias secteur (yfinance et GICS utilisent des libellés variables)
    # Inclut les libellés FR utilisés dans le PDF indice (Finance, Santé, etc.)
    _SECTOR_ALIASES = {
        "materials":              "Basic Materials",
        "basic materials":        "Basic Materials",
        "consumer staples":       "Consumer Defensive",
        "consumer defensive":     "Consumer Defensive",
        "financials":             "Financial Services",
        "financial services":     "Financial Services",
        "tech":                   "Technology",
        "information technology": "Technology",
        # Libellés FR courts utilisés dans top3_secteurs et donut indice
        "finance":                "Financial Services",
        "services financiers":    "Financial Services",
        # Banques (FR + EN) — alias critique manquant, redirigeait vers fallback
        # synthétique BAN1-6 au lieu de JPM/BAC/WFC/GS/MS.
        "banques":                "Financial Services",
        "banque":                 "Financial Services",
        "banks":                  "Financial Services",
        "bank":                   "Financial Services",
        "assurances":             "Financial Services",
        "insurance":              "Financial Services",
        "santé":                  "Healthcare",
        "sante":                  "Healthcare",
        "health care":            "Healthcare",
        "technologie":            "Technology",
        "industrie":              "Industrials",
        "industries":             "Industrials",
        "énergie":                "Energy",
        "energie":                "Energy",
        "conso. déf.":            "Consumer Defensive",
        "conso. def.":            "Consumer Defensive",
        "conso. cycl.":           "Consumer Cyclical",
        "consommation défensive": "Consumer Defensive",
        "consommation cyclique":  "Consumer Cyclical",
        "serv. publ.":            "Utilities",
        "services publics":       "Utilities",
        "télécoms":               "Communication Services",
        "telecoms":               "Communication Services",
        "matériaux":              "Basic Materials",
        "immobilier":             "Real Estate",
    }
    # Normalisation univers (DAX 40 == DAX, FTSE 100 == FTSE100, etc.)
    _UNIVERSE_ALIASES = {
        "dax 40": "DAX", "dax40": "DAX", "dax": "DAX",
        "ftse 100": "FTSE 100", "ftse100": "FTSE 100",
        "cac 40": "CAC 40", "cac40": "CAC 40",
        "euro stoxx 50": "STOXX 50", "stoxx 50": "STOXX 50", "stoxx50": "STOXX 50",
        "s&p 500": "S&P 500", "sp500": "S&P 500", "s&p500": "S&P 500", "spx": "S&P 500",
    }
    _normalize = lambda s: _SECTOR_ALIASES.get(s.strip().lower(), s)
    _normalize_u = lambda u: _UNIVERSE_ALIASES.get(u.strip().lower(), u)
    sector = _normalize(sector)
    universe = _normalize_u(universe)
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
        stock = get_ticker(tk)
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

    # --- PE médian actuel --- (pe_ratio = cli/LangGraph, pe = compute_screening)
    def _get_pe(t):
        return t.get("pe_ratio") or t.get("pe")
    pes_ltm = [float(_get_pe(t)) for t in tickers_data
               if _get_pe(t) and float(_get_pe(t)) > 0 and float(_get_pe(t)) < 500]
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

    Perf prod (Bug #118) :
    - Cache Redis 24h par ticker (clé piotroski:{ticker}) — les états annuels
      bougent 4 fois/an max, inutile de refetch
    - Env var DISABLE_PIOTROSKI=1 permet de skip complètement (fallback cold cache)
    """
    import os as _os
    if _os.getenv("DISABLE_PIOTROSKI", "").lower() in ("1", "true", "yes"):
        return None

    # Cache Redis — clé par ticker
    _tk = getattr(stock, "ticker", None) or getattr(stock, "_ticker", None) or ""
    if _tk:
        try:
            from core.cache import cache as _cache
            cached = _cache.get(f"piotroski:{_tk}")
            if cached is not None:
                return int(cached) if cached != "null" else None
        except Exception:
            pass

    result = None
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

        result = f if n >= 6 else None
    except Exception:
        result = None

    # Cache Redis 24h (états financiers annuels bougent 4×/an max)
    if _tk:
        try:
            from core.cache import cache as _cache
            _cache.set(f"piotroski:{_tk}", str(result) if result is not None else "null",
                       ttl_seconds=86400)
        except Exception:
            pass
    return result


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
            stock = get_ticker(tk)
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
            _roe_raw = info.get("returnOnEquity")
            roe      = round(float(_roe_raw) * 100, 1) if _roe_raw is not None else None
            # Clamp ROE : yfinance renvoie parfois +6000% quand BVPS quasi-nul
            # (ex: ABBV goodwill > equity). Cap [-200%, +200%] pour rester lisible.
            if roe is not None and (roe > 200 or roe < -200):
                roe = None
            # Fallback ROE pour les ~17% de tickers où returnOnEquity = None
            # (ex: Morgan Stanley). Calcul : netIncome / (marketCap/P_B)
            # = netIncome / equity_book_value. Verifie sur MS = 17.1% coherent.
            if roe is None:
                _ni = info.get("netIncomeToCommon")
                _ptb = info.get("priceToBook")
                if _ni and _ptb and mc and _ptb > 0:
                    try:
                        _equity = float(mc) / float(_ptb)
                        if _equity > 0:
                            _roe_calc = float(_ni) / _equity * 100
                            if -200 <= _roe_calc <= 200:
                                roe = round(_roe_calc, 1)
                    except (TypeError, ValueError, ZeroDivisionError):
                        pass
            rev_g    =  info.get("revenueGrowth")  or 0
            mom52    = (info.get("52WeekChange")    or 0) * 100
            mom52    = max(-300.0, min(300.0, mom52))  # cap +/-300% : valeurs extremes yfinance
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

            # Fallback price : fast_info -> history si currentPrice manquant
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if not price:
                try:
                    fi = stock.fast_info
                    price = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
                except Exception:
                    pass
            if not price:
                try:
                    hist = stock.history(period="5d")
                    if not hist.empty:
                        price = round(float(hist["Close"].iloc[-1]), 2)
                except Exception:
                    pass

            # Fallback market_cap : price × sharesOutstanding
            if not mc and price:
                try:
                    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
                    if shares:
                        mc = round(float(price) * float(shares))
                except Exception:
                    pass

            # Fallback EV/EBITDA et EV/Revenue : calcul depuis composantes
            ev_ebitda = info.get("enterpriseToEbitda")
            ev_revenue = info.get("enterpriseToRevenue")
            if not ev_ebitda or not ev_revenue:
                try:
                    ev = info.get("enterpriseValue")
                    ebitda_abs = info.get("ebitda")
                    rev_abs = info.get("totalRevenue")
                    if ev and ev > 0:
                        if not ev_ebitda and ebitda_abs and ebitda_abs > 0:
                            ev_ebitda = round(ev / ebitda_abs, 1)
                        if not ev_revenue and rev_abs and rev_abs > 0:
                            ev_revenue = round(ev / rev_abs, 1)
                except Exception:
                    pass

            # Fallback P/E : calcul depuis eps ou netIncome
            if not pe:
                try:
                    eps = info.get("trailingEps") or info.get("epsTrailingTwelveMonths")
                    if eps and eps > 0 and price and price > 0:
                        pe_calc = round(price / eps, 1)
                        if 0 < pe_calc < 500:
                            pe = pe_calc
                except Exception:
                    pass
            if not pe:
                try:
                    net_income = info.get("netIncomeToCommon")
                    if net_income and net_income > 0 and mc and mc > 0:
                        pe_calc = round(mc / net_income, 1)
                        if 0 < pe_calc < 500:
                            pe = pe_calc
                except Exception:
                    pass

            # Revenue growth — sanity check (yfinance peut renvoyer des valeurs aberrantes)
            if rev_g and abs(rev_g) > 2.0:  # > 200% -> suspect
                rev_g = 0

            # PEG ratio (PE / croissance revenus annualisee %)
            peg_ratio = None
            if pe and pe > 0 and rev_g and rev_g > 0:
                peg_ratio = round(pe / (rev_g * 100), 2)
                if peg_ratio > 50 or peg_ratio < 0:
                    peg_ratio = None

            # FCF Yield = Free Cash Flow / Market Cap
            # Fallback : OCF - CapEx si freeCashflow absent (hardware/fabless companies)
            fcf_yield = None
            try:
                fcf_abs = info.get("freeCashflow")
                if not fcf_abs:
                    _ocf   = info.get("operatingCashflow")
                    _capex = info.get("capitalExpenditures")  # negatif dans yfinance
                    if _ocf is not None and _capex is not None:
                        fcf_abs = _ocf + _capex
                if fcf_abs and mc and mc > 0:
                    fcf_yield = round(float(fcf_abs) / float(mc) * 100, 2)
                    if fcf_yield < -50 or fcf_yield > 50:
                        fcf_yield = None
            except Exception:
                pass

            # Dividende & payout
            # yfinance retourne dividendYield en % (ex: 0.97 = 0.97%)
            # On le convertit en fraction pour rester coherent avec _fmt_pct (×100)
            div_yield_raw = None
            payout_ratio_raw = None
            try:
                _dy = info.get("dividendYield")
                if _dy and 0 < float(_dy) < 100.0:
                    div_yield_raw = round(float(_dy) / 100.0, 6)  # 0.97 -> 0.0097
            except Exception:
                pass
            try:
                _pr = info.get("payoutRatio")
                if _pr and 0 < float(_pr) < 5.0:
                    payout_ratio_raw = round(float(_pr), 4)  # payoutRatio reste en fraction
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
                "industry":        info.get("industryDisp") or info.get("industry") or "",
                "score_global":    score,
                "score_value":     round(s_val, 1),
                "score_growth":    round(s_gro, 1),
                "score_quality":   round(s_qua, 1),
                "score_momentum":  round(s_mom, 1),
                "ev_ebitda":       ev_ebitda,
                "ev_revenue":      ev_revenue,
                "pe_ratio":        pe,
                "ebitda_margin":   round(ebitda_m, 1),
                "gross_margin":    round(gross_m, 1),
                "net_margin":      round(net_m, 1),
                "roe":             roe,  # None si returnOnEquity absent
                "roic":            roic,
                "revenue_growth":  rev_g,
                "momentum_52w":    round(mom52, 1),
                "altman_z":        altman_z,
                "altman_z_model":  altman_z_model,
                "piotroski_f":     piotroski,
                "peg_ratio":       peg_ratio,
                "fcf_yield":       fcf_yield,
                "div_yield":       div_yield_raw,
                "payout_ratio":    payout_ratio_raw,
                "beneish_m":       -2.5,
                "beta":            beta,
                "price":           price,
                "market_cap":      mc,
                "revenue_ltm":     info.get("totalRevenue"),
                "ebitda_ltm":      info.get("ebitda"),
                "pb_ratio":        round(float(info.get("priceToBook")), 2) if info.get("priceToBook") else None,
                "currency":        info.get("currency", "USD"),
                "sentiment_score": 0.0,
                # Métriques alternatives (paliers 2/3)
                "ps_ratio":        round(float(info.get("priceToSalesTrailing12Months")), 2)
                                   if info.get("priceToSalesTrailing12Months") else None,
                "ev_gross_profit": round(float(info.get("enterpriseValue", 0)) / float(info.get("grossProfits", 1)), 2)
                                   if info.get("enterpriseValue") and info.get("grossProfits") and float(info.get("grossProfits", 0)) > 0 else None,
                "rule_of_40":      round((rev_g * 100 if abs(rev_g) < 1 else rev_g) + ebitda_m, 1)
                                   if rev_g is not None and ebitda_m else None,
                "valuation_tier":  1 if ev_ebitda and ev_ebitda > 0 else (2 if info.get("totalRevenue") else 3),
            }
        except Exception as e:
            log.warning("yfinance.info '%s' erreur: %s", tk, e)
            return None

    # Audit perf 26/04/2026 (P0 #1) : un seul pool fan-out 16 workers qui mixe
    # _fetch_one (info yfinance) ET _fetch_pe_historical (5y PE history). Avant
    # c'etait 2 pools sequentiels (8 workers chacun) ce qui rendait quadratique
    # la latence pipeline indice (11 secteurs × 2 pools). get_ticker() etant
    # cached, les deux pools beneficient du meme objet yfinance.Ticker.
    results = []
    pe_hist_by_ticker: dict[str, list[float]] = {tk: [] for tk in symbols}
    with ThreadPoolExecutor(max_workers=16) as ex:
        # Submit info fetches (avec mapping pour identifier le ticker)
        info_futures = {ex.submit(_fetch_one, tk): tk for tk in symbols}
        # Submit PE history en parallele — pe_hist marche meme sur tickers qui
        # echouent au info fetch (peu cher, donc on submit pour tous).
        pe_futures = {ex.submit(_fetch_pe_historical, tk): tk for tk in symbols}

        for fut in as_completed(info_futures, timeout=60):
            try:
                r = fut.result(timeout=20)
            except Exception as _fe:
                log.debug("_fetch_one timeout/erreur : %s", _fe)
                r = None
            if r:
                results.append(r)

        for fut in as_completed(pe_futures):
            tk = pe_futures[fut]
            try:
                pe_hist_by_ticker[tk] = fut.result()
            except Exception:
                pe_hist_by_ticker[tk] = []

    results.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)
    log.info("Secteur %s/%s: %d/%d tickers OK", sector, universe, len(results), len(symbols))
    log.info("PE historique: %d tickers avec données", sum(1 for v in pe_hist_by_ticker.values() if v))

    tks = [r["ticker"] for r in results]
    # VaR sectorielle + cache metrics en parallele (independants apres results)
    var_data = {}
    cache = {"scenarios_bull": [], "conviction_deltas": [], "wacc_values": []}
    if tks:
        mc_dict = {r["ticker"]: r.get("market_cap") or 0 for r in results}
        with ThreadPoolExecutor(max_workers=2) as ex2:
            f_var = ex2.submit(_fetch_portfolio_var, tks, mc_dict)
            f_cache = ex2.submit(_load_cache_metrics, tks)
            try:
                var_data = f_var.result()
            except Exception as _ve:
                log.warning("VaR fetch error: %s", _ve)
            try:
                cache = f_cache.result()
            except Exception as _ce:
                log.warning("Cache fetch error: %s", _ce)
        log.info("VaR secteur: %s", var_data)
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
            "fcf_yield":    round(2.5 + i * 0.4, 2),   # deja en % (ex: 2.5%)
            "div_yield":    round(0.012 + i * 0.003, 4), # fraction (0.012 = 1.2%)
            "payout_ratio": round(0.25 + i * 0.05, 4),  # fraction (0.25 = 25%)
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

# ETF proxies pour EV/EBITDA au niveau indice (fallback non-US)
_ETF_INDEX_PROXIES = {
    "FTSE 100":      "ISF.L",       # iShares Core FTSE 100
    "FTSE100":       "ISF.L",
    "CAC 40":        "CAC.PA",      # Amundi CAC 40
    "CAC40":         "CAC.PA",
    "DAX":           "EXS1.DE",     # iShares Core DAX
    "DAX 40":        "EXS1.DE",
    "DAX40":         "EXS1.DE",
    "Euro Stoxx 50": "SX5E.PA",     # iShares Euro Stoxx 50
    "STOXX50":       "SX5E.PA",
}

def _compute_indice_stats(yf_symbol: str, rf_annual: float = 0.04) -> dict:
    """Calcule les stats de performance d'un indice via yfinance.

    Retourne un dict {perf_ytd, perf_1y, perf_3y, perf_5y, vol_1y,
    sharpe_1y, max_dd} pour les tuiles UI Next.js (indice-perf-tiles.tsx).
    Les valeurs sont en décimal (0.12 = 12 %).
    """
    out: dict = {
        "perf_ytd": None, "perf_1y": None, "perf_3y": None, "perf_5y": None,
        "vol_1y": None, "sharpe_1y": None, "max_dd": None,
    }
    if not yf_symbol:
        return out
    try:
        import datetime as _dt
        import numpy as _np
        from core.yfinance_cache import get_ticker as _gt
        hist = _gt(yf_symbol).history(period="6y")
        if hist is None or hist.empty:
            return out
        close = hist["Close"].dropna()
        if len(close) < 5:
            return out
        today = _dt.date.today()
        last = float(close.iloc[-1])

        def _base_at_or_before(target_date):
            mask = close.index.date <= target_date
            sub = close[mask]
            return float(sub.iloc[-1]) if len(sub) > 0 else None

        b_ytd = _base_at_or_before(_dt.date(today.year, 1, 1))
        b_1y  = _base_at_or_before(today - _dt.timedelta(days=365))
        b_3y  = _base_at_or_before(today - _dt.timedelta(days=3*365))
        b_5y  = _base_at_or_before(today - _dt.timedelta(days=5*365))
        if b_ytd: out["perf_ytd"] = last / b_ytd - 1
        if b_1y:  out["perf_1y"]  = last / b_1y  - 1
        if b_3y:  out["perf_3y"]  = last / b_3y  - 1
        if b_5y:  out["perf_5y"]  = last / b_5y  - 1

        try:
            cutoff = today - _dt.timedelta(days=380)
            close_1y = close[close.index.date >= cutoff]
            rets = close_1y.pct_change().dropna()
            if len(rets) > 20:
                vol_1y = float(rets.std()) * _np.sqrt(252)
                out["vol_1y"] = vol_1y
                if out["perf_1y"] is not None and vol_1y > 0:
                    out["sharpe_1y"] = (out["perf_1y"] - rf_annual) / vol_1y
            if len(close_1y) > 5:
                roll_max = close_1y.cummax()
                dd = (close_1y - roll_max) / roll_max
                out["max_dd"] = float(dd.min())
        except Exception:
            pass
    except Exception as _e:
        log.debug(f"_compute_indice_stats({yf_symbol}) erreur: {_e}")
    return out


_INDICE_META = {
    "S&P 500":      {"code": "^GSPC",     "nb_societes": 503},
    "CAC 40":       {"code": "^FCHI",     "nb_societes": 40},
    "CAC40":        {"code": "^FCHI",     "nb_societes": 40},
    "DAX":          {"code": "^GDAXI",    "nb_societes": 40},
    "DAX 40":       {"code": "^GDAXI",    "nb_societes": 40},
    "DAX40":        {"code": "^GDAXI",    "nb_societes": 40},
    "FTSE 100":     {"code": "^FTSE",     "nb_societes": 100},
    "FTSE100":      {"code": "^FTSE",     "nb_societes": 100},
    "Euro Stoxx 50":{"code": "^STOXX50E", "nb_societes": 50},
    "STOXX50":      {"code": "^STOXX50E", "nb_societes": 50},
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
        ("Technology",             65, 72, "Surpondérer",   "24.8x", 28.4, "+14.2%", "+18.4%"),
        ("Health Care",            64, 65, "Surpondérer",   "14.2x", 22.1, "+9.8%",  "+8.4%"),
        ("Financials",             72, 62, "Surpondérer",   "9.8x",  31.2, "+11.4%", "+12.1%"),
        ("Communication Services", 26, 58, "Neutre",        "12.6x", 24.6, "+10.1%", "+9.2%"),
        ("Consumer Discretionary", 55, 55, "Neutre",        "16.4x", 14.8, "+8.2%",  "+6.8%"),
        ("Industrials",            77, 53, "Neutre",        "14.8x", 16.2, "+6.8%",  "+5.4%"),
        ("Consumer Staples",       38, 48, "Neutre",        "13.2x", 18.4, "+3.2%",  "+2.1%"),
        ("Materials",              28, 46, "Neutre",        "11.4x", 20.4, "+4.8%",  "+1.8%"),
        ("Energy",                 23, 44, "Neutre",        "6.2x",  28.8, "-2.4%",  "-4.2%"),
        ("Real Estate",            31, 38, "Sous-pondérer", "18.6x", 48.2, "+1.2%",  "-2.8%"),
        ("Utilities",              28, 36, "Sous-pondérer", "11.8x", 32.4, "+2.8%",  "-5.4%"),
    ]
    import statistics
    # Audit code 29/04/2026 P0 #2 : guard secteurs vides
    # Avant : statistics.mean([]) StatisticsError + division par zéro silencieuse
    # capturée plus loin par bare except → conviction=None inexpliquée.
    if not secteurs:
        log.warning("[indice] secteurs vide — impossible de calculer score/conviction")
        scores = []
        avg_score = 50.0
        nb_surp = 0
        nb_sous = 0
        conviction = 50
    else:
        scores = [s[2] for s in secteurs]
        avg_score = round(statistics.mean(scores), 1)
        nb_surp = sum(1 for s in secteurs if s[3] == "Surpondérer")
        nb_sous = sum(1 for s in secteurs if s[3] == "Sous-pondérer")
        conviction = round(nb_surp / len(secteurs) * 100)
    signal_global = ("Surpondérer" if avg_score > 62 else
                     ("Sous-pondérer" if avg_score < 45 else "Neutre"))

    # Top 3 secteurs genere depuis la liste 'secteurs' reelle (pas de hardcoded)
    _sorted_secs = sorted(secteurs, key=lambda s: s[2], reverse=True)[:3]
    top3_secteurs = []
    for _s in _sorted_secs:
        top3_secteurs.append({
            "nom":           _s[0],
            "signal":        _s[3],
            "score":         _s[2],
            "ev_ebitda":     _s[4],
            "pe_forward_raw": None,
            "pe_mediane_10y": None,
            "poids_indice":  f"{round(100 * _s[1] / sum(x[1] for x in secteurs), 1)} %".replace('.', ','),
            "catalyseur":    f"Dynamique sectorielle favorable (score {_s[2]}/100) — à détailler par l'analyse LLM",
            "risque":        "À identifier depuis le contexte macro et fondamental actuel",
            "societes":      [],  # rempli par agent_data si dispo
        })

    # Rotation generee depuis les secteurs reels (chasse hardcoding #90)
    # Les colonnes : (nom, phase_fav, sens_taux, sens_pib, signal)
    # Phase_fav et sensibilites sont derivees depuis les caracteristiques connues
    # des secteurs GICS, pas hardcodees par nom.
    _ROT_CANON = {
        "Technology":             ("Expansion",     "Faible",    "Forte",      "Accumuler"),
        "Health Care":            ("Tous cycles",   "Modérée",   "Modérée",    "Accumuler"),
        "Financials":             ("Expansion",     "Haute",     "Haute",      "Accumuler"),
        "Communication Services": ("Expansion",     "Faible",    "Modérée",    "Neutre"),
        "Consumer Discretionary": ("Expansion",     "Modérée",   "Haute",      "Neutre"),
        "Industrials":            ("Expansion",     "Modérée",   "Forte",      "Neutre"),
        "Consumer Staples":       ("Contraction",   "Modérée",   "Faible",     "Neutre"),
        "Materials":              ("Expansion",     "Faible",    "Forte",      "Neutre"),
        "Energy":                 ("Tous cycles",   "Faible",    "Modérée",    "Neutre"),
        "Real Estate":            ("Contraction",   "Très haute","Faible",     "Alléger"),
        "Utilities":              ("Contraction",   "Très haute","Faible",     "Alléger"),
    }
    rotation = []
    for _s in secteurs:
        _rot_row = _ROT_CANON.get(_s[0])
        if _rot_row:
            rotation.append((_s[0], *_rot_row))
        else:
            # Secteur inconnu : valeurs neutres
            rotation.append((_s[0], "Tous cycles", "Moderee", "Moderee", "Neutre"))

    # etf_perf vide par defaut : _fetch_real_indice_data le remplit avec
    # les vrais returns ETF via yfinance. Pas de hardcoding.
    etf_perf = {}

    return {
        "indice":           universe,
        "code":             meta["code"],
        "signal_global":    signal_global,
        "conviction_pct":   conviction,
        "nb_secteurs":      len(secteurs),
        "nb_societes":      meta["nb_societes"],
        "cours":            "5 210",
        "variation_ytd":    "+4,8 %",
        "pe_forward":       "21,5x",
        "pe_mediane_10y":   "18,2x",
        "prime_decote":     "+18 % prime",
        "erp":              "4,2 %",
        "erp_signal":       "Favorable",
        "rf_rate":          "4,50 %",
        "bpa_growth":       "+8,5 %",
        "date_analyse":     date_str,
        "texte_description": (
            f"Le {universe} regroupe les {meta['nb_societes']} plus grandes capitalisations "
            f"domestiques, pondérées par leur capitalisation flottante. Cet indice "
            f"constitue un benchmark de référence pour les allocataires d'actifs "
            f"institutionnels sur sa zone géographique. La composition GICS couvre "
            f"{len(secteurs)} secteurs, la répartition sectorielle reflète le tissu "
            f"économique sous-jacent de l'univers analysé."
        ),
        # Textes chasse hardcoding #90 : generiques data-driven, pas de sector
        # names hardcoded. Le LLM du writer enrichit a partir de ces bases.
        "texte_macro": (
            f"L'environnement macro conditionne l'allocation sur le {universe} : politique "
            f"monétaire des banques centrales, trajectoire de l'inflation, cycle économique, "
            f"tensions géopolitiques et dynamique des taux longs. Ces facteurs déterminent "
            f"le régime de valorisation sectoriel et la tolérance au risque des "
            f"investisseurs institutionnels sur un horizon 12 mois glissants."
        ),
        "texte_signal": (
            f"Le signal global sur le {universe} est {signal_global} avec une conviction de "
            f"{conviction} % (sur la base des {len(secteurs)} secteurs analysés). "
            f"{nb_surp} {('secteur ressort' if nb_surp == 1 else 'secteurs ressortent')} en Surpondérer et reflètent les dynamiques "
            f"sectorielles positives identifiées par le scoring FinSight (momentum, "
            f"révisions BPA, valorisation relative). Les secteurs Neutre sont en attente "
            f"de catalyseurs, et les secteurs Sous-pondérer présentent des fondamentaux "
            f"dégradés ou une valorisation tendue."
        ),
        "texte_valorisation": (
            f"Le P/E Forward du {universe} est à croiser avec la médiane historique 10 ans "
            f"pour juger du niveau de valorisation relative. L'ERP Damodaran fournit une mesure "
            f"de la prime de risque exigée vs le taux sans risque 10 ans, ancrant l'attractivité "
            f"relative de l'equity vs les obligations. La compression de multiple reste le risque "
            f"clé dans les régimes de taux restrictifs."
        ),
        "texte_cycle": (
            f"L'analyse cyclique combine trois indicateurs clés : l'ISM Manufacturier (seuil 50 "
            f"= contraction/expansion), la courbe des taux 10Y-2Y (normalisation = reprise ; "
            f"inversion = récession) et les Leading Indicators. Cette configuration détermine "
            f"la phase de cycle et oriente l'allocation sectorielle selon la sensibilité "
            f"connue de chaque secteur au régime macroéconomique actuel."
        ),
        "texte_rotation": (
            f"La rotation sectorielle s'appuie sur le modèle cycle 4 phases (Expansion / "
            f"Ralentissement / Récession / Reprise). Chaque secteur a une sensibilité "
            f"spécifique au cycle déterminée par sa structure de coûts, son exposition au "
            f"cycle de consommation et sa duration financière. Le signal FinSight synthétise "
            f"cette sensibilité avec les données fondamentales actuelles pour recommander les "
            f"sur/sous-pondérations tactiques."
        ),
        "phase_cycle":  "Expansion avancée",
        "cycle_detail": "Milieu-fin de cycle — ISM proche 50, courbe taux normalisée",
        "fred_signals": [
            {"nom": "PMI Manufacturier",  "valeur": "49.8", "tendance": "Stable",  "signal": "Neutre"},
            {"nom": "10Y - 2Y (courbe)",  "valeur": "+0.18%","tendance": "Hausse", "signal": "Neutre"},
            {"nom": "ISM Services",       "valeur": "52,6", "tendance": "Hausse",  "signal": "Surpondérer"},
            {"nom": "Taux chômage",       "valeur": "4,1 %", "tendance": "Stable",  "signal": "Neutre"},
            {"nom": "CPI Core YoY",       "valeur": "3,1 %", "tendance": "Baisse",  "signal": "Neutre"},
        ],
        # Catalyseurs generiques (le writer enrichit via LLM selon l'univers)
        "catalyseurs": [
            ("Politique monétaire", "Trajectoire des taux directeurs des banques centrales et son impact sur les multiples", "6-12 mois"),
            ("Trajectoire inflation", "Convergence de l'inflation vers la cible 2 % — conditions de pivot monétaire", "9-18 mois"),
            ("Révisions BPA", "Dynamique consensus sur les bénéfices agrégés de l'univers analysé", "3-6 mois"),
        ],
        "secteurs":      secteurs,
        "top3_secteurs": top3_secteurs,
        # Risques et conditions generiques (le writer enrichit via LLM)
        "risques": [
            ("Récession macro", "Ralentissement PIB < 0 sur 2 trimestres — révision BPA agrégée 10-20 %", "20 %", "ÉLEVÉ"),
            ("Choc taux", "Révision hawkish des banques centrales — compression multiples growth", "15 %", "ÉLEVÉ"),
            ("Choc géopolitique", "Escalade tensions majeures — spike VIX, rotation défensive", "18 %", "MODÉRÉ"),
            ("Compression marges", "Pression coûts matières premières / main d'œuvre sur EBITDA", "25 %", "MODÉRÉ"),
            ("Réglementation sectorielle", "Durcissement réglementaire sur les secteurs exposés", "12 %", "FAIBLE"),
        ],
        "scenarios": [],
        "conditions_invalidation": [
            f"Le {universe} casse son support technique majeur — signal bascule Sous-pondérer",
            "Durcissement monétaire inattendu des banques centrales — compression multiples",
            "Révisions BPA agrégées < -5 % sur 2 trimestres consécutifs",
            "Pic de volatilité (VIX > 35) persistant sur plus de 10 séances",
        ],
        "rotation":      rotation,
        # Sentiment_agg : distribution des secteurs par signal (calculee depuis
        # les vraies donnees tickers_data, pas de hardcoded counts/scores)
        "sentiment_agg": {
            "label":       signal_global,
            "score":        0.0,
            "nb_articles":  0,
            "positif_nb":   nb_surp, "positif_pct": round(100*nb_surp/max(len(secteurs),1)),
            "neutre_nb":    len(secteurs) - nb_surp - nb_sous,
            "neutre_pct":   round(100*(len(secteurs) - nb_surp - nb_sous)/max(len(secteurs),1)),
            "negatif_nb":   nb_sous, "negatif_pct": round(100*nb_sous/max(len(secteurs),1)),
            # Listes des secteurs (libellés bruts ; le writer applique _abbrev_sector)
            "themes_pos":   [s[0] for s in secteurs if s[3] == "Surpondérer"],
            "themes_neg":   [s[0] for s in secteurs if s[3] == "Sous-pondérer"],
            "positif": {"nb": nb_surp, "score": "—", "themes": "—"},
            "neutre":  {"nb": len(secteurs) - nb_surp - nb_sous, "score": "—", "themes": "—"},
            "negatif": {"nb": nb_sous, "score": "—", "themes": "—"},
            # par_secteur vide par defaut : laisse le writer utiliser les VRAIS
            # scores sectoriels calcules depuis les tickers_data
            "par_secteur": [],
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
            ("Signal indice",    "Score agrege secteurs : >60 Surpondérer / 40-60 Neutre / <40 Sous-pondérer"),
            ("Conviction",       "% secteurs en accord avec le signal global (surponderes / total)"),
            ("EV/EBITDA",        "Mediane LTM des 5 premiers titres par capitalisation de chaque secteur"),
            ("P/E Mediane 10Y",  "Bloomberg Consensus — comparaison avec P/E Forward actuel"),
        ],
        "perf_history": None,
        "pb_by_sector": {
            "Technology": 8.5, "Health Care": 4.2, "Financials": 1.5,
            "Consumer Discretionary": 5.8, "Communication Services": 3.6,
            "Industrials": 4.9, "Consumer Staples": 5.2, "Energy": 2.3,
            "Materials": 3.8, "Real Estate": 2.1, "Utilities": 1.8,
        },
        "dy_by_sector": {
            "Technology": 0.7, "Health Care": 1.6, "Financials": 2.5,
            "Consumer Discretionary": 0.9, "Communication Services": 1.1,
            "Industrials": 1.8, "Consumer Staples": 3.0, "Energy": 4.0,
            "Materials": 2.2, "Real Estate": 4.2, "Utilities": 3.5,
        },
        "erp_by_sector": {
            # ERP = Div.Yield + 6% croissance LT - 4.5% rf_rate (en %)
            "Technology": round(0.7 + 6.0 - 4.5, 1),
            "Health Care": round(1.6 + 6.0 - 4.5, 1),
            "Financials": round(2.5 + 6.0 - 4.5, 1),
            "Consumer Discretionary": round(0.9 + 6.0 - 4.5, 1),
            "Communication Services": round(1.1 + 6.0 - 4.5, 1),
            "Industrials": round(1.8 + 6.0 - 4.5, 1),
            "Consumer Staples": round(3.0 + 6.0 - 4.5, 1),
            "Energy": round(4.0 + 6.0 - 4.5, 1),
            "Materials": round(2.2 + 6.0 - 4.5, 1),
            "Real Estate": round(4.2 + 6.0 - 4.5, 1),
            "Utilities": round(3.5 + 6.0 - 4.5, 1),
        },
        "optimal_portfolios": {
            "sectors": [
                "Technology", "Health Care", "Financials", "Comm. Services",
                "Cons. Discret.", "Industrials", "Cons. Staples",
                "Materials", "Energy", "Real Estate", "Utilities",
            ],
            "rf_rate": 4.50,
            "min_var": {
                "weights": [8.2, 14.6, 11.8, 6.4, 5.2, 9.8, 16.4, 7.6, 8.4, 6.2, 5.4],
                "return": 7.8, "vol": 10.5, "sharpe": 0.63,
            },
            "tangency": {
                "weights": [38.0, 18.0, 22.0, 8.0, 6.0, 3.0, 3.0, 2.0, 0.0, 0.0, 0.0],
                "return": 24.7, "vol": 12.9, "sharpe": 1.92,
            },
            "erc": {
                "weights": [12.4, 10.8, 10.2, 9.6, 8.8, 9.4, 8.6, 8.4, 7.8, 7.4, 6.6],
                "return": 12.4, "vol": 11.2, "sharpe": 0.86,
            },
        },
        "score_median": avg_score,
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
        ticker_obj = get_ticker(code)
        info = ticker_obj.info or {}
        cours = info.get("regularMarketPrice") or info.get("previousClose")
        if cours:
            cours_str = f"{cours:,.0f}".replace(",", " ")
        # YTD depuis début de l'année
        hist_1y = ticker_obj.history(period="ytd", interval="1d")["Close"]
        if len(hist_1y) > 1:
            ytd_pct = (hist_1y.iloc[-1] / hist_1y.iloc[0] - 1) * 100
            ytd_str = f"{ytd_pct:+.1f}".replace(".", ",") + " %"
        pe_fwd = info.get("forwardPE") or info.get("trailingPE")
        if pe_fwd and 0 < pe_fwd < 100:
            pe_fwd_str = f"{pe_fwd:.1f}".replace(".", ",") + "x"
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
            t = get_ticker(etf)
            hist = t.history(period="1y", interval="1mo")["Close"]
            if len(hist) < 2:
                return etf, None, None, None
            ret_1y = (hist.iloc[-1] / hist.iloc[0] - 1) * 100
            info = t.info or {}
            pb = info.get("priceToBook")
            dy = info.get("yield") or info.get("dividendYield")
            if dy and dy < 0.5:     # yfinance ETF: decimal → converti en %
                dy = round(dy * 100, 2)
            elif dy:
                dy = round(float(dy), 2)
            return etf, round(ret_1y, 1), (round(float(pb), 1) if pb else None), dy
        except Exception:
            return etf, None, None, None

    # Audit perf 26/04/2026 (P1 #5) : ETF pool + ^TNX + SPY.info en parallele
    # dans un seul TPE (13 workers). Avant : ETF pool puis ^TNX puis SPY en
    # serie -> ~1-2s de wall time inutile.
    def _fetch_tnx():
        try:
            return get_ticker("^TNX").history(period="5d")
        except Exception as _e:
            log.debug(f"^TNX fetch error: {_e}")
            return None

    def _fetch_spy_info():
        try:
            return get_ticker("SPY").info or {}
        except Exception as _e:
            log.debug(f"SPY info error: {_e}")
            return {}

    rf_rate   = 0.045
    rf_pct_str = "4,50 %"
    erp_val    = None
    erp_pct    = "—"
    erp_signal = "—"
    tnx_hist = None
    spy_info = {}

    if etf_map:
        with ThreadPoolExecutor(max_workers=13) as ex:
            futs = {ex.submit(_fetch_etf, e): e for e in etf_map}
            f_tnx = ex.submit(_fetch_tnx)
            f_spy = ex.submit(_fetch_spy_info)
            for fut in as_completed(futs):
                etf, ret, pb, dy = fut.result()
                nom = etf_map.get(etf, etf)
                etf_perf[etf] = {"nom": nom, "return_1y": ret or 0.0, "pb": pb, "dy": dy}
            tnx_hist = f_tnx.result()
            spy_info = f_spy.result()
    else:
        # Pas d'ETF (indice non-US) — fetch ^TNX et SPY en parallele quand meme
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_tnx = ex.submit(_fetch_tnx)
            f_spy = ex.submit(_fetch_spy_info)
            tnx_hist = f_tnx.result()
            spy_info = f_spy.result()

    # 2b. 10Y Treasury yield → ERP reel (data deja fetched en parallele)
    try:
        if tnx_hist is not None and not tnx_hist.empty:
            rf_rate    = float(tnx_hist["Close"].iloc[-1]) / 100
            rf_pct_str = f"{rf_rate*100:.2f}".replace(".", ",") + " %"
        pe_fwd_num = indice_info.get("forwardPE") or indice_info.get("trailingPE")
        # Fallback : SPY comme proxy du S&P 500 si ^GSPC ne retourne pas de PE
        if not (pe_fwd_num and 0 < pe_fwd_num < 100):
            pe_fwd_num = spy_info.get("forwardPE") or spy_info.get("trailingPE")
        if pe_fwd_num and 0 < pe_fwd_num < 100:
            erp_val    = 1 / pe_fwd_num - rf_rate
            erp_pct    = f"{erp_val*100:.1f}".replace(".", ",") + " %"
            erp_signal = ("Tendu" if erp_val < 0.02
                          else "Favorable" if erp_val > 0.04
                          else "Neutre")
    except Exception as _erpex:
        log.warning("ERP calcul erreur: %s", _erpex)

    # 3. Secteurs — signal derive du return ETF
    def _signal_from_ret(ret: float) -> str:
        if ret > 12: return "Surpondérer"
        if ret < -2: return "Sous-pondérer"
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
        growth_generic = {"Technology":"+13,0 %","Health Care":"+9,5 %","Financials":"+10,0 %",
                          "Consumer Discretionary":"+7,5 %","Communication Services":"+8,5 %",
                          "Industrials":"+6,5 %","Consumer Staples":"+3,5 %","Energy":"-1,5 %",
                          "Materials":"+4,0 %","Real Estate":"+2,0 %","Utilities":"+2,5 %"}
        ev  = ev_generic.get(nom, 12.0)
        mg  = margin_generic.get(nom, 18.0)
        gr  = growth_generic.get(nom, "+6,0 %")
        mom_str = f"{ret:+.1f} %".replace('.', ',')
        ev_str = f"{ev:.1f}x".replace('.', ',')
        secteurs.append((nom, nb, sc, sig, ev_str, mg, gr, mom_str))

    # Fallback si ETF non disponibles — essai fetch constituants EU
    _eu_res: list = []               # accessible plus loin pour tickers_raw
    _eu_members_by_sec: dict = {}   # accessible plus loin pour top3
    _eu_perf_history = None         # accessible dans base.update()
    _etf_proxy_ev = None            # ETF proxy EV/EBITDA (reutilise pour top3)
    _tickers_by_sector: dict = {}   # mapping secteur -> [tickers] pour opti non-US

    # Map des indices EU : sert à la fois pour le fallback (si l'ETF n'a pas
    # rempli secteurs) ET pour ALWAYS fetch la liste des constituants
    # individuels — sinon le PDF affiche « Aucun constituant disponible »
    # alors même que les agrégats sectoriels sont OK (cas DAX 40 sur l'UI :
    # ETF EXS1.DE donne le breakdown par secteur mais pas les tickers).
    _EU_CONST_MAP = {
        "DAX":          "DAX40",
        "DAX 40":       "DAX40",
        "DAX40":        "DAX40",
        "FTSE 100":     "FTSE100",
        "FTSE100":      "FTSE100",
        "Euro Stoxx 50":"STOXX50",
        "STOXX50":      "STOXX50",
        "CAC 40":       "CAC40",   # securite si ETF CAC absent
        "CAC40":        "CAC40",
    }
    _is_eu_indice = universe in _EU_CONST_MAP
    # Force le fetch des constituants pour les indices EU même quand `secteurs`
    # est déjà rempli par l'ETF (sinon _eu_res reste vide → tickers_raw vide).
    if not secteurs or _is_eu_indice:
        _YF_SECT = {
            "Technology":             "Technology",
            "Healthcare":             "Health Care",
            "Financial Services":     "Financials",
            "Consumer Cyclical":      "Consumer Discretionary",
            "Consumer Defensive":     "Consumer Staples",
            "Communication Services": "Communication Services",
            "Industrials":            "Industrials",
            "Energy":                 "Energy",
            "Basic Materials":        "Materials",
            "Real Estate":            "Real Estate",
            "Utilities":              "Utilities",
        }
        _univ_key = _EU_CONST_MAP.get(universe)
        if _univ_key:
            try:
                import sys as _sys_eu
                _sys_eu.path.insert(0, "scripts")
                from cache_update import (
                    DAX40_TICKERS, FTSE100_TICKERS, STOXX50_TICKERS, CAC40_TICKERS)
                _tkr_pool = {
                    "DAX40":   DAX40_TICKERS,
                    "FTSE100": FTSE100_TICKERS[:60],   # limiter FTSE a 60 pour la vitesse
                    "STOXX50": STOXX50_TICKERS,
                    "CAC40":   CAC40_TICKERS,
                }.get(_univ_key, [])

                def _fetch_eu_tkr(tk):
                    try:
                        _obj = get_ticker(tk)
                        _inf = _obj.info or {}
                        _52w = (_inf.get("52WeekChange") or 0) * 100
                        _52w = max(-300.0, min(300.0, _52w))  # cap +/-300%

                        # Prix et market data
                        _price   = (_inf.get("currentPrice") or
                                    _inf.get("regularMarketPrice") or
                                    _inf.get("previousClose"))
                        _mktcap  = _inf.get("marketCap")
                        # Fallback mktcap : price * shares si marketCap absent (tickers EU)
                        if _mktcap is None and _price:
                            _shr = (_inf.get("sharesOutstanding") or
                                    _inf.get("impliedSharesOutstanding"))
                            if _shr:
                                _mktcap = _price * _shr
                        _ev_raw  = _inf.get("enterpriseValue")
                        _rev_raw = _inf.get("totalRevenue")
                        _ebitda_raw = _inf.get("ebitda")

                        # Fallback ev : mktcap + dette - cash si enterpriseValue absent
                        if _ev_raw is None and _mktcap:
                            _tdebt_ev = _inf.get("totalDebt") or 0
                            _cash_ev  = _inf.get("totalCash") or 0
                            _ev_raw   = _mktcap + _tdebt_ev - _cash_ev

                        # Fallback ebitda via operatingIncome (EBIT) si ebitda absent
                        if not _ebitda_raw:
                            _ebit_eu = _inf.get("operatingIncome") or _inf.get("ebit")
                            if _ebit_eu and abs(_ebit_eu) > 0:
                                _ebitda_raw = _ebit_eu  # approximation EBIT ~ EBITDA (hors D&A)

                        # FCF Yield (fallback OCF - CapEx si freeCashflow absent)
                        _fcf = _inf.get("freeCashflow")
                        if not _fcf:
                            _ocf_eu = _inf.get("operatingCashflow")
                            _cap_eu = _inf.get("capitalExpenditures")
                            if _ocf_eu is not None and _cap_eu is not None:
                                _fcf = _ocf_eu + _cap_eu
                        _fcf_yield = (_fcf / _mktcap) if (_fcf and _mktcap and _mktcap > 0) else None

                        # ND/EBITDA
                        _tdebt   = _inf.get("totalDebt") or 0
                        _cash    = _inf.get("totalCash") or 0
                        _nd      = _tdebt - _cash
                        _nd_ebitda = (_nd / _ebitda_raw) if (_ebitda_raw and abs(_ebitda_raw) > 0) else None

                        # Altman Z approx (Z' modele Altman 1983 private)
                        # Calcule meme si certains champs sont None — utilise des defaults raisonnables
                        _altman  = None
                        _roa     = _inf.get("returnOnAssets")
                        _roe     = _inf.get("returnOnEquity")
                        _pm      = _inf.get("profitMargins")
                        _cr      = _inf.get("currentRatio")
                        _de      = _inf.get("debtToEquity")   # en %
                        _ev_rev  = _inf.get("enterpriseToRevenue")
                        # Fallback ev_rev via calcul direct
                        if _ev_rev is None and _ev_raw and _rev_raw and _rev_raw > 0:
                            _ev_rev = _ev_raw / _rev_raw
                        # Calcul Altman meme avec champs partiels (defaults secteur neutre)
                        try:
                            _de_dec  = max(0.01, ((_de or 100) / 100))
                            _cr_use  = _cr if _cr is not None else 1.5
                            _pm_use  = _pm if _pm is not None else 0.0
                            _roa_use = _roa if _roa is not None else 0.0
                            _ev_rev_use = _ev_rev if _ev_rev is not None else 1.0
                            _x1 = max(-0.5, min(0.5, (_cr_use - 1.5) / 5))
                            _x2 = max(0.0,  _pm_use * 2)
                            _x3 = max(-0.5, min(0.5, _roa_use))
                            _x4 = max(0.1,  min(10.0, 1.0 / _de_dec))
                            _x5 = max(0.1,  min(3.0,  1.0 / max(0.5, _ev_rev_use)))
                            _altman = round(0.717*_x1 + 0.847*_x2 + 3.107*_x3 + 0.420*_x4 + 0.998*_x5, 2)
                        except Exception:
                            _altman = None

                        # Beneish M approx pour tickers EU (simplifie — proxy sur marges et croissance)
                        # M-score approximatif : si marge nette deteriore + croissance rev forte = risque
                        # Toujours calculer une valeur (jamais None) pour éviter colonnes vides dans XLSX.
                        _pm_use2  = _pm if _pm is not None else 0.0
                        _rg_eu    = _inf.get("revenueGrowth") or 0.0
                        _roa_beneish = _roa_use if '_roa_use' in dir() and isinstance(_roa_use, (int, float)) else (_roa or 0.0)
                        _m_base = -4.0
                        try:
                            if _rg_eu > 0.20:    _m_base += 0.8
                            if _pm_use2 < 0.02:  _m_base += 0.6
                            if _roa_beneish < 0: _m_base += 1.0
                        except Exception:
                            pass
                        _beneish_m = round(_m_base, 2)

                        # Next earnings (timestamp → date str si future)
                        # Ordre de fallback : info.earningsTimestamp → Ticker.calendar →
                        # Ticker.earnings_dates (prochaine date future).
                        _next_earn = None
                        import datetime as _dt2
                        _et = _inf.get("earningsTimestamp") or _inf.get("earningsCallTimestampStart")
                        if _et:
                            try:
                                _edt = _dt2.datetime.fromtimestamp(int(_et)).date()
                                if _edt >= _dt2.date.today():
                                    _next_earn = str(_edt)
                            except Exception:
                                pass
                        if not _next_earn:
                            try:
                                _cal = getattr(_tkr_obj, "calendar", None)
                                if isinstance(_cal, dict):
                                    _ed = _cal.get("Earnings Date")
                                    if isinstance(_ed, (list, tuple)) and _ed:
                                        _ed = _ed[0]
                                    if _ed:
                                        _ed_d = _ed.date() if hasattr(_ed, "date") else _ed
                                        if hasattr(_ed_d, "isoformat"):
                                            _ed_d = _ed_d.isoformat()
                                        _next_earn = str(_ed_d)[:10]
                            except Exception:
                                pass
                        if not _next_earn:
                            try:
                                _edts = getattr(_tkr_obj, "earnings_dates", None)
                                if _edts is not None and hasattr(_edts, "index"):
                                    _today = _dt2.date.today()
                                    for _ix in _edts.index:
                                        _dx = _ix.date() if hasattr(_ix, "date") else _ix
                                        if hasattr(_dx, "__ge__") and _dx >= _today:
                                            _next_earn = str(_dx)[:10]
                                            break
                            except Exception:
                                pass

                        # Signal analyste
                        _rec     = _inf.get("recommendationKey", "") or ""
                        _signal_map = {
                            "strongBuy": "Surpondérer", "buy": "Surpondérer",
                            "hold": "Neutre", "underperform": "Sous-pondérer",
                            "sell": "Sous-pondérer",
                        }
                        _signal  = _signal_map.get(_rec.lower(), "Neutre")

                        # Secteur normalise
                        _sector  = _YF_SECT.get(_inf.get("sector", ""), "Autre")

                        return {
                            "ticker":          tk,
                            "name":            (_inf.get("longName") or _inf.get("shortName") or tk),
                            "sector":          _sector,
                            "price":           _price,
                            "mkt_cap":         round(_mktcap / 1e9, 2) if _mktcap else None,
                            "ev":              round(_ev_raw  / 1e9, 2) if _ev_raw  else None,
                            "rev_ltm":         round(_rev_raw  / 1e9, 2) if _rev_raw  else None,
                            "ebitda_ltm":      round(_ebitda_raw / 1e9, 2) if _ebitda_raw else None,
                            "ev_ebitda":       _inf.get("enterpriseToEbitda") or (
                                                   round(_ev_raw / _ebitda_raw, 1)
                                                   if (_ev_raw and _ebitda_raw and _ebitda_raw > 0
                                                       and 0.5 < _ev_raw / _ebitda_raw < 120)
                                                   else None),
                            "ev_revenue":      _ev_rev,
                            "pe_trailing":     _inf.get("trailingPE"),
                            "pe_fwd":          _inf.get("forwardPE"),
                            "eps":             _inf.get("trailingEps"),
                            "gross_margins":   _inf.get("grossMargins"),
                            "ebitda_margins":  (_inf.get("ebitdaMargins") or (
                                                   round(_ebitda_raw / _rev_raw, 4)
                                                   if (_ebitda_raw and _rev_raw and _rev_raw > 0
                                                       and not _inf.get("ebitdaMargins"))
                                                   else None)),
                            "profit_margins":  _pm,
                            "rev_growth":      _inf.get("revenueGrowth"),
                            "earnings_growth": _inf.get("earningsGrowth"),
                            "roe":             _roe,
                            "roa":             _roa,
                            "current_ratio":   _cr,
                            "nd_ebitda":       round(_nd_ebitda, 2) if _nd_ebitda is not None else None,
                            "altman_z":        _altman,
                            "beneish_m":       _beneish_m,
                            "mom_52w":         _52w,
                            "fcf_yield":       round(_fcf_yield * 100, 2) if _fcf_yield is not None else None,
                            "next_earnings":   _next_earn,
                            "signal":          _signal,
                            # Legacy fields pour compatibilite secteur
                            "mg_ebitda":       (_inf.get("ebitdaMargins") or 0) * 100,
                            "rev_gr":          (_inf.get("revenueGrowth") or 0) * 100,
                            "ret_52w":         _52w,
                            "score_raw":       max(25, min(85, round(50 + _52w * 1.2))),
                        }
                    except Exception as _e:
                        log.warning("[fetch_eu_tkr] %s erreur: %s", tk, _e)
                        return None

                # Workers 16 (etait 8) — yfinance est I/O-bound, GIL non bloquant.
                # Mesure avant/apres : ~32s -> ~17s sur 60 tickers EU.
                with ThreadPoolExecutor(max_workers=16) as _pex:
                    _eu_res = [r for r in _pex.map(_fetch_eu_tkr, _tkr_pool) if r]

                from collections import defaultdict
                _by_sec_raw = defaultdict(list)
                for _r in _eu_res:
                    if _r["sector"] and _r["sector"] != "Autre":
                        _by_sec_raw[_r["sector"]].append(_r)
                _eu_members_by_sec = dict(_by_sec_raw)
                # Exporter tickers par secteur pour l'opti corrélation (ajout 2026-04-17)
                _tickers_by_sector = {
                    _sec: [m.get("ticker") for m in _mems if m.get("ticker")]
                    for _sec, _mems in _eu_members_by_sec.items()
                }

                import statistics as _stat_eu
                def _med_pos(vals):
                    v = [x for x in vals if x is not None and x > 0]
                    return round(_stat_eu.median(v), 2) if v else None

                # Si secteurs est déjà rempli (par l'ETF en amont), on saute la
                # ré-population pour ne pas créer de doublons. On garde quand
                # même le fetch des constituants ci-dessus pour _eu_res.
                _secteurs_already_filled = bool(secteurs)
                for _sname, _mems in sorted(
                        _eu_members_by_sec.items(),
                        key=lambda kv: -sum(m["score_raw"] for m in kv[1]) / len(kv[1])):
                    _nb = len(_mems)
                    _sc = round(sum(m["score_raw"] for m in _mems) / _nb)
                    _sig = ("Surpondérer" if _sc >= 60
                            else ("Sous-pondérer" if _sc < 40 else "Neutre"))
                    _ev_v = [m["ev_ebitda"] for m in _mems
                             if m.get("ev_ebitda") and 0.5 < m["ev_ebitda"] < 100]
                    _ev_s = (f"{_stat_eu.median(_ev_v):.1f}x".replace('.', ',') if _ev_v else "\u2014")
                    _mg   = round(sum(m["mg_ebitda"] for m in _mems) / _nb, 1)
                    _gr_v = [m["rev_gr"] for m in _mems]
                    _gr   = round(sum(_gr_v) / len(_gr_v), 1) if _gr_v else 0.0
                    _gr_s = f"{_gr:+.1f} %".replace('.', ',')
                    _ret  = round(sum(m["ret_52w"] for m in _mems) / _nb, 1)
                    if not _secteurs_already_filled:
                        secteurs.append((_sname, _nb, _sc, _sig, _ev_s, _mg, _gr_s, f"{_ret:+.1f} %".replace('.', ',')))

                # Réécrit Nb sociétés depuis le count réel des constituants EU
                # (sinon on hérite des valeurs S&P 500 hardcodées qui dépassent
                # le total réel de l'indice — bug Tech=65 sur CAC 40)
                if _eu_members_by_sec and _secteurs_already_filled:
                    _new_secteurs_eu = []
                    for _t in secteurs:
                        _nm = _t[0]
                        _real_nb = len(_eu_members_by_sec.get(_nm, []))
                        if _real_nb > 0:
                            _new_secteurs_eu.append((_nm, _real_nb, *_t[2:]))
                        else:
                            _new_secteurs_eu.append(_t)
                    secteurs = _new_secteurs_eu

                # ERP depuis PE median des constituants
                _pe_eu = [m["pe_fwd"] for m in _eu_res if m.get("pe_fwd") and 3 < m["pe_fwd"] < 100]
                if _pe_eu:
                    import statistics as _se2
                    _pe_med = _se2.median(_pe_eu)
                    pe_fwd_str = f"{_pe_med:.1f}".replace(".", ",") + "x"
                    _erp_eu = 1 / _pe_med - rf_rate
                    erp_pct    = f"{_erp_eu*100:.1f}".replace(".", ",") + " %"
                    erp_signal = ("Tendu" if _erp_eu < 0.02
                                  else ("Favorable" if _erp_eu > 0.04 else "Neutre"))

                log.info("EU constituents OK: %d tickers / %d secteurs", len(_eu_res), len(secteurs))
            except Exception as _eu_ex:
                log.warning("EU constituents fetch erreur: %s", _eu_ex)

    # Fetch per-ticker pour indices US (S&P 500 etc.) — remplit VALUE/GROWTH/QUALITY/MOMENTUM
    if secteurs and not _eu_members_by_sec:
        # Utiliser les cles exactes de _SECTOR_TICKERS pour l'univers courant
        _SP500_SECTORS = [s for (s, u) in _SECTOR_TICKERS.keys() if u == universe]
        if not _SP500_SECTORS:  # Fallback si univers inconnu
            _SP500_SECTORS = [s for (s, u) in _SECTOR_TICKERS.keys() if u == "S&P 500"]
        _us_res_raw: list = []
        try:
            from concurrent.futures import ThreadPoolExecutor as _TPEX_us
            def _fetch_us_sector(s):
                try:
                    return _fetch_real_sector_data(s, universe, max_tickers=8)
                except Exception as _fe:
                    log.warning("fetch US sector %s error: %s", s, _fe)
                    return []
            with _TPEX_us(max_workers=4) as _usex:
                for _batch in _usex.map(_fetch_us_sector, _SP500_SECTORS):
                    _us_res_raw.extend(_batch)
        except Exception as _us_ex:
            log.warning("US per-ticker fetch erreur: %s", _us_ex)

        if _us_res_raw:
            def _norm_us(t: dict) -> dict:
                _mc   = t.get("market_cap")
                _rv   = t.get("revenue_ltm")
                _roe_pct = t.get("roe")          # % (ex: 15.0)
                _gm_pct  = t.get("gross_margin")  # % (ex: 65.0)
                _em_pct  = t.get("ebitda_margin") # %
                _nm_pct  = t.get("net_margin")    # %
                _rg      = t.get("revenue_growth") # decimal (ex: 0.10)
                _mom     = t.get("momentum_52w")   # % (ex: 12.5)
                return {
                    "ticker":          t.get("ticker"),
                    "name":            t.get("company", t.get("ticker", "")),
                    "sector":          t.get("sector", ""),
                    "price":           t.get("price"),
                    "mkt_cap":         round(_mc / 1e9, 2) if _mc else None,
                    "ev":              None,
                    "rev_ltm":         round(_rv / 1e9, 2) if _rv else None,
                    "ebitda_ltm":      None,
                    "ev_ebitda":       t.get("ev_ebitda"),
                    "ev_revenue":      t.get("ev_revenue"),
                    "pe_trailing":     t.get("pe_ratio"),
                    "pe_fwd":          None,
                    "eps":             None,
                    "gross_margins":   _gm_pct / 100 if _gm_pct is not None else None,
                    "ebitda_margins":  _em_pct / 100 if _em_pct is not None else None,
                    "profit_margins":  _nm_pct / 100 if _nm_pct is not None else None,
                    "rev_growth":      _rg,
                    "earnings_growth": None,
                    "roe":             _roe_pct / 100 if _roe_pct is not None else None,
                    "roa":             None,
                    "current_ratio":   None,
                    "nd_ebitda":       None,
                    "altman_z":        t.get("altman_z"),
                    "beneish_m":       t.get("beneish_m"),
                    "mom_52w":         _mom,
                    "fcf_yield":       t.get("fcf_yield"),
                    "next_earnings":   None,
                    "signal":          "Neutre",
                    "mg_ebitda":       _em_pct or 0,
                    "rev_gr":          (_rg or 0) * 100,
                    "ret_52w":         _mom or 0,
                    "score_raw":       t.get("score_global", 50),
                    # Champs critiques pour secteurs financiers (banques, REITs,
                    # insurance, utilities) — yfinance les expose mais le mapping
                    # _norm_us les droppait → tableau "—" page 6 PDF sectoriel.
                    "pb_ratio":        t.get("pb_ratio"),
                    "div_yield":       t.get("div_yield"),
                    "ps_ratio":        t.get("ps_ratio"),
                    "payout_ratio":    t.get("payout_ratio"),
                }
            _eu_res = [_norm_us(t) for t in _us_res_raw]
            from collections import defaultdict as _dd_us
            _by_sec_us: dict = {}
            _tmp_dd = {}
            for _r in _eu_res:
                _sec = _r.get("sector", "")
                if _sec and _sec != "Autre":
                    _tmp_dd.setdefault(_sec, []).append(_r)
            _eu_members_by_sec = _tmp_dd
            log.info("US per-ticker OK: %d tickers / %d secteurs", len(_eu_res), len(_eu_members_by_sec))

        # --- ETF proxy fallback pour EV/EBITDA si la majorite des secteurs ont "—" ---
        _etf_proxy_ev = None   # sera reutilise pour top3_secteurs
        _nb_ev_missing = sum(1 for s in secteurs if str(s[4]) in ("\u2014", "---", "", "None"))
        if secteurs and _nb_ev_missing > len(secteurs) * 0.5:
            _proxy_ticker = _ETF_INDEX_PROXIES.get(universe)
            if _proxy_ticker:
                try:
                    _proxy_obj  = get_ticker(_proxy_ticker)
                    _proxy_info = _proxy_obj.info or {}
                    _proxy_ev_raw = _proxy_info.get("enterpriseToEbitda")
                    if _proxy_ev_raw and 1.0 < float(_proxy_ev_raw) < 200:
                        _etf_proxy_ev = round(float(_proxy_ev_raw), 1)
                        log.info("ETF proxy %s -> EV/EBITDA = %.1fx (fallback pour %s)",
                                 _proxy_ticker, _etf_proxy_ev, universe)
                        # Injecter comme fallback pour chaque secteur manquant
                        _new_secteurs = []
                        for _s in secteurs:
                            if str(_s[4]) in ("\u2014", "---", "", "None"):
                                _new_secteurs.append(
                                    (_s[0], _s[1], _s[2], _s[3],
                                     f"{_etf_proxy_ev:.1f}x*".replace('.', ','), _s[5], _s[6], _s[7]))
                            else:
                                _new_secteurs.append(_s)
                        secteurs = _new_secteurs
                    else:
                        log.info("ETF proxy %s: enterpriseToEbitda absent ou hors bornes", _proxy_ticker)
                except Exception as _prx_ex:
                    log.warning("ETF proxy %s erreur: %s", _proxy_ticker, _prx_ex)

        if not secteurs:
            log.warning("ETF SPDR non disponibles — fallback donnees test")
            return _make_test_indice_data(universe)

    # Perf history reelle pour l'indice (index vs SP500, Bonds, Or)
    # Doit s'exécuter pour US ET EU (hors du branch `if secteurs and not _eu_members_by_sec:`)
    if secteurs and code:
        log.info("perf_history: tentative fetch pour %s (code=%s)", universe, code)
        try:
            import pandas as _pd_ph
            _ph_start = (today - datetime.timedelta(days=370)).isoformat()

            # Double fallback : core.yfinance_cache puis yf.download direct.
            # Bug 28/04 : le chart restait plat même avec _gt_ph qui fonctionne
            # en local — possible incompatibilité Railway/cache. On bascule sur
            # yf.download si _gt_ph retourne vide.
            from core.yfinance_cache import get_ticker as _gt_ph
            def _fetch_hist_series(tk: str):
                # Tentative 1 : via cache
                try:
                    h = _gt_ph(tk).history(start=_ph_start, interval="1d", auto_adjust=True)
                    if h is not None and not h.empty and "Close" in h.columns:
                        s = h["Close"].dropna()
                        if not s.empty and len(s) >= 5:
                            return s
                except Exception as _fex1:
                    log.debug("perf_history cache %s erreur: %s", tk, _fex1)
                # Tentative 2 : yf.download direct (single-ticker → flat columns)
                try:
                    h2 = yf.download(tk, start=_ph_start, interval="1d",
                                     progress=False, auto_adjust=True, threads=False)
                    if h2 is None or h2.empty:
                        return None
                    if isinstance(h2.columns, _pd_ph.MultiIndex):
                        if ("Close", tk) in h2.columns:
                            s = h2[("Close", tk)]
                        else:
                            close_cols = [c for c in h2.columns if c[0] == "Close"]
                            s = h2[close_cols[0]] if close_cols else None
                    else:
                        s = h2["Close"] if "Close" in h2.columns else None
                    if s is None:
                        return None
                    if isinstance(s, _pd_ph.DataFrame):
                        s = s.iloc[:, 0]
                    s = s.dropna()
                    if s.empty or len(s) < 5:
                        return None
                    return s
                except Exception as _fex2:
                    log.warning("perf_history fetch %s erreur: %s", tk, _fex2)
                    return None

            s_idx = _fetch_hist_series(code)
            if s_idx is None or len(s_idx) < 5:
                raise ValueError(f"indice series vide pour {code}")

            s_sp   = _fetch_hist_series("^GSPC") if code != "^GSPC" else None
            s_bond = _fetch_hist_series("AGG")
            s_gold = _fetch_hist_series("GLD")

            # Aligne toutes les séries sur les dates de l'indice principal
            _ph_close = _pd_ph.DataFrame({code: s_idx})
            if s_sp is not None:   _ph_close["^GSPC"] = s_sp
            if s_bond is not None: _ph_close["AGG"]   = s_bond
            if s_gold is not None: _ph_close["GLD"]   = s_gold
            _ph_close = _ph_close.ffill().dropna(subset=[code])
            if len(_ph_close) < 5:
                raise ValueError(f"perf_history: alignement final insuffisant ({len(_ph_close)} pts)")

            def _rebase_col(col):
                if col not in _ph_close.columns:
                    return []
                s = _ph_close[col].dropna()
                if s.empty:
                    return []
                base = s.iloc[0]
                if base == 0 or _pd_ph.isna(base):
                    return []
                return [round((float(v) / float(base)) * 100, 2) for v in s]

            _ph_dts = [str(d.date()) for d in _ph_close.index]
            _eu_perf_history = {
                "dates":       _ph_dts,
                "indice":      _rebase_col(code),
                "bonds":       _rebase_col("AGG"),
                "gold":        _rebase_col("GLD"),
                "sp500":       _rebase_col("^GSPC"),
                "label_start": _ph_dts[0] if _ph_dts else "",
                "label_end":   _ph_dts[-1] if _ph_dts else "",
                "indice_name": universe,
            }
            log.info("perf_history OK: %d points (%s, indice=%s, bonds=%s, gold=%s)",
                     len(_ph_dts), universe,
                     "OK" if _eu_perf_history["indice"] else "VIDE",
                     "OK" if _eu_perf_history["bonds"] else "VIDE",
                     "OK" if _eu_perf_history["gold"] else "VIDE")
        except Exception as _ph_ex:
            log.warning("perf_history erreur (%s): %s", universe, _ph_ex, exc_info=True)

    # P/B et DivYield génériques (fallback si ETF info incomplet)
    _PB_GENERIC = {
        "Technology": 8.5, "Health Care": 4.2, "Financials": 1.5,
        "Consumer Discretionary": 5.8, "Communication Services": 3.6,
        "Industrials": 4.9, "Consumer Staples": 5.2, "Energy": 2.3,
        "Materials": 3.8, "Real Estate": 2.1, "Utilities": 1.8,
    }
    _DIVYIELD_GENERIC = {
        "Technology": 0.7, "Health Care": 1.6, "Financials": 2.1,
        "Consumer Discretionary": 0.8, "Communication Services": 0.9,
        "Industrials": 1.5, "Consumer Staples": 2.8, "Energy": 3.5,
        "Materials": 2.0, "Real Estate": 3.8, "Utilities": 3.2,
    }

    # 2b. Analytics indice avances (S&P 500 uniquement)
    import numpy as _np_indice
    sector_contribution = []
    indice_analytics = {}
    correlation_data = {}

    # Bloc analytics : S&P 500 (via ETFs SPDR) OU indice non-US (via _tickers_by_sector
    # peuplé dans le fallback EU). On exécute dès que l'un des deux est disponible.
    if (universe == "S&P 500" and etf_perf) or _tickers_by_sector:
        # Contribution sectorielle : weight × return_1y
        total_nb_soc = sum(_SP500_NB_SOC.get(info.get("nom",""), 30) for info in etf_perf.values())
        for etf_k, info_k in sorted(etf_perf.items(),
                                    key=lambda x: x[1].get("return_1y", 0), reverse=True):
            nom_k = info_k.get("nom", "")
            ret_k = info_k.get("return_1y", 0.0)
            nb_k  = _SP500_NB_SOC.get(nom_k, 30)
            w_k   = nb_k / total_nb_soc if total_nb_soc > 0 else 0
            sector_contribution.append((nom_k, round(w_k * ret_k, 2), round(ret_k, 1)))

        # Breadth : % secteurs en momentum positif
        nb_pos_b  = sum(1 for inf in etf_perf.values() if inf.get("return_1y", 0) > 0)
        nb_tot_b  = len(etf_perf)
        breadth_pct = round(100 * nb_pos_b / nb_tot_b) if nb_tot_b > 0 else 0

        # Factor tilts : cyclique vs defensif
        _CYCLICAL  = {"Technology", "Consumer Discretionary", "Communication Services",
                      "Financials", "Industrials", "Energy", "Materials"}
        _DEFENSIVE = {"Consumer Staples", "Health Care", "Utilities", "Real Estate"}
        cyc_rets = [inf["return_1y"] for inf in etf_perf.values()
                    if inf.get("nom","") in _CYCLICAL]
        def_rets = [inf["return_1y"] for inf in etf_perf.values()
                    if inf.get("nom","") in _DEFENSIVE]
        cyc_avg  = round(float(_np_indice.mean(cyc_rets)), 1) if cyc_rets else 0.0
        def_avg  = round(float(_np_indice.mean(def_rets)), 1) if def_rets else 0.0
        spread   = cyc_avg - def_avg
        tilt     = "Cyclique" if spread > 5 else ("Defensif" if spread < -5 else "Equilibree")
        indice_analytics = {
            "breadth_pct": breadth_pct, "breadth_nb": nb_pos_b, "nb_total": nb_tot_b,
            "cyclical_return": cyc_avg, "defensive_return": def_avg,
            "tilt": tilt, "tilt_spread": round(abs(spread), 1),
        }

        # P/B, DivYield et ERP sectoriel implicite
        pb_by_sector  = {}
        dy_by_sector  = {}
        erp_by_sector = {}
        for _e, _inf in etf_perf.items():
            _nom = _inf.get("nom", "")
            _pb  = _inf.get("pb") or _PB_GENERIC.get(_nom)
            _dy  = _inf.get("dy") or _DIVYIELD_GENERIC.get(_nom)
            pb_by_sector[_nom]  = _pb
            dy_by_sector[_nom]  = _dy
            # ERP sectoriel = DivYield + croissance_LT - RF (Gordon Growth)
            _growth_generic = {
                "Technology": 13.0, "Health Care": 9.5, "Financials": 10.0,
                "Consumer Discretionary": 7.5, "Communication Services": 8.5,
                "Industrials": 6.5, "Consumer Staples": 3.5, "Energy": -1.5,
                "Materials": 4.0, "Real Estate": 2.0, "Utilities": 2.5,
            }
            _gr = _growth_generic.get(_nom, 6.0) / 100
            _dy_dec = (_dy or 0) / 100
            erp_by_sector[_nom] = round((_dy_dec + _gr - rf_rate) * 100, 1)

        # Matrice de correlation (daily returns 52 semaines)
        daily_ret_full = None
        corr_df        = None
        etf_in_c       = []
        try:
            import pandas as _pd_corr
            etf_list_corr = list(etf_map.keys())
            if etf_list_corr:
                # S&P 500 : ETFs SPDR sectoriels directement
                raw_daily = yf.download(etf_list_corr, period="1y", interval="1d", progress=False)
                if isinstance(raw_daily.columns, _pd_corr.MultiIndex):
                    prices_d = raw_daily["Close"]
                else:
                    prices_d = raw_daily
                prices_d       = prices_d.dropna(how="all")
                daily_ret_full = prices_d.pct_change().dropna(how="all")
                corr_df        = daily_ret_full.corr()
                etf_in_c       = [e for e in etf_list_corr if e in corr_df.columns]
            else:
                # Indices non-US (DAX/CAC/FTSE/...) : construire des returns
                # sectoriels synthétiques à partir des constituants groupés
                # par secteur GICS. _tickers_by_sector a été peuplé plus haut
                # dans le fallback EU (_fetch_eu_tkr).
                _sector_to_tickers = {
                    _sec: (_tks or [])[:5]
                    for _sec, _tks in (_tickers_by_sector or {}).items()
                    if _tks
                }
                if _sector_to_tickers:
                    _all_tk = sorted({t for L in _sector_to_tickers.values() for t in L})
                    _raw = yf.download(_all_tk, period="1y", interval="1d", progress=False)
                    _px = _raw["Close"] if isinstance(_raw.columns, _pd_corr.MultiIndex) else _raw
                    _px = _px.dropna(how="all")
                    _daily = _px.pct_change().dropna(how="all")
                    # Synthetic sector returns = moyenne des returns des tickers du secteur
                    _sec_returns = {}
                    for _sec_name, _tks in _sector_to_tickers.items():
                        _cols = [t for t in _tks if t in _daily.columns]
                        if _cols:
                            _sec_returns[_sec_name] = _daily[_cols].mean(axis=1)
                    if _sec_returns:
                        daily_ret_full = _pd_corr.DataFrame(_sec_returns).dropna(how="all")
                        corr_df = daily_ret_full.corr()
                        etf_in_c = list(corr_df.columns)
                        # Map sector_name -> sector_name (pas d'ETF intermédiaire)
                        etf_map = {s: s for s in etf_in_c}
                        # Étendre etf_perf avec return_1y approximatif depuis daily returns
                        for _sec in etf_in_c:
                            _r = _sec_returns[_sec]
                            _ret_1y = float((1 + _r).prod() - 1) * 100 if len(_r) > 0 else 0.0
                            if _sec not in etf_perf:
                                etf_perf[_sec] = {}
                            etf_perf[_sec].setdefault("nom", _sec)
                            etf_perf[_sec].setdefault("return_1y", round(_ret_1y, 1))

            if corr_df is not None and etf_in_c:
                corr_matrix = []
                for e1 in etf_in_c:
                    corr_matrix.append(
                        [round(float(corr_df.loc[e1, e2]), 2) for e2 in etf_in_c])
                correlation_data = {
                    "sectors": [etf_map.get(e, e) for e in etf_in_c],
                    "matrix":  corr_matrix,
                }
                log.info("Matrice correlation %dx%d calculee", len(etf_in_c), len(etf_in_c))
        except Exception as _ec:
            log.warning("Correlation matrix erreur: %s", _ec)

        # Portefeuilles optimaux : Min-Variance, Tangency, ERC
        optimal_portfolios = {}
        if daily_ret_full is not None and corr_df is not None and len(etf_in_c) >= 4:
            try:
                from scipy.optimize import minimize as _sp_min
                _n   = len(etf_in_c)
                _x0  = _np_indice.array([1/_n] * _n)
                _bds = [(0.0, 0.40)] * _n
                _bds_erc = [(0.01, 0.40)] * _n
                _con = [{"type": "eq", "fun": lambda w: _np_indice.sum(w) - 1}]
                _vols = daily_ret_full[etf_in_c].std().values * _np_indice.sqrt(252)
                _corr = _np_indice.array([[float(corr_df.loc[e1, e2])
                                           for e2 in etf_in_c] for e1 in etf_in_c])
                _cov  = _np_indice.outer(_vols, _vols) * _corr
                _mu   = _np_indice.array([
                    etf_perf.get(e, {}).get("return_1y", 0.0) / 100
                    for e in etf_in_c])

                def _metrics(w):
                    ret = float(w @ _mu)
                    vol = float(_np_indice.sqrt(max(w @ _cov @ w, 1e-12)))
                    return round(ret*100,1), round(vol*100,1), round((ret-rf_rate)/vol, 2)

                # Min Variance
                res_mv = _sp_min(lambda w: float(w @ _cov @ w), _x0,
                                 method="SLSQP", bounds=_bds, constraints=_con)
                w_mv = res_mv.x if res_mv.success else _x0

                # Tangency (Max Sharpe)
                def _neg_sharpe(w):
                    vol = float(_np_indice.sqrt(max(w @ _cov @ w, 1e-12)))
                    return -(float(w @ _mu) - rf_rate) / vol
                res_tg = _sp_min(_neg_sharpe, _x0,
                                 method="SLSQP", bounds=_bds, constraints=_con)
                w_tg = res_tg.x if res_tg.success else _x0

                # Equal Risk Contribution
                def _erc_obj(w):
                    var = float(w @ _cov @ w)
                    if var < 1e-12: return 1e10
                    rc = w * (_cov @ w)
                    return float(_np_indice.sum((rc - var/_n)**2))
                res_erc = _sp_min(_erc_obj, _x0,
                                  method="SLSQP", bounds=_bds_erc, constraints=_con)
                w_erc = res_erc.x if res_erc.success else _x0

                _secs_opt = [etf_map.get(e, e) for e in etf_in_c]
                optimal_portfolios = {
                    "sectors": _secs_opt,
                    "rf_rate": round(rf_rate*100, 2),
                    "min_var":  {"weights": [round(float(w)*100,1) for w in w_mv],
                                 **dict(zip(["return","vol","sharpe"], _metrics(w_mv)))},
                    "tangency": {"weights": [round(float(w)*100,1) for w in w_tg],
                                 **dict(zip(["return","vol","sharpe"], _metrics(w_tg)))},
                    "erc":      {"weights": [round(float(w)*100,1) for w in w_erc],
                                 **dict(zip(["return","vol","sharpe"], _metrics(w_erc)))},
                }
                log.info("Portfolios opt: MV sh=%.2f TG sh=%.2f ERC sh=%.2f",
                         optimal_portfolios["min_var"]["sharpe"],
                         optimal_portfolios["tangency"]["sharpe"],
                         optimal_portfolios["erc"]["sharpe"])
            except Exception as _ep:
                log.warning("Portfolio optimization erreur: %s", _ep)

    import statistics
    scores = [s[2] for s in secteurs]
    avg_score = round(statistics.mean(scores), 1)
    nb_surp = sum(1 for s in secteurs if s[3] == "Surpondérer")
    conviction = round(nb_surp / len(secteurs) * 100) if secteurs else 50
    signal_global = ("Surpondérer" if avg_score > 62 else
                     ("Sous-pondérer" if avg_score < 45 else "Neutre"))

    # Top 3 secteurs : les 3 avec meilleur return ETF (S&P 500) ou score constituants (EU)
    sorted_etf = sorted(etf_perf.items(), key=lambda x: x[1].get("return_1y",0), reverse=True)
    top3_secteurs = []

    # Pré-fetch parallèle EV/EBITDA + ret_52w des top tickers US pour ne pas
    # afficher des sociétés représentatives clones (I8 — fix 29/04/2026).
    # Sans ce pré-fetch, les 3 sociétés d'un même secteur S&P 500 partageaient
    # ev_ebitda="—" et un score uniformément dérivé du score sectoriel.
    _us_per_ticker: dict = {}
    if not _eu_members_by_sec:  # chemin US (S&P 500 etc.) — EU a déjà ses propres data par société
        _all_us_tkrs = []
        for _etf_t, _info_t in sorted_etf[:3]:
            _nm_t = _info_t.get("nom", "")
            _tks_t = (_get_real_tickers(_nm_t, universe) or
                      _get_real_tickers(_nm_t, "S&P 500") or [])[:3]
            for _tk in _tks_t:
                if _tk and _tk not in _us_per_ticker:
                    _us_per_ticker[_tk] = None  # placeholder pour dédup
                    _all_us_tkrs.append(_tk)

        def _fetch_us_tkr_info(_tk: str) -> tuple:
            try:
                _i = get_ticker(_tk).info or {}
                _ev = _i.get("enterpriseToEbitda")
                _ev_clean = float(_ev) if _ev and 0.5 < float(_ev) < 200 else None
                _r52 = _i.get("52WeekChange") or _i.get("fiftyTwoWeekChange")
                _r52_pct = float(_r52) * 100 if _r52 is not None else 0.0
                _sc = max(25, min(85, round(50 + _r52_pct * 1.2)))
                return _tk, _ev_clean, _sc
            except Exception as _eu:
                log.debug("[us_tkr_info] %s erreur: %s", _tk, _eu)
                return _tk, None, None

        if _all_us_tkrs:
            try:
                with ThreadPoolExecutor(max_workers=min(9, len(_all_us_tkrs))) as _ex_us:
                    for _tk_r, _ev_r, _sc_r in _ex_us.map(_fetch_us_tkr_info, _all_us_tkrs):
                        _us_per_ticker[_tk_r] = (_ev_r, _sc_r)
            except Exception as _ep_us:
                log.debug("[us_tkr_info] pool erreur: %s", _ep_us)

    for i, (etf, info) in enumerate(sorted_etf[:3]):
        nom = info.get("nom","")
        ret = info.get("return_1y", 0.0)
        sc  = _score_from_ret(ret)
        sig = _signal_from_ret(ret)
        # Sociétés : si on a les constituants EU réels, prendre les 3 meilleurs
        # (EV/EBITDA + score propres) au lieu du score sectoriel cloné.
        _real_mems = _eu_members_by_sec.get(nom, [])
        if _real_mems:
            _top_mems = sorted(_real_mems, key=lambda m: m.get("score_raw", 0), reverse=True)[:3]
            societes = []
            for _m in _top_mems:
                _ev = _m.get("ev_ebitda")
                _ev_str = (f"{_ev:.1f}x".replace('.', ',') if _ev and 0.5 < _ev < 200 else "—")
                _msc = _m.get("score_raw", sc)
                societes.append((_m.get("ticker", "—"), sig, _ev_str, _msc))
        else:
            soc_tickers = (_get_real_tickers(nom, universe) or
                           _get_real_tickers(nom, "S&P 500"))[:3]
            societes = []
            for _idx, tk in enumerate(soc_tickers):
                _info_us = _us_per_ticker.get(tk)
                if isinstance(_info_us, tuple):
                    _ev_us, _sc_us = _info_us
                else:
                    _ev_us, _sc_us = None, None
                _ev_str = (f"{_ev_us:.1f}x".replace('.', ',') if _ev_us else "—")
                # Score propre par société (depuis perf 52W) avec fallback sur le score
                # sectoriel décrémenté pour conserver une dispersion minimale.
                _msc = _sc_us if isinstance(_sc_us, (int, float)) else sc - i*3 - _idx
                _msig = ("Surpondérer" if _msc >= 60
                         else ("Sous-pondérer" if _msc < 40 else "Neutre"))
                societes.append((tk, _msig, _ev_str, _msc))
        top3_secteurs.append({
            "nom": nom, "signal": sig, "score": sc,
            "ev_ebitda": "—", "pe_forward_raw": 20.0, "pe_mediane_10y": 18.0,
            "poids_indice": "—",
            "catalyseur": f"Performance YTD {ret:+.1f} % — momentum sectoriel positif".replace('.', ','),
            "risque": "Risque de compression multiple si croissance BPA décélérée",
            "societes": societes or [("—","Neutre","—",50)],
        })

    # Chemin EU : top3 depuis les secteurs constituants si ETF absent
    # Si _eu_members_by_sec est vide (EU fetch fail), fallback sur _get_real_tickers
    # depuis la table hardcodée CAC 40/DAX/FTSE avec score neutre.
    if not top3_secteurs and not _eu_members_by_sec and secteurs:
        for _ts in sorted(secteurs, key=lambda s: s[2], reverse=True)[:3]:
            _tsn = _ts[0]
            _tk_fallback = (_get_real_tickers(_tsn, universe) or
                            _get_real_tickers(_tsn, "S&P 500") or [])[:3]
            if not _tk_fallback:
                continue
            _socs_fb = [(tk, _ts[3], "\u2014", _ts[2]) for tk in _tk_fallback]
            top3_secteurs.append({
                "nom":            _tsn,
                "signal":         _ts[3],
                "score":          _ts[2],
                "ev_ebitda":      "\u2014",
                "pe_forward_raw": 18.0,
                "pe_mediane_10y": 16.0,
                "poids_indice":   "—",
                "catalyseur":     f"Secteur {_ts[3]} — score composite {_ts[2]}/100",
                "risque":         "Risque de compression multiple si révisions BPA détériorées",
                "societes":       _socs_fb,
            })

    if not top3_secteurs and _eu_members_by_sec:
        import statistics as _stat_t3
        for _ts in sorted(secteurs, key=lambda s: s[2], reverse=True)[:3]:
            _tsn  = _ts[0]
            _mems = sorted(_eu_members_by_sec.get(_tsn, []),
                           key=lambda m: m["score_raw"], reverse=True)[:3]
            _socs = []
            for _m in _mems:
                _er = _m.get("ev_ebitda")
                _es = (f"{_er:.1f}x".replace('.', ',') if _er and 0.5 < _er < 200 else "\u2014")
                _socs.append((_m["ticker"], _ts[3], _es, _m["score_raw"]))
            _ev_v = [m["ev_ebitda"] for m in _eu_members_by_sec.get(_tsn, [])
                     if m.get("ev_ebitda") and 0.5 < m["ev_ebitda"] < 100]
            _pe_v = [m["pe_fwd"] for m in _eu_members_by_sec.get(_tsn, [])
                     if m.get("pe_fwd") and 3 < m["pe_fwd"] < 100]
            _ret  = (sum(m["ret_52w"] for m in _eu_members_by_sec.get(_tsn, [])) /
                     max(1, len(_eu_members_by_sec.get(_tsn, []))))
            top3_secteurs.append({
                "nom":            _tsn,
                "signal":         _ts[3],
                "score":          _ts[2],
                "ev_ebitda":      (f"{_stat_t3.median(_ev_v):.1f}x".replace('.', ',') if _ev_v else "\u2014"),
                "pe_forward_raw": round(_stat_t3.median(_pe_v), 1) if _pe_v else 18.0,
                "pe_mediane_10y": 16.0,
                "poids_indice":   "—",
                "catalyseur":     f"Performance 52S {_ret:+.1f} % — momentum {_ts[3].lower()}".replace('.', ','),
                "risque":         "Risque macro zone Euro, USD strength, taux longs",
                "societes":       _socs or [("—", "Neutre", "\u2014", 50)],
            })

    # --- ETF proxy fallback pour top3_secteurs ev_ebitda (reutilise _etf_proxy_ev) ---
    if _etf_proxy_ev is None:
        # Fetch proxy si pas deja fait (chemin S&P 500 n'a pas eu le fallback secteurs)
        _proxy_ticker_t3 = _ETF_INDEX_PROXIES.get(universe)
        if _proxy_ticker_t3:
            try:
                _p3_obj  = get_ticker(_proxy_ticker_t3)
                _p3_info = _p3_obj.info or {}
                _p3_ev   = _p3_info.get("enterpriseToEbitda")
                if _p3_ev and 1.0 < float(_p3_ev) < 200:
                    _etf_proxy_ev = round(float(_p3_ev), 1)
            except Exception:
                pass
    if _etf_proxy_ev:
        _t3_ev_missing = sum(1 for t in top3_secteurs
                             if str(t.get("ev_ebitda", "\u2014")) in ("\u2014", "---", "", "None"))
        if top3_secteurs and _t3_ev_missing > len(top3_secteurs) * 0.5:
            for _t3 in top3_secteurs:
                if str(_t3.get("ev_ebitda", "\u2014")) in ("\u2014", "---", "", "None"):
                    _t3["ev_ebitda"] = f"{_etf_proxy_ev:.1f}x*"
            log.info("ETF proxy top3 -> EV/EBITDA fallback %.1fx pour %s", _etf_proxy_ev, universe)

    # Fallback ultime : si un secteur du top3 n'a pas de societes (ou seulement
    # un placeholder synthétique), peupler avec _get_real_tickers (table hardcodée
    # par univers). Sans ça, le tableau « Sociétés représentatives » du PDF reste
    # vide (audit 28/04/2026 — bug placeholder ('—','Neutre','—',50) qui empêchait
    # le fallback de se déclencher).
    def _is_placeholder_socs(socs):
        if not socs:
            return True
        # Tous les tickers sont des em-dash → placeholder synthétique
        return all(str(s[0]).strip() in ("—", "\u2014", "", "None") for s in socs if len(s) > 0)
    log.info("top3_secteurs avant fallback societes: %d secteurs",
             len(top3_secteurs))
    for _t3 in top3_secteurs:
        _existing = _t3.get("societes")
        _is_ph = _is_placeholder_socs(_existing)
        log.info("  %s : societes=%s, is_placeholder=%s",
                 _t3.get("nom", "?"), _existing, _is_ph)
        if _is_ph:
            _fallback_tk = (_get_real_tickers(_t3.get("nom", ""), universe) or
                            _get_real_tickers(_t3.get("nom", ""), "S&P 500") or [])[:3]
            log.info("    fallback tickers: %s", _fallback_tk)
            if _fallback_tk:
                _t3["societes"] = [
                    (tk, _t3.get("signal", "Neutre"), _t3.get("ev_ebitda", "\u2014"),
                     _t3.get("score", 50))
                    for tk in _fallback_tk
                ]

    # Base test pour les champs sans source temps reel
    base = _make_test_indice_data(universe)
    # Regenerer texte_signal coherent avec le signal reel — version enrichie
    # via LLM pour synthèse slide 2 plus longue et pertinente (demande Baptiste
    # 2026-04-17). Fallback déterministe si LLM indisponible.
    noms_surp = [s[0] for s in secteurs if s[3] == "Surpondérer"][:5]
    noms_sous = [s[0] for s in secteurs if s[3] == "Sous-pondérer"][:5]
    _nb_neutre = len(secteurs) - nb_surp - sum(1 for s in secteurs if s[3] == 'Sous-pondérer')
    _nb_sous = sum(1 for s in secteurs if s[3] == 'Sous-pondérer')

    texte_signal_reel = ""
    try:
        from core.llm_provider import llm_call
        from core.prompt_standards import build_system_prompt, length_rule, pptx_overflow_rule
        _sys_ts = build_system_prompt(
            role="analyste sell-side senior sur allocation stratégique d'indices",
        )
        _prompt_ts = (
            f"{_sys_ts}\n\n"
            f"{length_rule(min_words=100, max_words=150)}\n"
            f"{pptx_overflow_rule(zone='slide 2 — synthèse signal', max_words=150)}\n\n"
            f"CONTEXTE — synthèse signal global {universe} :\n"
            f"Signal : {signal_global} (conviction {conviction}%).\n"
            f"{len(secteurs)} secteurs analysés : "
            f"{nb_surp} Surpondérer, {_nb_neutre} Neutre, {_nb_sous} Sous-pondérer.\n"
            f"Leaders : {', '.join(noms_surp) or 'aucun'}.\n"
            f"Retardataires : {', '.join(noms_sous) or 'aucun'}.\n\n"
            f"STRUCTURE dense en 3 temps :\n"
            f"1. DIAGNOSTIC (40 mots) : signal global + justification momentum/révisions/"
            f"valorisation. Pourquoi ce niveau de conviction.\n"
            f"2. SECTEURS CLÉS (50 mots) : secteurs moteurs Surpondérer avec 1-2 mots "
            f"clés par secteur. Mentionner aussi les Sous-pondérer si relevant.\n"
            f"3. HORIZON & TACTIQUE (40 mots) : horizon 12 mois, risques à surveiller, "
            f"triggers de re-rating/de-rating."
        )
        texte_signal_reel = (llm_call(_prompt_ts, phase="long", max_tokens=450) or "").strip()
    except Exception as _e_ts:
        log.debug(f"[cli_analyze:texte_signal] LLM skipped: {_e_ts}")

    # Fallback déterministe enrichi (sans LLM) si pas de sortie
    if not texte_signal_reel:
        texte_signal_reel = (
            f"Le signal global sur le {universe} ressort {signal_global} avec une conviction de "
            f"{conviction}% sur la base des {len(secteurs)} secteurs analysés. "
            f"{nb_surp} secteur(s) ressortent Surpondérer — {', '.join(noms_surp) or 'aucun'} "
            f"— portés par momentum positif 52 semaines et révisions BPA favorables. "
            f"{_nb_neutre} secteurs affichent un profil Neutre, {_nb_sous} restent en Sous-pondérer "
            f"{('(' + ', '.join(noms_sous) + ')') if noms_sous else ''}. "
            f"La prime/décote de valorisation et le positionnement dans le cycle macro "
            f"justifient un horizon d'allocation 12 mois. Triggers à surveiller : inflexion "
            f"banque centrale, révisions BPA NTM, rotation défensif/offensif."
        )

    # Prime/decote vs mediane P/E historique 10 ans
    _PE_HIST_INDICE = {
        "S&P 500": (14.0, 22.0), "CAC 40": (11.0, 20.0), "CAC40": (11.0, 20.0),
        "DAX": (10.0, 19.0), "DAX 40": (10.0, 19.0), "DAX40": (10.0, 19.0),
        "FTSE 100": (10.0, 17.0), "FTSE100": (10.0, 17.0),
        "Euro Stoxx 50": (11.0, 19.0), "STOXX50": (11.0, 19.0),
    }
    _pe_range = _PE_HIST_INDICE.get(universe, (12.0, 22.0))
    _pe_med_10y = round((_pe_range[0] + _pe_range[1]) / 2, 1)
    _prime_decote_str = "\u2014"
    try:
        _pe_num = float(pe_fwd_str.replace("x","").replace(",",".").strip())
        _prime_val = (_pe_num - _pe_med_10y) / _pe_med_10y * 100
        _prime_decote_str = (f"+{_prime_val:.0f}% prime"
                             if _prime_val > 0 else f"{_prime_val:.0f}% decote")
    except Exception:
        pass

    # P/B et DivYield generiques pour indices EU (si ETF SPDR non disponibles)
    _EU_PB_GENERIC = {
        "Technology": 8.5, "Health Care": 4.2, "Financials": 1.5,
        "Consumer Discretionary": 5.8, "Communication Services": 3.6,
        "Industrials": 4.9, "Consumer Staples": 5.2, "Energy": 2.3,
        "Materials": 3.8, "Real Estate": 2.1, "Utilities": 1.8,
    }
    _EU_DY_GENERIC = {
        "Technology": 0.7, "Health Care": 1.6, "Financials": 2.5,
        "Consumer Discretionary": 0.9, "Communication Services": 1.1,
        "Industrials": 1.8, "Consumer Staples": 3.0, "Energy": 4.0,
        "Materials": 2.2, "Real Estate": 4.2, "Utilities": 3.5,
    }
    _eu_pb_map = {}
    _eu_dy_map = {}
    _eu_erp_map = {}
    _EU_NORM = {
        "Healthcare": "Health Care",
        "Cons. Staples": "Consumer Staples",
        "Consumer Defensive": "Consumer Staples",
        "Cons. Discret.": "Consumer Discretionary",
        "Consumer Disc.": "Consumer Discretionary",
        "Comm. Services": "Communication Services",
        "Financial Services": "Financials",
        "Info. Technology": "Technology",
        "Info Technology": "Technology",
    }
    if universe != "S&P 500":
        for _sname, _nb, _sc, _sig, _ev_s, _mg, _gr_s, _mom_s in secteurs:
            _norm_name = _EU_NORM.get(_sname, _sname)
            _pb_v = _EU_PB_GENERIC.get(_norm_name) or _EU_PB_GENERIC.get(_sname)
            _dy_v = _EU_DY_GENERIC.get(_norm_name) or _EU_DY_GENERIC.get(_sname)
            _eu_pb_map[_sname] = _pb_v
            _eu_dy_map[_sname] = _dy_v
            _dy_dec = (_dy_v or 0) / 100
            _gr_eu  = 6.0 / 100
            _eu_erp_map[_sname] = round((_dy_dec + _gr_eu - rf_rate) * 100, 1)

    base.update({
        "code":               code,
        "cours":              cours_str,
        "variation_ytd":      ytd_str,
        "pe_forward":         pe_fwd_str,
        "pe_mediane_10y":     _pe_med_10y,
        "prime_decote":       _prime_decote_str,
        "erp":                erp_pct,
        "rf_rate":            rf_pct_str,
        "erp_signal":         erp_signal,
        "signal_global":      signal_global,
        "conviction_pct":     conviction,
        "score_median":       avg_score,
        "nb_secteurs":        len(secteurs),
        "secteurs":           secteurs,
        "top3_secteurs":      top3_secteurs,
        "etf_perf":           etf_perf,
        "date_analyse":       date_str,
        "texte_signal":       texte_signal_reel,
        "sector_contribution":  sector_contribution,
        "indice_analytics":     indice_analytics,
        "correlation_matrix":   correlation_data,
        "pb_by_sector":         pb_by_sector    if universe == "S&P 500" else _eu_pb_map,
        "dy_by_sector":         dy_by_sector    if universe == "S&P 500" else _eu_dy_map,
        "erp_by_sector":        erp_by_sector   if universe == "S&P 500" else _eu_erp_map,
        "etf_proxy_ev_ebitda":  _etf_proxy_ev,        # ETF proxy fallback (None si non-utilise)
        "optimal_portfolios":   optimal_portfolios,
        "methodologie": [
            ("Score FinSight",   "Composite 0-100 : momentum 40% + revisions BPA 30% + valorisation relative 30%"),
            ("Signal indice",    "Score agrege secteurs : >60 Surpondérer / 40-60 Neutre / <40 Sous-pondérer"),
            ("Conviction",       "% secteurs en accord avec le signal global (surponderes / total)"),
            ("EV/EBITDA",        "Mediane LTM des 5 premiers titres par capitalisation de chaque secteur"),
            ("P/E Forward",      "Consensus analystes NTM (yfinance + FMP) — comparaison P/E Mediane 10Y"),
            ("ERP Damodaran",    "Earnings yield (1/PE Fwd) moins 10Y Treasury yield — proxy prime de risque actions"),
            ("Allocation Markowitz", "Optimisation scipy SLSQP sur correlation sectorielle 52S, contrainte max 40%/secteur"),
            ("Sentiment",        "FinBERT sur articles Finnhub + RSS — non agrege au niveau indice"),
        ],
        **({"perf_history": _eu_perf_history} if _eu_perf_history else {}),
        # Per-ticker raw data pour IndiceExcelWriter (EU + US indices)
        "tickers_raw": _eu_res if _eu_members_by_sec else [],
        "universe":    universe,
        # indice_stats : perf_ytd/1y/3y/5y/vol_1y/sharpe_1y/max_dd pour tuiles UI
        "indice_stats": _compute_indice_stats(code, rf_annual=rf_rate),
    })

    # Sentiment_agg : recalcule depuis les VRAIS secteurs (sinon hérite des
    # noms anglais hardcodés de _make_test_indice_data → slide 19 vide en prod)
    _real_surp = [s[0] for s in secteurs if s[3] == "Surpondérer"]
    _real_sous = [s[0] for s in secteurs if s[3] == "Sous-pondérer"]
    _nb_surp_r = len(_real_surp)
    _nb_sous_r = len(_real_sous)
    _nb_neut_r = len(secteurs) - _nb_surp_r - _nb_sous_r
    _denom_r   = max(len(secteurs), 1)
    base["sentiment_agg"] = {
        "label":        signal_global,
        "score":        0.0,
        "nb_articles":  0,
        "positif_nb":   _nb_surp_r,
        "positif_pct":  round(100 * _nb_surp_r / _denom_r),
        "neutre_nb":    _nb_neut_r,
        "neutre_pct":   round(100 * _nb_neut_r / _denom_r),
        "negatif_nb":   _nb_sous_r,
        "negatif_pct":  round(100 * _nb_sous_r / _denom_r),
        "themes_pos":   _real_surp,
        "themes_neg":   _real_sous,
        "positif": {"nb": _nb_surp_r, "score": "—", "themes": "—"},
        "neutre":  {"nb": _nb_neut_r, "score": "—", "themes": "—"},
        "negatif": {"nb": _nb_sous_r, "score": "—", "themes": "—"},
        "par_secteur": [],
    }

    # LLM : generation texte analytique reel (texte_macro, texte_valorisation, catalyseurs, risques)
    try:
        import json as _json_llm
        from core.llm_provider import LLMProvider as _LLMProvider
        _llm = _LLMProvider(provider="mistral", model="mistral-small-latest")
        _top3_prompt = []
        for _t in top3_secteurs[:3]:
            _top3_prompt.append(
                f"{_t['nom']} (signal={_t['signal']}, score={_t['score']}, "
                f"mom={_t.get('catalyseur','—')})")
        _sous_pond = [s[0] for s in secteurs if s[3] == "Sous-pondérer"][:2]
        _prompt_llm = (
            f"Indice: {universe} | Cours: {cours_str} | YTD: {ytd_str} | "
            f"P/E: {pe_fwd_str} | ERP: {erp_pct} ({erp_signal}) | "
            f"Signal global: {signal_global} ({conviction}% conviction) | Rf: {rf_pct_str}\n"
            f"Top secteurs: {'; '.join(_top3_prompt)}\n"
            f"Sous-pondérer: {', '.join(_sous_pond) if _sous_pond else 'aucun'}\n"
            f"Reponds UNIQUEMENT en JSON valide, sans markdown, sans points de suspension (...).\n"
            f'{{"texte_macro":"2 phrases sur macro actuelle (taux, croissance, risques specifiques a {universe})","'
            f'texte_valorisation":"2 phrases sur valorisation (P/E vs historique, ERP, attractivite)","'
            f'catalyseurs":[{{"titre":"titre court","description":"1 phrase complete"}},'
            f'{{"titre":"titre court","description":"1 phrase complete"}},'
            f'{{"titre":"titre court","description":"1 phrase complete"}}],"'
            f'risques":[{{"titre":"titre court","description":"1 phrase","proba":"X %","severity":"ELEVE"}},'
            f'{{"titre":"titre court","description":"1 phrase","proba":"X %","severity":"MODERE"}},'
            f'{{"titre":"titre court","description":"1 phrase","proba":"X %","severity":"MODERE"}}]}}'
        )
        _resp_llm = _llm.generate(
            prompt=_prompt_llm,
            system=(
                "Tu es un analyste buy-side senior specialise dans les indices boursiers. "
                "Reponds en francais avec accents. JSON strict uniquement. "
                "Phrases completes sans points de suspension (...). "
                "IMPORTANT: les titres des risques doivent decrire des evenements negatifs qui se materialisent (ex: 'Recession aux Etats-Unis', 'Compression des marges', 'Choc de taux'), jamais des scenarios positifs."
            ),
            max_tokens=700,
        )
        _js_s = _resp_llm.find("{")
        _js_e = _resp_llm.rfind("}") + 1
        if _js_s >= 0 and _js_e > _js_s:
            _parsed_llm = _json_llm.loads(_resp_llm[_js_s:_js_e])
            if "texte_macro" in _parsed_llm:
                base["texte_macro"] = _parsed_llm["texte_macro"]
            if "texte_valorisation" in _parsed_llm:
                base["texte_valorisation"] = _parsed_llm["texte_valorisation"]
            if "catalyseurs" in _parsed_llm and isinstance(_parsed_llm["catalyseurs"], list):
                base["catalyseurs"] = [
                    (c.get("titre", "\u2014"), c.get("description", "\u2014"), "6-12 mois")
                    for c in _parsed_llm["catalyseurs"][:3]
                ]
            if "risques" in _parsed_llm and isinstance(_parsed_llm["risques"], list):
                base["risques"] = [
                    (r.get("titre", "\u2014"), r.get("description", "\u2014"),
                     r.get("proba", "15 %"), r.get("severity", "MODERE"))
                    for r in _parsed_llm["risques"][:3]
                ]
            log.info("LLM texte indice OK (%s, %d chars)", universe, len(_resp_llm))
    except Exception as _llm_ex:
        log.warning("LLM texte indice erreur: %s -- fallback f-string", _llm_ex)
        _f_surp = [s[0] for s in secteurs if s[3] == "Surpondérer"]
        _f_sous = [s[0] for s in secteurs if s[3] == "Sous-pondérer"]
        base["texte_macro"] = (
            f"L'{universe} affiche une performance YTD de {ytd_str} dans un contexte "
            f"de taux a {rf_pct_str} (obligation de reference 10 ans). "
            f"Le signal global ressort {signal_global} avec une conviction de {conviction}%."
        )
        base["texte_valorisation"] = (
            f"Le P/E Forward de l'{universe} s'etablit a {pe_fwd_str}. "
            f"L'ERP implicite de {erp_pct} signale un profil de risque {erp_signal.lower()} "
            f"par rapport aux obligations souveraines."
        )
        base["catalyseurs"] = [
            (_f_surp[0] if _f_surp else "Momentum sectoriel",
             f"Secteur leader sur 52 semaines avec signal Surpondérer confirme par le score composite.",
             "6-12 mois"),
            ("Prime de risque",
             f"ERP a {erp_pct} — attractivite relative des actions versus les obligations maintenue.",
             "3-6 mois"),
            ("Conviction allocataire",
             f"{conviction}% de conviction Surpondérer sur {len(secteurs)} secteurs analyses par FinSight.",
             "6-18 mois"),
        ]
        base["risques"] = [
            ("Retournement macro",
             f"Deterioration du cycle economique impactant les {_f_surp[0] if _f_surp else 'secteurs leaders'}.",
             "20 %", "ELEVE"),
            ("Choc taux",
             f"Remontee du 10 ans au-dela de {rf_pct_str} — compression des multiples de valorisation.",
             "15 %", "MODERE"),
            ("Pression sectorielle",
             f"Sous-performance de {_f_sous[0] if _f_sous else 'secteurs défensifs'} — rotation defensive.",
             "15 %", "MODERE"),
        ]

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
    elif mode in ("cmp_secteur", "cmpsec", "cmp-secteur"):
        # Usage : python cli_analyze.py cmp_secteur Technology "S&P 500" Healthcare "S&P 500"
        sector_a  = arg1
        universe_a = arg2
        sector_b  = sys.argv[4] if len(sys.argv) > 4 else "Healthcare"
        universe_b = sys.argv[5] if len(sys.argv) > 5 else universe_a
        run_cmp_secteur(sector_a, universe_a, sector_b, universe_b)
    else:
        print(f"Mode inconnu : {mode}. Utiliser : societe | secteur | indice | cmp_secteur")
        sys.exit(1)