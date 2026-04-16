# -*- coding: utf-8 -*-
"""
data/sources/edgar_source.py — Extraction de données depuis EDGAR (SEC).

Télécharge les derniers 10-K/10-Q depuis EDGAR, extrait les pages pertinentes,
et utilise le LLM pour parser les métriques sectorielles manquantes
(CET1, NPL, NIM pour banques ; FFO, AFFO, Occupancy pour REIT ; etc.).

Usage :
    from data.sources.edgar_source import extract_sector_metrics

    metrics = extract_sector_metrics("JPM", "BANK")
    # → {"cet1": 15.2, "npl_ratio": 0.6, "nim": 2.8, "cost_income": 55.3, ...}

    metrics = extract_sector_metrics("PLD", "REIT")
    # → {"ffo": 5420, "affo": 4850, "occupancy": 96.5, "walt": 5.1, ...}
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
from typing import Optional

log = logging.getLogger(__name__)

_USER_AGENT = "FinSight IA research@finsight-ia.com"
_EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"
_EDGAR_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


# ═══════════════════════════════════════════════════════════════════════════════
# EDGAR — Fetch derniers filings
# ═══════════════════════════════════════════════════════════════════════════════

def _get_cik(ticker: str) -> Optional[str]:
    """Résout un ticker vers son CIK (Central Index Key) EDGAR."""
    try:
        import requests
        url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "company": ticker,
            "CIK": ticker,
            "type": "10-K",
            "dateb": "",
            "owner": "include",
            "count": "1",
            "search_text": "",
            "output": "atom",
        }
        resp = requests.get(url, params=params, headers={"User-Agent": _USER_AGENT}, timeout=15)
        # Extract CIK from response
        match = re.search(r'CIK=(\d+)', resp.text)
        if match:
            return match.group(1).lstrip("0")
        # Try the JSON endpoint
        resp2 = requests.get(
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2024-01-01&forms=10-K",
            headers={"User-Agent": _USER_AGENT}, timeout=15,
        )
        return None
    except Exception as e:
        log.warning(f"[edgar] CIK lookup failed for {ticker}: {e}")
        return None


def _get_latest_10k_url(ticker: str) -> Optional[str]:
    """Retourne l'URL du dernier 10-K filing pour un ticker."""
    try:
        import requests
        # Méthode 1 : EDGAR full-text search API
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K&dateRange=custom&startdt=2024-01-01"
        resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                filing_url = hits[0].get("_source", {}).get("file_url")
                if filing_url:
                    return f"https://www.sec.gov{filing_url}" if filing_url.startswith("/") else filing_url

        # Méthode 2 : submissions endpoint
        # Résoudre le CIK via le ticker mapping
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        resp_t = requests.get(tickers_url, headers={"User-Agent": _USER_AGENT}, timeout=15)
        if resp_t.status_code == 200:
            tickers_data = resp_t.json()
            cik = None
            for entry in tickers_data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry["cik_str"]).zfill(10)
                    break
            if cik:
                sub_url = f"{_EDGAR_SUBMISSIONS}/CIK{cik}.json"
                resp_s = requests.get(sub_url, headers={"User-Agent": _USER_AGENT}, timeout=15)
                if resp_s.status_code == 200:
                    sub_data = resp_s.json()
                    recent = sub_data.get("filings", {}).get("recent", {})
                    forms = recent.get("form", [])
                    accessions = recent.get("accessionNumber", [])
                    primary_docs = recent.get("primaryDocument", [])
                    for idx, form in enumerate(forms):
                        if form == "10-K" and idx < len(accessions):
                            acc = accessions[idx].replace("-", "")
                            doc = primary_docs[idx] if idx < len(primary_docs) else ""
                            raw_cik = cik.lstrip("0")
                            return f"https://www.sec.gov/Archives/edgar/data/{raw_cik}/{acc}/{doc}"
        return None
    except Exception as e:
        log.warning(f"[edgar] 10-K URL lookup failed for {ticker}: {e}")
        return None


