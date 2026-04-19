"""i18n côté backend FinSight IA.

Fournit :
- LANGUAGE_NAMES : nom des langues pour intégrer dans les prompts LLM
- CURRENCY_SYMBOLS : symboles + code devises
- system_language_directive(lang) : directive à insérer dans system prompt
- format_currency(value, ccy, lang) : format sortie cohérent par locale
- t(lang, key) : traduction de strings (chargées depuis core/i18n/messages_*.json)
- pcg_to_ifrs / ifrs_libelle(field, lang) : mapping libellés comptables PCG → IFRS
  pour les writers PDF/PPTX/XLSX
"""

from __future__ import annotations

import json
import locale as _pylocale
from functools import lru_cache
from pathlib import Path
from typing import Optional

SUPPORTED_LANGUAGES = ("fr", "en", "es", "de", "it", "pt")
SUPPORTED_CURRENCIES = ("EUR", "USD", "GBP", "CHF", "JPY", "CAD")
DEFAULT_LANGUAGE = "fr"
DEFAULT_CURRENCY = "EUR"

# Nom natif de chaque langue, à insérer dans les prompts LLM
LANGUAGE_NAMES = {
    "fr": "français",
    "en": "English",
    "es": "español",
    "de": "Deutsch",
    "it": "italiano",
    "pt": "português",
}

# Symbole pour formatage compact
CURRENCY_SYMBOLS = {
    "EUR": "€", "USD": "$", "GBP": "£",
    "CHF": "CHF", "JPY": "¥", "CAD": "C$",
}

# BCP-47 locales pour formatage
LOCALE_BCP47 = {
    "fr": "fr_FR", "en": "en_US", "es": "es_ES",
    "de": "de_DE", "it": "it_IT", "pt": "pt_PT",
}


def normalize_language(lang: Optional[str]) -> str:
    if not lang:
        return DEFAULT_LANGUAGE
    lang = lang.lower().strip()[:2]
    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def normalize_currency(ccy: Optional[str]) -> str:
    if not ccy:
        return DEFAULT_CURRENCY
    ccy = ccy.upper().strip()[:3]
    return ccy if ccy in SUPPORTED_CURRENCIES else DEFAULT_CURRENCY


def system_language_directive(lang: str) -> str:
    """Directive à insérer dans le system prompt LLM pour qu'il réponde dans
    la langue choisie. Mention explicite des accents pour le français.
    """
    lang = normalize_language(lang)
    if lang == "fr":
        return (
            "Tu réponds STRICTEMENT en français correct avec accents (é è ê à ç) "
            "et apostrophes droites. Pas d'anglicismes inutiles."
        )
    name = LANGUAGE_NAMES[lang]
    return (
        f"You MUST reply strictly in {name}. Use proper grammar, accents and "
        "punctuation native to that language. Do not mix languages."
    )


_FX_FALLBACK = {
    # Taux moyens mars-avril 2026 (exchange rate static fallback)
    ("EUR", "USD"): 1.08, ("EUR", "GBP"): 0.86, ("EUR", "CHF"): 0.95,
    ("EUR", "JPY"): 162.0, ("EUR", "CAD"): 1.47,
    ("USD", "EUR"): 0.93, ("USD", "GBP"): 0.79, ("USD", "CHF"): 0.88,
    ("USD", "JPY"): 150.0, ("USD", "CAD"): 1.36,
    ("GBP", "EUR"): 1.17, ("GBP", "USD"): 1.27, ("GBP", "CHF"): 1.11,
    ("CHF", "EUR"): 1.05, ("CHF", "USD"): 1.14,
    ("JPY", "EUR"): 0.0062, ("JPY", "USD"): 0.0067,
    ("CAD", "EUR"): 0.68, ("CAD", "USD"): 0.74,
}

_FX_CACHE: dict[tuple[str, str], tuple[float, float]] = {}  # (from,to) → (rate, ts_secondes)
_FX_TTL = 3600  # 1h


