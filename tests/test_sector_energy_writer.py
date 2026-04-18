"""Tests unitaires pour outputs/sector_energy_xlsx_writer."""
import pytest
from pathlib import Path
import tempfile
from outputs.sector_energy_xlsx_writer import (
    write_energy_sector_xlsx, build_ticker_dict_from_yfinance, COLUMNS,
)


def test_write_energy_sector_xlsx_smoke():
    """Smoke test : 2 sociétés, fichier généré."""
    sample = [
        {"ticker": "XOM", "company_name": "Exxon Mobil", "price": 110.5,
         "market_cap": 440.0, "ev_ebitda": 6.2},
        {"ticker": "CVX", "company_name": "Chevron", "price": 155.3,
         "market_cap": 280.0, "ev_ebitda": 7.1},
    ]
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        out = write_energy_sector_xlsx(sample, tmp.name)
    assert Path(out).exists()
    assert Path(out).stat().st_size > 50_000  # template fait ~110 KB


def test_columns_schema_consistent():
    """COLUMNS doit avoir 1 entrée par colonne lettre, sans doublon de key."""
    keys = [k for _, k in COLUMNS]
    assert len(keys) == len(set(keys)), "Doublon dans COLUMNS keys"
    letters = [letter for letter, _ in COLUMNS]
    assert len(letters) == len(set(letters)), "Doublon dans COLUMNS letters"


def test_build_ticker_dict_from_yfinance_handles_empty():
    """Si yfinance .info est vide, on retourne un dict avec defaults."""
    result = build_ticker_dict_from_yfinance("XOM", {})
    assert result["ticker"] == "XOM"
    assert result["sector"] == "Énergie"
    assert result["company_name"] == "XOM"  # fallback ticker


def test_build_ticker_dict_from_yfinance_full():
    """Avec une .info complète, tous les champs sont mappés."""
    info = {
        "longName": "Exxon Mobil Corporation",
        "currentPrice": 110.5,
        "marketCap": 440_000_000_000,  # 440 Mds
        "ebitda": 50_000_000_000,
        "enterpriseToEbitda": 6.2,
        "trailingPE": 12.5,
    }
    result = build_ticker_dict_from_yfinance("XOM", info)
    assert result["company_name"] == "Exxon Mobil Corporation"
    assert result["price"] == 110.5
    assert result["market_cap"] == 440.0  # converti en Mds
    assert result["ebitda_ltm"] == 50.0
    assert result["ev_ebitda"] == 6.2
    assert result["pe_ratio"] == 12.5