def _clean_html_to_text(html: str) -> str:
    """Nettoie le HTML EDGAR (XBRL inline) et retourne du texte lisible.

    Les 10-K EDGAR contiennent du HTML avec :
    - des balises XBRL inline (<ix:*, <xbrli:*) = données structurées à ignorer
    - des balises <script>, <style> = à supprimer
    - du texte narratif dans <p>, <span>, <div>, <td> = à garder
    - des attributs XBRL dans les balises standard = à ignorer

    Cette fonction extrait uniquement le texte humainement lisible.
    """
    # 1. Supprimer les blocs entiers qu'on ne veut pas
    # Script, style, XBRL context (données non narratives)
    cleaned = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<style[^>]*>.*?</style>', ' ', cleaned, flags=re.DOTALL | re.IGNORECASE)

    # 2. Supprimer les blocs XBRL hidden (données structurées, pas du texte)
    # Les <div style="display:none"> contiennent souvent les données XBRL
    cleaned = re.sub(r'<div[^>]*display\s*:\s*none[^>]*>.*?</div>', ' ', cleaned, flags=re.DOTALL | re.IGNORECASE)

    # 3. Supprimer les balises XBRL inline mais GARDER leur contenu textuel
    # <ix:nonFraction ...>1,234</ix:nonFraction> → 1,234
    # <ix:nonNumeric ...>Some text</ix:nonNumeric> → Some text
    cleaned = re.sub(r'<ix:[^>]*>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'</ix:[^>]*>', '', cleaned, flags=re.IGNORECASE)

    # 4. Supprimer les balises XBRL contextuelles (xbrli:context, xbrli:unit, etc.)
    # Ces blocs ne contiennent PAS de texte narratif, juste des IDs et dates
    cleaned = re.sub(r'<xbrli:[^>]*>.*?</xbrli:[^>]*>', ' ', cleaned, flags=re.DOTALL | re.IGNORECASE)

    # 5. Remplacer les balises de block par des newlines pour garder la structure
    cleaned = re.sub(r'</?(p|div|tr|br|h[1-6]|li|section|article)[^>]*>', '\n', cleaned, flags=re.IGNORECASE)
    # Balises td/th → tab (colonnes de tableau)
    cleaned = re.sub(r'</?(td|th)[^>]*>', '\t', cleaned, flags=re.IGNORECASE)

    # 6. Supprimer toutes les balises HTML restantes
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)

    # 7. Décoder les entités HTML
    try:
        import html as html_mod
        cleaned = html_mod.unescape(cleaned)
    except Exception:
        pass

    # 8. Nettoyer les espaces multiples et lignes vides
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # espaces multiples → un seul
    cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)  # lignes vides multiples → une seule
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # max 2 newlines consécutifs

    # 9. Supprimer les lignes qui sont juste des nombres/dates isolés (résidus XBRL)
    lines = cleaned.split('\n')
    filtered = []
    for line in lines:
        stripped = line.strip()
        # Skip lignes trop courtes (< 10 chars) sauf si c'est un nombre avec contexte
        if len(stripped) < 10:
            continue
        # Skip lignes qui sont juste des dates XBRL (2025-12-31, 0000019617, etc.)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', stripped):
            continue
        if re.match(r'^\d{10,}$', stripped):
            continue
        # Skip lignes qui sont des identifiants XBRL (us-gaap:*, jpm:*, etc.)
        if re.match(r'^[a-z-]+:[A-Za-z]+', stripped):
            continue
        filtered.append(line)

    return '\n'.join(filtered)


