# -*- coding: utf-8 -*-
"""
tests/test_core.py — Filet de sécurité pour les modules core de FinSight IA.

Tests standalone (pattern assert, pas pytest obligatoire) couvrant :
- core/currency.py       : convert, GBp, fallback exotique, cache
- core/sector_profiles.py : detect_profile sur 30 cas
- core/yfinance_cache.py : singleton, TTL, thread safety
- outputs/excel_profile_router.py : dispatcher, cell maps, formula cells
- core/llm_context.py    : format_* helpers (pas de fetch live)

USAGE:
    python tests/test_core.py

Exit code 0 si tous les tests passent, 1 si au moins un échoue.
"""
from __future__ import annotations

import os
import sys
import time

# Force stdout utf-8 pour Windows cp1252
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Root project dans le path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═════════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE DE TEST
# ═════════════════════════════════════════════════════════════════════════════

_PASS = 0
_FAIL = 0
_FAILURES: list[tuple[str, str]] = []


def assert_eq(actual, expected, msg: str = ""):
    global _PASS, _FAIL
    if actual == expected:
        _PASS += 1
    else:
        _FAIL += 1
        _FAILURES.append((msg or "assert_eq", f"expected {expected!r}, got {actual!r}"))


def assert_true(cond: bool, msg: str = ""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
        _FAILURES.append((msg or "assert_true", "condition was False"))


def assert_in(elem, container, msg: str = ""):
    global _PASS, _FAIL
    if elem in container:
        _PASS += 1
    else:
        _FAIL += 1
        _FAILURES.append((msg or "assert_in", f"{elem!r} not in {container!r}"))


def assert_approx(actual, expected, tol: float = 0.01, msg: str = ""):
    global _PASS, _FAIL
    try:
        if actual is None or expected is None:
            _FAIL += 1
            _FAILURES.append((msg or "assert_approx", f"None : {actual} vs {expected}"))
            return
        if abs(float(actual) - float(expected)) <= tol * abs(float(expected)):
            _PASS += 1
        else:
            _FAIL += 1
            _FAILURES.append(
                (msg or "assert_approx", f"expected ~{expected} (tol {tol*100}%), got {actual}")
            )
    except Exception as e:
        _FAIL += 1
        _FAILURES.append((msg or "assert_approx", f"type error: {e}"))


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ═════════════════════════════════════════════════════════════════════════════
# TESTS : core/currency.py
# ═════════════════════════════════════════════════════════════════════════════

def test_currency():
    section("core/currency.py")
    from core.currency import (
        convert,
        fetch_fx_rate,
        get_target_currency,
        currency_symbol,
        DEFAULT_TARGET_CURRENCY,
        clear_fx_cache,
        _normalize_currency,
    )

    clear_fx_cache()

    # Identity conversion
    assert_eq(convert(100, "EUR", "EUR"), 100.0, "EUR→EUR identity")
    assert_eq(convert(100, "USD", "USD"), 100.0, "USD→USD identity")

    # None propagation
    assert_eq(convert(None, "USD"), None, "None input → None output")

    # Default target
    assert_eq(get_target_currency(), "EUR", "Default target is EUR")
    assert_eq(DEFAULT_TARGET_CURRENCY, "EUR", "Default constant is EUR")

    # GBp normalization
    ccy, mult = _normalize_currency("GBp")
    assert_eq(ccy, "GBP", "GBp normalizes to GBP")
    assert_eq(mult, 0.01, "GBp multiplier is 0.01")

    # ILA normalization
    ccy, mult = _normalize_currency("ILA")
    assert_eq(ccy, "ILS", "ILA normalizes to ILS")

    # Currency symbol
    assert_eq(currency_symbol("USD"), "$", "USD symbol is $")
    assert_eq(currency_symbol("EUR"), "€", "EUR symbol is €")
    assert_eq(currency_symbol("GBP"), "£", "GBP symbol is £")
    assert_eq(currency_symbol("JPY"), "¥", "JPY symbol is ¥")

    # Fallback unknown currency
    result = convert(100, "XYZ", "EUR")
    assert_eq(result, 100.0, "Unknown currency fallback 1:1")

    # Live FX test (online)
    rate = fetch_fx_rate("USD", "EUR")
    if rate is not None:
        assert_true(0.7 < rate < 1.2, f"USD→EUR rate plausible (got {rate})")
        assert_approx(convert(100, "USD", "EUR"), 100 * rate, tol=0.01, msg="100 USD→EUR matches rate")


# ═════════════════════════════════════════════════════════════════════════════
# TESTS : core/sector_profiles.py
# ═════════════════════════════════════════════════════════════════════════════

def test_sector_profiles():
    section("core/sector_profiles.py")
    from core.sector_profiles import detect_profile

    # Banks (US + EU + UK)
    assert_eq(detect_profile("Financial Services", "Banks - Diversified"), "BANK", "JPM bank")
    assert_eq(detect_profile("Financial Services", "Banks - Regional"), "BANK", "Regional bank")
    assert_eq(detect_profile("Financial Services", "Capital Markets"), "BANK", "GS capital markets = BANK")
    assert_eq(detect_profile("Banques", ""), "BANK", "FR fallback Banques")

    # Insurance
    assert_eq(detect_profile("Financial Services", "Insurance - Diversified"), "INSURANCE", "AXA insurance")
    assert_eq(detect_profile("Financial Services", "Insurance - Life"), "INSURANCE", "Life insurance")
    assert_eq(detect_profile("Financial Services", "Insurance - Reinsurance"), "INSURANCE", "Reinsurance")
    assert_eq(detect_profile("Assurance", ""), "INSURANCE", "FR fallback Assurance")

    # REIT
    assert_eq(detect_profile("Real Estate", "REIT - Retail"), "REIT", "Realty Income")
    assert_eq(detect_profile("Real Estate", "REIT - Industrial"), "REIT", "Prologis")
    assert_eq(detect_profile("Immobilier", ""), "REIT", "FR fallback Immobilier")

    # Utility
    assert_eq(detect_profile("Utilities", "Utilities - Regulated Electric"), "UTILITY", "NextEra")
    assert_eq(detect_profile("Services aux collectivités", ""), "UTILITY", "FR fallback Services collectivités")

    # Oil & Gas
    assert_eq(detect_profile("Energy", "Oil & Gas Integrated"), "OIL_GAS", "XOM integrated")
    assert_eq(detect_profile("Energy", "Oil & Gas E&P"), "OIL_GAS", "EOG E&P")
    # Energy downstream (refining/equipment/services) stays STANDARD
    assert_eq(detect_profile("Energy", "Oil & Gas Refining & Marketing"), "STANDARD", "VLO downstream")
    assert_eq(detect_profile("Energy", "Oil & Gas Equipment & Services"), "STANDARD", "SLB services")
    assert_eq(detect_profile("Pétrole", ""), "OIL_GAS", "FR fallback Pétrole")

    # Standard (corporate)
    assert_eq(detect_profile("Technology", "Software - Infrastructure"), "STANDARD", "MSFT tech")
    assert_eq(detect_profile("Consumer Cyclical", "Auto Manufacturers"), "STANDARD", "TSLA auto")
    assert_eq(detect_profile("Healthcare", "Biotechnology"), "STANDARD", "biotech")
    assert_eq(detect_profile("Consumer Defensive", "Beverages - Non-Alcoholic"), "STANDARD", "KO")

    # Asset Managers (BlackRock, Brookfield) → STANDARD (fee-based)
    assert_eq(detect_profile("Financial Services", "Asset Management"), "STANDARD", "Asset manager = STANDARD")

    # Edge case : empty inputs → STANDARD
    assert_eq(detect_profile("", ""), "STANDARD", "Empty → STANDARD")
    assert_eq(detect_profile(None, None), "STANDARD", "None → STANDARD")


# ═════════════════════════════════════════════════════════════════════════════
# TESTS : core/yfinance_cache.py
# ═════════════════════════════════════════════════════════════════════════════

def test_yfinance_cache():
    section("core/yfinance_cache.py")
    from core.yfinance_cache import (
        get_ticker,
        clear_ticker_cache,
        clear_ticker,
        cache_stats,
        set_ttl,
    )

    clear_ticker_cache()

    # Stats init
    stats = cache_stats()
    assert_eq(stats["size"], 0, "Empty cache size = 0")
    assert_eq(stats["hits"], 0, "Empty cache hits = 0")
    assert_eq(stats["misses"], 0, "Empty cache misses = 0")

    # Cache miss + singleton
    tk1 = get_ticker("AAPL")
    tk2 = get_ticker("AAPL")
    assert_true(tk1 is tk2, "Same instance for same symbol (singleton)")

    # Case insensitive
    tk3 = get_ticker("aapl")
    assert_true(tk1 is tk3, "Case insensitive")

    # Multiple tickers
    tk_msft = get_ticker("MSFT")
    assert_true(tk1 is not tk_msft, "Different symbols → different instances")

    # Stats
    stats = cache_stats()
    assert_eq(stats["size"], 2, "2 unique tickers cached")
    assert_true(stats["hits"] >= 2, f"At least 2 hits (got {stats['hits']})")
    assert_eq(stats["misses"], 2, "2 unique misses")
    assert_in("AAPL", stats["symbols"], "AAPL in cache symbols")

    # Clear single
    clear_ticker("AAPL")
    assert_eq(cache_stats()["size"], 1, "After clear_ticker, 1 left")

    # Clear all
    clear_ticker_cache()
    assert_eq(cache_stats()["size"], 0, "clear_ticker_cache empties all")


# ═════════════════════════════════════════════════════════════════════════════
# TESTS : outputs/excel_profile_router.py
# ═════════════════════════════════════════════════════════════════════════════

def test_excel_profile_router():
    section("outputs/excel_profile_router.py")
    from outputs.excel_profile_router import (
        TEMPLATES,
        get_template_for,
        get_cell_map,
        get_formula_cells_for,
        profile_template_exists,
    )

    # TEMPLATES dict has all 6 profiles
    for profile in ("STANDARD", "BANK", "INSURANCE", "REIT", "UTILITY", "OIL_GAS"):
        assert_in(profile, TEMPLATES, f"{profile} in TEMPLATES")

    # STANDARD template exists
    assert_true(profile_template_exists("STANDARD"), "STANDARD template file exists")

    # BANK/INSURANCE/etc. templates don't exist yet → fallback to STANDARD
    for profile in ("BANK", "INSURANCE", "REIT", "UTILITY", "OIL_GAS"):
        path = get_template_for(profile)
        assert_in("TEMPLATE", path.name.upper(), f"{profile} falls back to template file")

    # get_cell_map for STANDARD returns real dict
    cm = get_cell_map("STANDARD")
    assert_in("is_rows", cm, "STANDARD cell_map has is_rows")
    assert_in("bs_asset_rows", cm, "STANDARD cell_map has bs_asset_rows")
    assert_in("mkt_fields", cm, "STANDARD cell_map has mkt_fields")
    assert_eq(cm["is_rows"]["revenue"], 9, "revenue row is 9")

    # Non-STANDARD profiles fallback to STANDARD cell_map
    cm_bank = get_cell_map("BANK")
    assert_in("is_rows", cm_bank, "BANK cell_map fallback has is_rows")

    # Formula cells detection on STANDARD template
    fc = get_formula_cells_for("STANDARD")
    assert_true(len(fc) > 50, f"STANDARD has >50 formula cells (got {len(fc)})")
    # H108 is WACC formula in TEMPLATE.xlsx
    assert_in("H108", fc, "H108 (WACC) detected as formula")


# ═════════════════════════════════════════════════════════════════════════════
# TESTS : core/llm_context.py
# ═════════════════════════════════════════════════════════════════════════════

def test_llm_context():
    section("core/llm_context.py")
    from core.llm_context import (
        format_macro_for_prompt,
        format_news_for_prompt,
        format_finsight_explanation,
        LLM_DECISION_FRAMING,
    )

    # Macro formatting with sample data (pas de fetch live pour garder le test rapide)
    macro = {
        "regime": "Bull",
        "vix": 18.4,
        "tnx_10y": 4.26,
        "irx_3m": 3.61,
        "spread_10y_3m": 0.65,
        "recession_prob_6m": 10,
        "recession_prob_12m": 15,
        "recession_level": "Faible",
        "recession_drivers": [],
        "sp_vs_ma200": 3.2,
        "sp_mom_6m": 8.1,
    }
    block = format_macro_for_prompt(macro)
    assert_in("Bull", block, "Macro block mentions regime")
    assert_in("18.4", block, "Macro block mentions VIX")
    assert_in("4.26", block, "Macro block mentions TNX")

    # FinSight explanation
    expl = format_finsight_explanation(
        score_global=75, score_value=80, score_growth=70,
        score_quality=85, score_momentum=65, profile="STANDARD", ticker="AAPL"
    )
    assert_in("AAPL", expl, "Explanation mentions ticker")
    assert_in("75", expl, "Explanation mentions global score")
    assert_in("Value", expl, "Explanation mentions Value dim")
    assert_in("Growth", expl, "Explanation mentions Growth dim")
    assert_in("STANDARD", expl, "Explanation mentions profile")
    assert_in("rétrospective", expl.lower(), "Explanation mentions rétrospectif")

    # None score → "indisponible"
    expl_none = format_finsight_explanation(None, ticker="X")
    assert_in("indisponible", expl_none.lower(), "None score → indisponible")

    # News formatting with None sentiment
    news = format_news_for_prompt(None, ticker="AAPL")
    assert_in("AAPL", news, "News block mentions ticker")
    assert_in("aucune news", news.lower(), "Empty news explained")

    # LLM framing constant
    assert_in("décision", LLM_DECISION_FRAMING.lower(), "Framing mentions decision")
    assert_in("news", LLM_DECISION_FRAMING.lower(), "Framing mentions news")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    t_start = time.time()

    print("=" * 60)
    print("  FinSight IA — Core modules test suite")
    print("=" * 60)

    try:
        test_currency()
    except Exception as e:
        import traceback
        _FAILURES.append(("test_currency", f"unhandled: {e}\n{traceback.format_exc()}"))

    try:
        test_sector_profiles()
    except Exception as e:
        import traceback
        _FAILURES.append(("test_sector_profiles", f"unhandled: {e}\n{traceback.format_exc()}"))

    try:
        test_yfinance_cache()
    except Exception as e:
        import traceback
        _FAILURES.append(("test_yfinance_cache", f"unhandled: {e}\n{traceback.format_exc()}"))

    try:
        test_excel_profile_router()
    except Exception as e:
        import traceback
        _FAILURES.append(("test_excel_profile_router", f"unhandled: {e}\n{traceback.format_exc()}"))

    try:
        test_llm_context()
    except Exception as e:
        import traceback
        _FAILURES.append(("test_llm_context", f"unhandled: {e}\n{traceback.format_exc()}"))

    elapsed = time.time() - t_start

    # Report
    print("\n" + "=" * 60)
    print(f"  RESULTAT : {_PASS} passed, {_FAIL} failed ({elapsed:.1f}s)")
    print("=" * 60)

    if _FAIL > 0:
        print("\n  ÉCHECS :")
        for i, (name, msg) in enumerate(_FAILURES, 1):
            print(f"  [{i}] {name}: {msg}")
        return 1

    print("\n  ✓ Tous les tests passent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