def get_fx_rate(from_ccy: str, to_ccy: str) -> float:
    """Récupère le taux from→to. Cache 1h. Fallback statique si offline."""
    import time as _time
    f = normalize_currency(from_ccy)
    t = normalize_currency(to_ccy)
    if f == t:
        return 1.0
    key = (f, t)
    cached = _FX_CACHE.get(key)
    now = _time.time()
    if cached and now - cached[1] < _FX_TTL:
        return cached[0]
    # Tentative API live
    try:
        import requests as _rq
        r = _rq.get(
            f"https://api.exchangerate.host/latest",
            params={"base": f, "symbols": t},
            timeout=4,
        )
        if r.status_code == 200:
            data = r.json()
            rate = float(data.get("rates", {}).get(t, 0))
            if rate > 0:
                _FX_CACHE[key] = (rate, now)
                return rate
    except Exception:
        pass
    # Fallback statique
    rate = _FX_FALLBACK.get(key) or _FX_FALLBACK.get((t, f))
    if rate:
        return rate if key in _FX_FALLBACK else 1.0 / rate
    return 1.0


def convert_amount(value: float, from_ccy: str = "EUR", to_ccy: str = "EUR") -> float:
    """Convertit un montant from_ccy → to_ccy via taux live (cache 1h)."""
    if value is None or not isinstance(value, (int, float)):
        return value
    if normalize_currency(from_ccy) == normalize_currency(to_ccy):
        return float(value)
    return float(value) * get_fx_rate(from_ccy, to_ccy)


def format_currency_amount(value: float, currency: str = "EUR", lang: str = "fr",
                           compact: bool = True, from_currency: str = "EUR") -> str:
    """Formate un montant monétaire pour affichage (compact = 4,2 M€).
    Si `from_currency` ≠ `currency`, conversion via taux de change live.
    """
    if value is None:
        return "—"
    currency = normalize_currency(currency)
    if from_currency and normalize_currency(from_currency) != currency:
        value = convert_amount(value, from_currency, currency)
    symbol = CURRENCY_SYMBOLS[currency]
    abs_v = abs(value)

    # Choix unité compacte
    if compact and abs_v >= 1e9:
        unit, div = ("Md", 1e9) if lang == "fr" else ("B", 1e9)
        return f"{value / div:.1f} {unit} {symbol}".strip()
    if compact and abs_v >= 1e6:
        return f"{value / 1e6:.1f} M {symbol}".strip()
    if compact and abs_v >= 1e3:
        return f"{value / 1e3:.0f} k {symbol}".strip()

    # Formatage par locale
    try:
        _pylocale.setlocale(_pylocale.LC_ALL, LOCALE_BCP47[lang])
        formatted = _pylocale.format_string("%.0f", value, grouping=True)
    except _pylocale.Error:
        formatted = f"{value:,.0f}".replace(",", " " if lang == "fr" else ",")
    return f"{formatted} {symbol}".strip()


# ─── Strings i18n côté backend (outputs PDF/PPTX/XLSX) ────────────────────

@lru_cache(maxsize=None)
def _load_messages(lang: str) -> dict:
    p = Path(__file__).parent / "i18n" / f"messages_{lang}.json"
    if not p.exists():
        # fallback FR
        p = Path(__file__).parent / "i18n" / "messages_fr.json"
        if not p.exists():
            return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def t(lang: str, key: str, default: Optional[str] = None) -> str:
    """Lookup t("fr", "kpi.revenue") → "Chiffre d'affaires".
    Si la clé manque, fallback FR puis renvoie default ou la clé brute.
    """
    lang = normalize_language(lang)
    parts = key.split(".")

    def _walk(d: dict) -> Optional[str]:
        cur: object = d
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return None
        return cur if isinstance(cur, str) else None

    val = _walk(_load_messages(lang))
    if val is not None:
        return val
    if lang != "fr":
        val = _walk(_load_messages("fr"))
        if val is not None:
            return val
    return default if default is not None else key