def fetch_10k_text(ticker: str, max_pages: int = 50) -> Optional[str]:
    """Télécharge et extrait le texte du dernier 10-K.

    Retourne le texte brut (limité à max_pages) ou None si échec.
    """
    url = _get_latest_10k_url(ticker)
    if not url:
        log.warning(f"[edgar] Pas de 10-K trouvé pour {ticker}")
        return None

    try:
        import requests
        log.info(f"[edgar] Fetch 10-K {ticker}: {url[:80]}...")
        resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")

        # Si c'est un HTML (filing viewer), extraire le texte propre
        if "html" in content_type or url.endswith(".htm") or url.endswith(".html"):
            full_text = _clean_html_to_text(resp.text)

        # Si c'est un PDF
        elif url.endswith(".pdf") or "pdf" in content_type:
            try:
                import pdfplumber
                pdf = pdfplumber.open(io.BytesIO(resp.content))
                pages = pdf.pages[:max_pages]
                full_text = "\n\n".join(p.extract_text() or "" for p in pages)
            except Exception as _pe:
                log.warning(f"[edgar] PDF parse failed: {_pe}")
                return None
        else:
            full_text = resp.text

        # Limiter la taille (LLM context)
        if len(full_text) > 200_000:
            full_text = full_text[:200_000]

        log.info(f"[edgar] 10-K {ticker}: {len(full_text)} chars extraits")
        return full_text

    except Exception as e:
        log.warning(f"[edgar] Fetch 10-K failed for {ticker}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTION — Pages pertinentes par secteur
# ═══════════════════════════════════════════════════════════════════════════════

# Mots-clés pour localiser les sections pertinentes par profil sectoriel
_KEYWORDS_BY_PROFILE = {
    "BANK": [
        "net interest margin", "nim", "net interest income", "cet1",
        "common equity tier", "npl", "non-performing", "nonperforming",
        "provision for credit", "cost-to-income", "efficiency ratio",
        "tier 1 capital", "risk-weighted", "liquidity coverage",
    ],
    "INSURANCE": [
        "combined ratio", "loss ratio", "expense ratio", "net premiums",
        "solvency", "embedded value", "policyholder", "underwriting",
        "claims", "reserve", "statutory capital",
    ],
    "REIT": [
        "funds from operations", "ffo", "affo", "adjusted funds",
        "net operating income", "noi", "occupancy", "same-store",
        "same-property", "cap rate", "capitalization rate",
        "weighted average lease term", "walt", "nav", "net asset value",
    ],
    "UTILITY": [
        "rate base", "regulated asset", "rab", "allowed return",
        "allowed roe", "rate case", "regulatory", "tariff",
        "rate of return", "capital expenditure program",
    ],
    "OIL_GAS": [
        "proved reserves", "probable reserves", "production",
        "barrels of oil equivalent", "boe", "finding and development",
        "f&d cost", "reserve replacement", "breakeven",
        "lifting cost", "netback",
    ],
}


def _extract_relevant_sections(full_text: str, profile: str, max_chars: int = 15000) -> str:
    """Extrait les sections pertinentes du 10-K pour le profil sectoriel.

    Parcourt le texte par blocs de ~500 caractères et retient ceux qui
    contiennent des mots-clés sectoriels. Retourne un texte condensé
    de max_chars caractères.
    """
    keywords = _KEYWORDS_BY_PROFILE.get(profile, [])
    if not keywords:
        return full_text[:max_chars]

    text_lower = full_text.lower()
    block_size = 500
    scored_blocks = []

    for i in range(0, len(full_text), block_size):
        block = full_text[i:i + block_size]
        block_lower = text_lower[i:i + block_size]
        score = sum(1 for kw in keywords if kw in block_lower)
        if score > 0:
            scored_blocks.append((score, block))

    # Trier par pertinence et prendre les meilleurs blocs
    scored_blocks.sort(key=lambda x: x[0], reverse=True)
    result = []
    total = 0
    for score, block in scored_blocks:
        if total + len(block) > max_chars:
            break
        result.append(block)
        total += len(block)

    return "\n...\n".join(result) if result else full_text[:max_chars]


# ═══════════════════════════════════════════════════════════════════════════════
# LLM — Extraction structurée
# ═══════════════════════════════════════════════════════════════════════════════

_EXTRACTION_SCHEMAS = {
    "BANK": {
        "cet1_ratio": "CET1 ratio (Common Equity Tier 1) en pourcentage (ex: 15.2)",
        "npl_ratio": "NPL ratio (Non-Performing Loans / Total Loans) en pourcentage (ex: 0.6)",
        "nim": "Net Interest Margin en pourcentage (ex: 2.8)",
        "cost_income": "Cost-to-Income ratio (Efficiency Ratio) en pourcentage (ex: 55.3)",
        "lcr": "Liquidity Coverage Ratio en pourcentage (ex: 130)",
        "rote": "Return on Tangible Equity en pourcentage (ex: 18.5)",
        "tier1_ratio": "Tier 1 Capital Ratio en pourcentage (ex: 16.8)",
    },
    "INSURANCE": {
        "combined_ratio": "Combined Ratio en pourcentage (ex: 95.2)",
        "loss_ratio": "Loss Ratio en pourcentage (ex: 62.5)",
        "expense_ratio": "Expense Ratio en pourcentage (ex: 32.7)",
        "solvency_ratio": "Solvency II ratio ou RBC ratio en pourcentage (ex: 210)",
        "net_premiums_written": "Net Premiums Written en millions (ex: 45000)",
    },
    "REIT": {
        "ffo": "Funds From Operations (FFO) en millions (ex: 5420)",
        "affo": "Adjusted Funds From Operations (AFFO) en millions (ex: 4850)",
        "ffo_per_share": "FFO per share en dollars (ex: 5.82)",
        "occupancy": "Occupancy Rate en pourcentage (ex: 96.5)",
        "same_store_noi_growth": "Same-Store NOI Growth en pourcentage (ex: 3.2)",
        "walt": "Weighted Average Lease Term en annees (ex: 5.1)",
        "nav_per_share": "Net Asset Value per share en dollars (ex: 135.50)",
    },
    "UTILITY": {
        "rate_base": "Regulated Asset Base (Rate Base) en millions (ex: 52000)",
        "allowed_roe": "Allowed Return on Equity en pourcentage (ex: 9.5)",
        "capex_program": "Capital Expenditure Program total en millions (ex: 15000)",
        "earned_roe": "Earned ROE en pourcentage (ex: 10.2)",
    },
    "OIL_GAS": {
        "proved_reserves": "Proved Reserves (1P) en millions de barils equivalent (ex: 2500)",
        "production_boed": "Production en milliers de barils equivalent par jour (ex: 450)",
        "reserve_life": "Reserve Life (Reserves / Production annuelle) en annees (ex: 12.5)",
        "finding_dev_cost": "Finding & Development Cost en dollars par BOE (ex: 15.50)",
        "breakeven_wti": "Breakeven WTI price en dollars par baril (ex: 45)",
    },
}


def extract_sector_metrics(ticker: str, profile: str) -> dict:
    """Pipeline complet : EDGAR fetch → extraction sections → LLM parsing.

    Args:
        ticker  : ticker US (ex: JPM, PLD, MET)
        profile : BANK, INSURANCE, REIT, UTILITY, OIL_GAS

    Returns:
        dict de métriques extraites. Clés = schema keys, valeurs = float ou None.
    """
    if profile not in _EXTRACTION_SCHEMAS:
        log.info(f"[edgar] Profil {profile} n'a pas de schema d'extraction")
        return {}

    schema = _EXTRACTION_SCHEMAS[profile]

    # 1. Fetch 10-K
    t0 = time.time()
    full_text = fetch_10k_text(ticker)
    if not full_text:
        return {}

    # 2. Extraire les sections pertinentes
    relevant = _extract_relevant_sections(full_text, profile, max_chars=12000)
    if len(relevant) < 100:
        log.warning(f"[edgar] Sections pertinentes trop courtes pour {ticker} ({profile})")
        return {}

    # 3. LLM extraction
    try:
        from core.llm_provider import llm_call
    except ImportError:
        log.warning("[edgar] llm_call not available")
        return {}

    schema_desc = "\n".join(f'  "{k}": {v}' for k, v in schema.items())
    prompt = (
        f"Tu es un analyste financier senior. Extrait les metriques suivantes "
        f"du document 10-K de {ticker} (profil {profile}).\n\n"
        f"DOCUMENT (extraits pertinents) :\n"
        f"---\n{relevant[:10000]}\n---\n\n"
        f"Metriques a extraire :\n{schema_desc}\n\n"
        f"REGLES :\n"
        f"- Retourne UNIQUEMENT un JSON valide avec les cles ci-dessus\n"
        f"- Valeurs numeriques (float), pas de texte\n"
        f"- Si une metrique n'est pas trouvee dans le document, mettre null\n"
        f"- Ne pas inventer de valeurs — uniquement ce qui est dans le document\n"
        f"- Les pourcentages sont en valeur absolue (15.2 pas 0.152)\n\n"
        f"JSON :"
    )

    try:
        raw = llm_call(prompt, phase="critical", max_tokens=500)
        if not raw:
            return {}

        # Parser le JSON
        import json
        # Nettoyer la réponse (enlever markdown code blocks si présent)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```\w*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned)
        cleaned = cleaned.strip()

        result = json.loads(cleaned)
        # Convertir en float et filtrer les None
        metrics = {}
        for k, v in result.items():
            if k in schema and v is not None:
                try:
                    metrics[k] = float(v)
                except (TypeError, ValueError):
                    pass

        elapsed = time.time() - t0
        log.info(f"[edgar] {ticker} ({profile}): {len(metrics)} metriques extraites en {elapsed:.1f}s")
        return metrics

    except Exception as e:
        log.warning(f"[edgar] LLM extraction failed for {ticker}: {e}")
        return {}
