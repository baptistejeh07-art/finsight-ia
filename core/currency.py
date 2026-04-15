# -*- coding: utf-8 -*-
"""
core/currency.py — Conversion de devise centralisée pour FinSight IA.

Phase A refonte devise (#182 Baptiste) : expose une API simple pour convertir
tout montant monétaire dans la devise cible (EUR par défaut) avant affichage
dans les outputs (UI, PDF, PPTX, XLSX).

ARCHITECTURE :

- `DEFAULT_TARGET_CURRENCY = "EUR"` — constante modifiable plus tard via
  settings utilisateur (paramètre user `st.session_state.user_currency`).

- `get_target_currency()` — lit la devise cible courante depuis session_state
  si Streamlit est actif, sinon fallback DEFAULT_TARGET_CURRENCY.

- `fetch_fx_rate(from_ccy, to_ccy)` — retourne le taux spot depuis yfinance
  (`EURUSD=X`, `EURGBP=X`, etc.) avec cache 1h module-level. Zéro nouvelle
  API key, gratuit illimité.

- `convert(amount, from_ccy, to_ccy=None)` — API principale. Si to_ccy None,
  utilise get_target_currency(). Gère les cas spéciaux :
  - GBp (pence britanniques) → divise par 100 pour avoir GBP
  - ILa (agorot israéliens) → divise par 100
  - KRw (South Korean won en cents) → pas de conversion connue
  - Devise exotique non supportée → fallback 1:1 avec warning

- `convert_batch(amounts_dict, from_ccy, to_ccy)` — convertit plusieurs
  montants d'un coup en réutilisant le même taux FX (1 appel au lieu de N).

PHILOSOPHIE :
- Le **pipeline interne** reste en devise native (snapshot, ratios, etc.)
- La **conversion se fait uniquement au MOMENT DE L'AFFICHAGE** dans les
  writers (excel_writer, pdf_writer, pptx_writer) et l'UI (app.py)
- Ça permet à la Phase B de propager la conversion à tous les outputs
  sans toucher au pipeline LangGraph

USAGE :

    from core.currency import convert, get_target_currency

    # Dans l'UI app.py :
    price_eur = convert(mkt.share_price, ci.currency)  # USD → EUR automatique
    target_ccy = get_target_currency()  # "EUR" (ou user choice)
    st.write(f"{price_eur:,.2f} {target_ccy}")

    # Dans comparables_source.py :
    peer_price_eur = convert(peer_price_usd, peer.currency)
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.yfinance_cache import get_ticker

log = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_TARGET_CURRENCY = "EUR"

# Devises supportées (normalisation ISO 4217 + cas yfinance)
# yfinance retourne parfois "GBP" et parfois "GBp" (pence, 1/100 GBP)
_SUPPORTED_CURRENCIES = {
    "USD", "EUR", "GBP", "GBp",  # GBp = pence britanniques
    "CHF", "JPY", "CAD", "AUD", "NZD",
    "HKD", "SGD", "CNY", "CNH", "INR", "KRW", "TWD",
    "SEK", "NOK", "DKK", "PLN", "CZK", "HUF",
    "BRL", "MXN", "ARS",
    "ZAR",
    "ILA", "ILS",  # ILA = agorot (1/100 ILS)
}

# Cache FX : {(from, to): (rate, timestamp)}
_FX_CACHE: dict[tuple[str, str], tuple[float, float]] = {}
_FX_TTL_SEC = 60 * 60  # 1 heure


# ═════════════════════════════════════════════════════════════════════════════
# NORMALISATION
# ═════════════════════════════════════════════════════════════════════════════

def _normalize_currency(ccy: Optional[str]) -> tuple[str, float]:
    """Normalise une devise yfinance et retourne (ccy_iso, multiplicateur).

    Le multiplicateur gère les sous-unités :
    - GBp (pence) → ("GBP", 0.01)
    - ILA (agorot) → ("ILS", 0.01)
    - Autres → (ccy_upper, 1.0)

    Utilisé en amont de convert() : un peer britannique avec share_price
    en GBp doit être divisé par 100 pour obtenir des GBP avant FX.
    """
    if not ccy:
        return ("USD", 1.0)  # fallback conservateur
    s = str(ccy).strip()
    if s == "GBp":
        return ("GBP", 0.01)
    if s == "ILA":
        return ("ILS", 0.01)
    return (s.upper(), 1.0)


# ═════════════════════════════════════════════════════════════════════════════
# TARGET CURRENCY (session / global)
# ═════════════════════════════════════════════════════════════════════════════

def get_target_currency() -> str:
    """Retourne la devise cible courante.

    Ordre de priorité :
    1. `st.session_state.user_currency` si Streamlit est actif et la clé existe
    2. Variable globale `_override_target_currency` (pour tests)
    3. `DEFAULT_TARGET_CURRENCY` (= "EUR")
    """
    # Tente de lire le setting user Streamlit
    try:
        import streamlit as _st
        _user_ccy = _st.session_state.get("user_currency")
        if _user_ccy:
            return str(_user_ccy).upper()
    except Exception:
        pass

    if _OVERRIDE_TARGET_CURRENCY:
        return _OVERRIDE_TARGET_CURRENCY

    return DEFAULT_TARGET_CURRENCY


_OVERRIDE_TARGET_CURRENCY: Optional[str] = None


def set_target_currency_override(ccy: Optional[str]) -> None:
    """Override global (pour tests ou CLI). Ne touche pas à session_state."""
    global _OVERRIDE_TARGET_CURRENCY
    _OVERRIDE_TARGET_CURRENCY = ccy


# ═════════════════════════════════════════════════════════════════════════════
# FX RATE FETCH (yfinance + cache 1h)
# ═════════════════════════════════════════════════════════════════════════════

def fetch_fx_rate(from_ccy: str, to_ccy: str) -> Optional[float]:
    """Retourne le taux spot {from}→{to} via yfinance, avec cache 1h.

    Retourne `None` si le taux ne peut pas être récupéré (réseau, devise
    inconnue, etc.) — l'appelant doit gérer le fallback.

    Args:
        from_ccy : code ISO 3 chars (USD, EUR, GBP...)
        to_ccy   : code ISO 3 chars

    Returns:
        float : multiplicateur (amount * rate = amount dans to_ccy)
        None  : échec fetch
    """
    if not from_ccy or not to_ccy:
        return None

    from_ccy = from_ccy.upper()
    to_ccy = to_ccy.upper()

    # Identité : pas de conversion nécessaire
    if from_ccy == to_ccy:
        return 1.0

    # Cache hit
    now = time.time()
    key = (from_ccy, to_ccy)
    if key in _FX_CACHE:
        rate, ts = _FX_CACHE[key]
        if (now - ts) < _FX_TTL_SEC:
            return rate

    # Fetch via yfinance
    # Symbole conventionnel : {FROM}{TO}=X (ex: EURUSD=X = 1 EUR en USD)
    # Pour convertir FROM → TO, on veut {FROM}{TO}=X
    ticker_symbol = f"{from_ccy}{to_ccy}=X"
    rate = None
    try:
        import yfinance as yf
        tk = get_ticker(ticker_symbol)
        # fast_info est plus fiable que info pour les FX
        try:
            fi = tk.fast_info
            rate = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
        except Exception:
            pass
        if rate is None:
            info = tk.info or {}
            rate = info.get("regularMarketPrice") or info.get("ask") or info.get("bid")
        if rate is None:
            # Dernier recours : download 1 jour
            import pandas as _pd  # noqa: F401
            hist = tk.history(period="5d")
            if not hist.empty and "Close" in hist.columns:
                rate = float(hist["Close"].iloc[-1])
    except Exception as e:
        log.warning(f"[currency] fetch_fx_rate({from_ccy}→{to_ccy}) failed: {e}")
        rate = None

    if rate is None or rate <= 0:
        # Tenter l'inverse : {TO}{FROM}=X puis 1/rate
        try:
            import yfinance as yf
            tk_inv = get_ticker(f"{to_ccy}{from_ccy}=X")
            fi = tk_inv.fast_info
            inv_rate = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
            if inv_rate and inv_rate > 0:
                rate = 1.0 / float(inv_rate)
        except Exception:
            pass

    if rate is None or rate <= 0:
        log.warning(
            f"[currency] Impossible de récupérer le taux {from_ccy}→{to_ccy}"
        )
        return None

    # Cache + return
    _FX_CACHE[key] = (float(rate), now)
    log.debug(f"[currency] FX {from_ccy}→{to_ccy} = {rate:.4f} (cached)")
    return float(rate)


def clear_fx_cache() -> None:
    """Clear le cache FX. Utile pour les tests unitaires."""
    _FX_CACHE.clear()


# ═════════════════════════════════════════════════════════════════════════════
# CONVERSION API
# ═════════════════════════════════════════════════════════════════════════════

def convert(
    amount: Optional[float],
    from_ccy: Optional[str],
    to_ccy: Optional[str] = None,
) -> Optional[float]:
    """Convertit un montant d'une devise à une autre.

    API principale — à utiliser partout dans les writers et l'UI pour
    afficher des montants dans la devise cible (EUR par défaut).

    Args:
        amount    : montant source (ou None)
        from_ccy  : devise source (ex: "USD", "EUR", "GBp"). None → USD fallback
        to_ccy    : devise cible. None → get_target_currency() = EUR par défaut

    Returns:
        float : montant converti dans to_ccy
        None  : si amount est None, ou si la conversion échoue totalement

    Exemples :
        convert(100, "USD", "EUR")    # → ~92.0 (selon FX)
        convert(100, "GBp", "EUR")    # → ~1.15 (pence × 0.01 × GBP/EUR)
        convert(100, "EUR", "EUR")    # → 100.0 (identité)
        convert(None, "USD")          # → None (propage)
    """
    if amount is None:
        return None

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None

    # Normalise la source (gère GBp → GBP × 0.01)
    src_ccy, src_mult = _normalize_currency(from_ccy)
    amount_normalized = amount * src_mult

    # Target
    tgt_ccy = (to_ccy or get_target_currency()).upper()

    # Identité
    if src_ccy == tgt_ccy:
        return round(amount_normalized, 4)

    # Fetch rate
    rate = fetch_fx_rate(src_ccy, tgt_ccy)
    if rate is None or rate <= 0:
        log.warning(
            f"[currency] Conversion {src_ccy}→{tgt_ccy} impossible "
            f"— fallback 1:1 (montant inchangé)"
        )
        return round(amount_normalized, 4)

    return round(amount_normalized * rate, 4)


def convert_batch(
    amounts: dict,
    from_ccy: Optional[str],
    to_ccy: Optional[str] = None,
) -> dict:
    """Convertit plusieurs montants du même from_ccy d'un coup.

    Plus efficace que convert() N fois : un seul fetch_fx_rate.

    Args:
        amounts  : dict {key: amount} à convertir
        from_ccy : devise source commune
        to_ccy   : devise cible (défaut : target currency)

    Returns:
        dict {key: amount_converted}
    """
    if not amounts:
        return {}

    src_ccy, src_mult = _normalize_currency(from_ccy)
    tgt_ccy = (to_ccy or get_target_currency()).upper()

    # Pas de conversion nécessaire
    if src_ccy == tgt_ccy and src_mult == 1.0:
        return {k: v for k, v in amounts.items()}

    rate = fetch_fx_rate(src_ccy, tgt_ccy) if src_ccy != tgt_ccy else 1.0
    if rate is None or rate <= 0:
        rate = 1.0  # fallback

    out = {}
    for k, v in amounts.items():
        if v is None:
            out[k] = None
            continue
        try:
            fv = float(v)
            out[k] = round(fv * src_mult * rate, 4)
        except (TypeError, ValueError):
            out[k] = None
    return out


# ═════════════════════════════════════════════════════════════════════════════
# LABEL HELPERS (pour affichage)
# ═════════════════════════════════════════════════════════════════════════════

_CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CHF": "Fr",
    "CAD": "C$",
    "AUD": "A$",
    "HKD": "HK$",
    "SGD": "S$",
    "CNY": "¥",
    "CNH": "¥",
    "INR": "₹",
    "KRW": "₩",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "PLN": "zł",
}


def currency_symbol(ccy: Optional[str] = None) -> str:
    """Retourne le symbole d'une devise (ou son code ISO en fallback).

    Exemples : "USD" → "$", "EUR" → "€", "JPY" → "¥", inconnu → code ISO.
    """
    if ccy is None:
        ccy = get_target_currency()
    return _CURRENCY_SYMBOLS.get(ccy.upper(), ccy.upper())