# ─── Mapping libellés comptables PCG (FR) → IFRS (universel) ─────────────

# Pour les analyses PME françaises (Pappers/INPI), les libellés natifs sont en
# PCG. Quand l'user choisit EN/DE/ES/etc., on traduit vers les équivalents
# IFRS standards (utilisés par Bloomberg, FactSet, S&P).
#
# Note : certains termes sont une approximation pratique :
#   - "EBE" (Excédent Brut d'Exploitation) ≈ EBITDA (différence technique
#     mineure : EBE exclut les transferts de charges)
#   - "Capacité d'autofinancement" ≈ Cash from operations (proxy)

PCG_FIELDS = {
    # Compte de résultat
    "chiffre_affaires": {
        "fr": "Chiffre d'affaires", "en": "Revenue", "es": "Ingresos",
        "de": "Umsatz", "it": "Ricavi", "pt": "Receita",
    },
    "production_vendue_biens": {
        "fr": "Production vendue (biens)", "en": "Goods sold",
        "es": "Bienes vendidos", "de": "Warenumsatz",
        "it": "Beni venduti", "pt": "Bens vendidos",
    },
    "production_vendue_services": {
        "fr": "Prestations de services", "en": "Services revenue",
        "es": "Ingresos por servicios", "de": "Dienstleistungserlöse",
        "it": "Ricavi da servizi", "pt": "Receita de serviços",
    },
    "achats_marchandises": {
        "fr": "Achats de marchandises", "en": "Cost of goods purchased",
        "es": "Compras de mercancías", "de": "Wareneinkauf",
        "it": "Acquisti di merci", "pt": "Compras de mercadorias",
    },
    "autres_achats_charges_externes": {
        "fr": "Autres achats et charges externes",
        "en": "Other external expenses", "es": "Otros gastos externos",
        "de": "Sonstige externe Aufwendungen", "it": "Altri costi esterni",
        "pt": "Outras despesas externas",
    },
    "salaires_traitements": {
        "fr": "Salaires et traitements", "en": "Salaries and wages",
        "es": "Salarios y sueldos", "de": "Löhne und Gehälter",
        "it": "Stipendi e salari", "pt": "Salários e ordenados",
    },
    "charges_sociales": {
        "fr": "Charges sociales", "en": "Social security contributions",
        "es": "Cargas sociales", "de": "Sozialabgaben",
        "it": "Oneri sociali", "pt": "Encargos sociais",
    },
    "dotations_amortissements": {
        "fr": "Dotations aux amortissements", "en": "Depreciation & amortization",
        "es": "Amortizaciones", "de": "Abschreibungen",
        "it": "Ammortamenti", "pt": "Amortizações",
    },
    "ebe_estime": {
        "fr": "Excédent brut d'exploitation (EBE)",
        "en": "EBITDA",
        "es": "EBITDA", "de": "EBITDA", "it": "EBITDA", "pt": "EBITDA",
    },
    "resultat_exploitation": {
        "fr": "Résultat d'exploitation", "en": "Operating income (EBIT)",
        "es": "Resultado de explotación", "de": "Betriebsergebnis",
        "it": "Risultato operativo", "pt": "Resultado operacional",
    },
    "resultat_financier": {
        "fr": "Résultat financier", "en": "Financial result",
        "es": "Resultado financiero", "de": "Finanzergebnis",
        "it": "Risultato finanziario", "pt": "Resultado financeiro",
    },
    "resultat_courant": {
        "fr": "Résultat courant avant impôts",
        "en": "Profit before tax (PBT)", "es": "Beneficio antes de impuestos",
        "de": "Ergebnis vor Steuern", "it": "Utile ante imposte",
        "pt": "Lucro antes de impostos",
    },
    "impots_benefices": {
        "fr": "Impôts sur les bénéfices", "en": "Income tax",
        "es": "Impuesto de sociedades", "de": "Ertragsteuern",
        "it": "Imposte sul reddito", "pt": "Imposto sobre o rendimento",
    },
    "resultat_net": {
        "fr": "Résultat net", "en": "Net income",
        "es": "Beneficio neto", "de": "Jahresüberschuss",
        "it": "Utile netto", "pt": "Lucro líquido",
    },
    # Bilan — Actif
    "actif_immobilise": {
        "fr": "Actif immobilisé", "en": "Non-current assets",
        "es": "Activo no corriente", "de": "Anlagevermögen",
        "it": "Immobilizzazioni", "pt": "Ativo não corrente",
    },
    "immobilisations_incorporelles": {
        "fr": "Immobilisations incorporelles", "en": "Intangible assets",
        "es": "Activos intangibles", "de": "Immaterielle Vermögenswerte",
        "it": "Immobilizzazioni immateriali", "pt": "Ativos intangíveis",
    },
    "immobilisations_corporelles": {
        "fr": "Immobilisations corporelles", "en": "Property, plant & equipment (PP&E)",
        "es": "Inmovilizado material", "de": "Sachanlagen",
        "it": "Immobilizzazioni materiali", "pt": "Ativos fixos tangíveis",
    },
    "stocks": {
        "fr": "Stocks", "en": "Inventory", "es": "Existencias",
        "de": "Vorräte", "it": "Rimanenze", "pt": "Inventários",
    },
    "creances_clients": {
        "fr": "Créances clients", "en": "Trade receivables",
        "es": "Cuentas por cobrar", "de": "Forderungen aus Lieferungen",
        "it": "Crediti commerciali", "pt": "Contas a receber",
    },
    "disponibilites": {
        "fr": "Disponibilités", "en": "Cash & equivalents",
        "es": "Efectivo y equivalentes", "de": "Liquide Mittel",
        "it": "Disponibilità liquide", "pt": "Caixa e equivalentes",
    },
    "total_actif": {
        "fr": "Total actif", "en": "Total assets", "es": "Activo total",
        "de": "Bilanzsumme", "it": "Attivo totale", "pt": "Ativo total",
    },
    # Bilan — Passif
    "capitaux_propres": {
        "fr": "Capitaux propres", "en": "Equity", "es": "Patrimonio neto",
        "de": "Eigenkapital", "it": "Patrimonio netto", "pt": "Capital próprio",
    },
    "capital_social": {
        "fr": "Capital social", "en": "Share capital", "es": "Capital social",
        "de": "Grundkapital", "it": "Capitale sociale", "pt": "Capital social",
    },
    "reserves": {
        "fr": "Réserves", "en": "Reserves", "es": "Reservas",
        "de": "Rücklagen", "it": "Riserve", "pt": "Reservas",
    },
    "dettes_financieres": {
        "fr": "Dettes financières", "en": "Financial debt",
        "es": "Deuda financiera", "de": "Finanzverbindlichkeiten",
        "it": "Debiti finanziari", "pt": "Dívida financeira",
    },
    "dettes_fournisseurs": {
        "fr": "Dettes fournisseurs", "en": "Trade payables",
        "es": "Cuentas por pagar", "de": "Verbindlichkeiten aus Lieferungen",
        "it": "Debiti commerciali", "pt": "Contas a pagar",
    },
    "total_passif": {
        "fr": "Total passif", "en": "Total liabilities & equity",
        "es": "Pasivo total", "de": "Bilanzsumme",
        "it": "Passivo totale", "pt": "Passivo total",
    },
}


def field_label(field: str, lang: str) -> str:
    """Renvoie le libellé du champ comptable dans la langue voulue.
    field = clé interne YearAccounts (chiffre_affaires, capitaux_propres, …)
    """
    lang = normalize_language(lang)
    spec = PCG_FIELDS.get(field)
    if not spec:
        # Fallback : libellé brut humanisé
        return field.replace("_", " ").capitalize()
    return spec.get(lang) or spec.get("en") or spec.get("fr") or field
