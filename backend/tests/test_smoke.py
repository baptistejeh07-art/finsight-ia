"""Smoke tests pour le backend FastAPI.

Lance via :
    cd backend
    pytest tests/

Ne fait PAS d'analyse réelle (yfinance/LLM trop lent en CI). Vérifie juste
que les routes existent et répondent correctement à des inputs valides.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Permet d'importer main depuis backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "finsight-api"


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "FinSight IA API"
    assert "/health" in body["endpoints"]


def test_resolve_ticker_upper():
    r = client.get("/resolve/AAPL")
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] == "societe"
    assert j["ticker"] == "AAPL"


def test_resolve_ticker_with_suffix():
    r = client.get("/resolve/MC.PA")
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] == "societe"
    assert j["ticker"] == "MC.PA"


def test_resolve_indice_known():
    r = client.get("/resolve/CAC 40")
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] == "indice"
    assert j["universe"] == "CAC 40"


def test_resolve_secteur_known():
    r = client.get("/resolve/Technologie")
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] == "secteur"
    assert j["sector"] == "Technologie"


def test_resolve_unknown_lowercase():
    """Une saisie en minuscules doit être unknown (pas un faux ticker)."""
    r = client.get("/resolve/apple")
    j = r.json()
    assert j["kind"] == "unknown"


def test_resolve_unknown_garbage():
    """FOOBAR123XYZ ne doit PAS être classifié société."""
    r = client.get("/resolve/FOOBAR123XYZ")
    j = r.json()
    assert j["kind"] == "unknown"


def test_jobs_list_empty_initially():
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "jobs" in r.json()


def test_jobs_get_404():
    r = client.get("/jobs/inexistant-id")
    assert r.status_code == 404


def test_me_unauthenticated():
    r = client.get("/me")
    assert r.status_code == 401


def test_history_unauthenticated():
    r = client.get("/history")
    assert r.status_code == 401


def test_file_path_traversal_blocked():
    """Tentative de path traversal hors outputs/generated doit être 403/404."""
    r = client.get("/file/etc/passwd")
    assert r.status_code in (403, 404)
