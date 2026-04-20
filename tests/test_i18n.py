"""Tests unitaires pour le système i18n FinSight (core/i18n.py)."""
from __future__ import annotations

import sys
import io
from pathlib import Path

# Force UTF-8 output pour Windows cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.i18n import (
    t,
    field_label,
    ratio_label,
    sig_label,
    common_label,
    benchmark_rank_label,
    scoring_label,
    signal_label,
    disclaimer,
    legal_form_label,
    director_quality_label,
    bodacc_label,
    normalize_language,
    system_language_directive,
    format_currency_amount,
)
from core.sector_labels import label_for, fr_label, en_label


def _assert(cond, msg):
    assert cond, msg
    print(f"  OK {msg}")


def test_ratio_label():
    print("\n[ratio_label]")
    _assert(ratio_label("roe", "fr") == "ROE", "ROE FR = ROE")
    _assert(ratio_label("roe", "en") == "ROE", "ROE EN = ROE")
    _assert(ratio_label("marge_ebitda", "de") == "EBITDA-Marge", "EBITDA DE")
    _assert(ratio_label("dso_jours", "it").startswith("DSO"), "DSO IT")
    _assert(ratio_label("inconnu", "fr") == "Inconnu", "fallback inconnu")


def test_sig_label():
    print("\n[sig_label]")
    _assert(sig_label("ebe", "fr").startswith("Excédent"), "EBE FR")
    _assert(sig_label("ebe", "en") == "EBITDA", "EBE EN = EBITDA")
    _assert(sig_label("ebe", "de") == "EBITDA", "EBE DE = EBITDA")
    _assert(sig_label("chiffre_affaires", "pt") == "Volume de negócios", "CA PT")
    _assert(sig_label("caf", "en").startswith("Cash flow"), "CAF EN")


def test_common_label():
    print("\n[common_label]")
    _assert(common_label("indicateur", "fr") == "Indicateur", "Indicateur FR")
    _assert(common_label("indicateur", "en") == "Indicator", "Indicator EN")
    _assert(common_label("indicateur", "de") == "Indikator", "Indikator DE")
    _assert(common_label("rang", "es") == "Rango", "Rango ES")


def test_signal_label():
    print("\n[signal_label]")
    _assert(signal_label("Surpondérer", "en") == "Overweight", "Surpondérer -> Overweight")
    _assert(signal_label("Neutre", "de") == "Neutral", "Neutre DE")
    _assert(signal_label("Favorable", "it") == "Favorevole", "Favorable IT")


def test_scoring_label():
    print("\n[scoring_label]")
    _assert(scoring_label("health_score", "en").startswith("FinSight"), "health score EN")
    _assert(scoring_label("altman_verdict", "de") == "Altman-Urteil", "altman verdict DE")


def test_benchmark_rank():
    print("\n[benchmark_rank_label]")
    _assert(benchmark_rank_label("top_25", "en") == "Top 25%", "top_25 EN")
    _assert(benchmark_rank_label("above_median", "de") == "Über Median", "above_median DE")
    _assert(benchmark_rank_label("below_median", "pt") == "Abaixo da mediana", "below_median PT")


def test_disclaimer():
    print("\n[disclaimer]")
    _assert(disclaimer("not_advice_mifid", "fr").startswith("Ne constitue"), "FR")
    _assert(disclaimer("not_advice_mifid", "en").startswith("Does not"), "EN")
    _assert(disclaimer("not_advice_mifid", "es").startswith("No constituye"), "ES")


def test_legal_form():
    print("\n[legal_form_label]")
    _assert("SAS" in legal_form_label("SAS", "fr"), "SAS FR contains SAS")
    _assert("joint-stock" in legal_form_label("SAS", "en"), "SAS EN mentions joint-stock")


def test_normalize():
    print("\n[normalize_language]")
    _assert(normalize_language("FR") == "fr", "FR→fr")
    _assert(normalize_language("en-US") == "en", "en-US→en")
    _assert(normalize_language("invalid") == "fr", "invalid→fr (fallback)")


def test_system_directive():
    print("\n[system_language_directive]")
    _assert("français" in system_language_directive("fr").lower(), "FR mentions français")
    _assert("English" in system_language_directive("en"), "EN mentions English")
    _assert("español" in system_language_directive("es").lower(), "ES mentions español")


def test_sector_label_for():
    print("\n[sector_label_for]")
    _assert(label_for("Technology", "fr") == "Technologie", "Tech FR")
    _assert(label_for("Technology", "it") == "Tecnologia", "Tech IT")
    _assert(label_for("Technology", "es") == "Tecnología", "Tech ES")
    _assert(label_for("Healthcare", "de") == "Gesundheitswesen", "Health DE")


def test_format_currency():
    print("\n[format_currency_amount]")
    res = format_currency_amount(1_500_000_000, "EUR", "fr")
    _assert("€" in res, f"EUR FR: {res}")
    res = format_currency_amount(1_500_000_000, "USD", "en")
    _assert("$" in res, f"USD EN: {res}")
    res = format_currency_amount(None, "EUR", "fr")
    _assert(res == "—", f"None → '—': {res}")


def run_all():
    tests = [
        test_ratio_label, test_sig_label, test_common_label, test_signal_label,
        test_scoring_label, test_benchmark_rank, test_disclaimer, test_legal_form,
        test_normalize, test_system_directive, test_sector_label_for, test_format_currency,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all())
