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


# ─── Catégories textuelles renvoyées par les sources tierces (Pappers, BODACC) ─

# Forme juridique : codes officiels INSEE → libellés multilingues
LEGAL_FORMS = {
    "SAS": {"fr": "SAS (Société par actions simplifiée)", "en": "SAS (Simplified joint-stock company)",
            "es": "SAS (Sociedad por acciones simplificada)", "de": "SAS (Vereinfachte AG)",
            "it": "SAS (Società per azioni semplificata)", "pt": "SAS (Sociedade por ações simplificada)"},
    "SASU": {"fr": "SASU (SAS unipersonnelle)", "en": "SASU (Single-shareholder SAS)",
             "es": "SASU (SAS unipersonal)", "de": "SASU (Ein-Gesellschafter-SAS)",
             "it": "SASU (SAS unipersonale)", "pt": "SASU (SAS unipessoal)"},
    "SARL": {"fr": "SARL (Société à responsabilité limitée)", "en": "SARL (Limited liability company)",
             "es": "SARL (Sociedad de responsabilidad limitada)", "de": "SARL (GmbH)",
             "it": "SARL (Srl)", "pt": "SARL (Sociedade por quotas)"},
    "EURL": {"fr": "EURL (SARL unipersonnelle)", "en": "EURL (Single-shareholder LLC)",
             "es": "EURL (SARL unipersonal)", "de": "EURL (Ein-Personen-GmbH)",
             "it": "EURL (Srl unipersonale)", "pt": "EURL (Sociedade unipessoal)"},
    "SA": {"fr": "SA (Société anonyme)", "en": "SA (Public limited company)",
           "es": "SA (Sociedad anónima)", "de": "SA (Aktiengesellschaft)",
           "it": "SA (Società per azioni)", "pt": "SA (Sociedade anónima)"},
    "SNC": {"fr": "SNC (Société en nom collectif)", "en": "SNC (General partnership)",
            "es": "SNC (Sociedad colectiva)", "de": "SNC (Offene Handelsgesellschaft)",
            "it": "SNC (Società in nome collettivo)", "pt": "SNC (Sociedade em nome coletivo)"},
    "SCI": {"fr": "SCI (Société civile immobilière)", "en": "SCI (Real estate civil company)",
            "es": "SCI (Sociedad civil inmobiliaria)", "de": "SCI (Immobilien-Gesellschaft bürgerlichen Rechts)",
            "it": "SCI (Società civile immobiliare)", "pt": "SCI (Sociedade civil imobiliária)"},
    "EI": {"fr": "EI (Entreprise individuelle)", "en": "EI (Sole proprietorship)",
           "es": "EI (Empresario individual)", "de": "EI (Einzelunternehmen)",
           "it": "EI (Ditta individuale)", "pt": "EI (Empresário em nome individual)"},
    "EIRL": {"fr": "EIRL (Entrepreneur individuel à responsabilité limitée)",
             "en": "EIRL (Limited liability sole trader)",
             "es": "EIRL (Empresario individual con responsabilidad limitada)",
             "de": "EIRL (Einzelunternehmer mit beschränkter Haftung)",
             "it": "EIRL (Imprenditore individuale a responsabilità limitata)",
             "pt": "EIRL (Empresário em nome individual de responsabilidade limitada)"},
}


def legal_form_label(form: str, lang: str) -> str:
    """Renvoie le libellé multilingue de la forme juridique."""
    if not form:
        return ""
    lang = normalize_language(lang)
    # Détection simple via mots-clefs (Pappers renvoie des chaînes type "Société par actions simplifiée")
    f_upper = form.upper()
    for code, spec in LEGAL_FORMS.items():
        if code in f_upper or any(part in f_upper for part in [code]):
            return spec.get(lang) or spec.get("en") or spec.get("fr") or form
    # Si pas de match : on retourne tel quel (déjà en FR par Pappers)
    return form


# Qualité dirigeant
DIRECTOR_QUALITIES = {
    "Président": {"fr": "Président", "en": "Chairman", "es": "Presidente",
                  "de": "Vorsitzender", "it": "Presidente", "pt": "Presidente"},
    "Directeur Général": {"fr": "Directeur Général", "en": "Chief Executive Officer (CEO)",
                          "es": "Director General", "de": "Geschäftsführer",
                          "it": "Direttore Generale", "pt": "Diretor-Geral"},
    "Directeur général": {"fr": "Directeur général", "en": "Chief Executive Officer (CEO)",
                          "es": "Director general", "de": "Geschäftsführer",
                          "it": "Direttore generale", "pt": "Diretor-geral"},
    "Gérant": {"fr": "Gérant", "en": "Managing director", "es": "Gerente",
               "de": "Geschäftsführer", "it": "Amministratore", "pt": "Gerente"},
    "Cogérant": {"fr": "Cogérant", "en": "Co-managing director", "es": "Cogerente",
                 "de": "Mit-Geschäftsführer", "it": "Co-amministratore", "pt": "Co-gerente"},
    "Administrateur": {"fr": "Administrateur", "en": "Director", "es": "Administrador",
                       "de": "Verwaltungsratsmitglied", "it": "Amministratore", "pt": "Administrador"},
    "Membre du conseil de surveillance": {"fr": "Membre du conseil de surveillance",
                                          "en": "Supervisory board member",
                                          "es": "Miembro del consejo de supervisión",
                                          "de": "Aufsichtsratsmitglied",
                                          "it": "Membro del consiglio di sorveglianza",
                                          "pt": "Membro do conselho fiscal"},
    "Commissaire aux comptes": {"fr": "Commissaire aux comptes", "en": "Statutory auditor",
                                "es": "Auditor de cuentas", "de": "Abschlussprüfer",
                                "it": "Revisore legale", "pt": "Revisor oficial de contas"},
}


def director_quality_label(quality: str, lang: str) -> str:
    if not quality:
        return ""
    lang = normalize_language(lang)
    spec = DIRECTOR_QUALITIES.get(quality)
    if spec:
        return spec.get(lang) or spec.get("en") or quality
    # Match insensitive case
    for key, spec in DIRECTOR_QUALITIES.items():
        if key.lower() in quality.lower():
            return spec.get(lang) or spec.get("en") or quality
    return quality


# Types de procédures BODACC
BODACC_PROCEDURE_TYPES = {
    "Dépôt des comptes": {"fr": "Dépôt des comptes annuels",
                          "en": "Annual accounts filing",
                          "es": "Depósito de cuentas anuales",
                          "de": "Hinterlegung des Jahresabschlusses",
                          "it": "Deposito del bilancio",
                          "pt": "Depósito de contas anuais"},
    "Procédure collective": {"fr": "Procédure collective",
                             "en": "Insolvency proceedings",
                             "es": "Procedimiento concursal",
                             "de": "Insolvenzverfahren",
                             "it": "Procedura concorsuale",
                             "pt": "Processo de insolvência"},
    "Redressement judiciaire": {"fr": "Redressement judiciaire",
                                "en": "Reorganization proceedings",
                                "es": "Reestructuración judicial",
                                "de": "Sanierungsverfahren",
                                "it": "Concordato preventivo",
                                "pt": "Processo de recuperação judicial"},
    "Liquidation judiciaire": {"fr": "Liquidation judiciaire",
                               "en": "Judicial liquidation",
                               "es": "Liquidación judicial",
                               "de": "Gerichtliche Liquidation",
                               "it": "Liquidazione giudiziale",
                               "pt": "Liquidação judicial"},
    "Sauvegarde": {"fr": "Procédure de sauvegarde",
                   "en": "Safeguard proceedings",
                   "es": "Procedimiento de salvaguarda",
                   "de": "Schutzschirmverfahren",
                   "it": "Procedura di salvaguardia",
                   "pt": "Processo de salvaguarda"},
    "Radiation": {"fr": "Radiation",
                  "en": "Strike-off",
                  "es": "Cancelación",
                  "de": "Löschung",
                  "it": "Cancellazione",
                  "pt": "Cancelamento"},
}


def bodacc_label(typ: str, lang: str) -> str:
    if not typ:
        return ""
    lang = normalize_language(lang)
    for key, spec in BODACC_PROCEDURE_TYPES.items():
        if key.lower() in typ.lower():
            return spec.get(lang) or spec.get("en") or typ
    return typ


# ─── Ratios & KPI labels (tableaux PDF/PPTX) ──────────────────────────────
RATIO_LABELS: dict[str, dict[str, str]] = {
    "marge_brute": {"fr": "Marge brute", "en": "Gross margin",
                    "es": "Margen bruto", "de": "Bruttomarge",
                    "it": "Margine lordo", "pt": "Margem bruta"},
    "marge_ebitda": {"fr": "Marge EBITDA", "en": "EBITDA margin",
                     "es": "Margen EBITDA", "de": "EBITDA-Marge",
                     "it": "Margine EBITDA", "pt": "Margem EBITDA"},
    "marge_nette": {"fr": "Marge nette", "en": "Net margin",
                    "es": "Margen neto", "de": "Nettomarge",
                    "it": "Margine netto", "pt": "Margem líquida"},
    "roce": {"fr": "ROCE", "en": "ROCE",
             "es": "ROCE", "de": "ROCE",
             "it": "ROCE", "pt": "ROCE"},
    "roe": {"fr": "ROE", "en": "ROE",
            "es": "ROE", "de": "ROE",
            "it": "ROE", "pt": "ROE"},
    "dette_nette_ebitda": {"fr": "Dette nette / EBITDA", "en": "Net debt / EBITDA",
                           "es": "Deuda neta / EBITDA", "de": "Nettoverschuldung / EBITDA",
                           "it": "Debito netto / EBITDA", "pt": "Dívida líquida / EBITDA"},
    "couverture_interets": {"fr": "Couverture des intérêts", "en": "Interest coverage",
                            "es": "Cobertura de intereses", "de": "Zinsdeckung",
                            "it": "Copertura interessi", "pt": "Cobertura de juros"},
    "autonomie_financiere": {"fr": "Autonomie financière", "en": "Financial autonomy",
                             "es": "Autonomía financiera", "de": "Finanzielle Unabhängigkeit",
                             "it": "Autonomia finanziaria", "pt": "Autonomia financeira"},
    "bfr_jours_ca": {"fr": "BFR (jours de CA)", "en": "Working capital (days of revenue)",
                     "es": "NOF (días de ingresos)", "de": "Working Capital (Umsatztage)",
                     "it": "Capitale circolante (giorni)", "pt": "Fundo de maneio (dias)"},
    "tresorerie_nette": {"fr": "Trésorerie nette", "en": "Net cash",
                         "es": "Tesorería neta", "de": "Netto-Cash",
                         "it": "Liquidità netta", "pt": "Tesouraria líquida"},
    "dso_jours": {"fr": "DSO (délai clients)", "en": "DSO (days sales outstanding)",
                  "es": "DSO (plazo de cobro)", "de": "DSO (Zahlungszieldauer)",
                  "it": "DSO (giorni di incasso)", "pt": "DSO (prazo de recebimento)"},
    "dpo_jours": {"fr": "DPO (délai fournisseurs)", "en": "DPO (days payables outstanding)",
                  "es": "DPO (plazo de pago)", "de": "DPO (Zahlungsziel Lieferanten)",
                  "it": "DPO (giorni di pagamento)", "pt": "DPO (prazo de pagamento)"},
    "rotation_stocks": {"fr": "Rotation des stocks", "en": "Inventory turnover",
                        "es": "Rotación de existencias", "de": "Lagerumschlag",
                        "it": "Rotazione delle scorte", "pt": "Rotação de stocks"},
    "ca_par_employe": {"fr": "CA par employé", "en": "Revenue per employee",
                       "es": "Ingresos por empleado", "de": "Umsatz je Mitarbeiter",
                       "it": "Ricavi per dipendente", "pt": "Receita por colaborador"},
    "charges_perso_ca": {"fr": "Charges personnel / CA", "en": "Staff costs / Revenue",
                         "es": "Gastos de personal / Ingresos", "de": "Personalkosten / Umsatz",
                         "it": "Costi del personale / Ricavi", "pt": "Custos pessoal / Receita"},
}


def ratio_label(key: str, lang: str) -> str:
    """Libellé multilingue d'un ratio/KPI (Marge brute, ROCE, DSO…)."""
    lang = normalize_language(lang)
    spec = RATIO_LABELS.get(key)
    if not spec:
        return key.replace("_", " ").capitalize()
    return spec.get(lang) or spec.get("en") or spec.get("fr") or key


# ─── Disclaimers & mentions légales (footers PDF/PPTX) ────────────────────
DISCLAIMERS: dict[str, dict[str, str]] = {
    "not_advice_mifid": {
        "fr": "Ne constitue pas un conseil en investissement au sens MiFID II.",
        "en": "Does not constitute investment advice within the meaning of MiFID II.",
        "es": "No constituye asesoramiento de inversión en el sentido de MiFID II.",
        "de": "Stellt keine Anlageberatung im Sinne von MiFID II dar.",
        "it": "Non costituisce consulenza in materia di investimenti ai sensi della MiFID II.",
        "pt": "Não constitui aconselhamento de investimento na aceção da MiFID II.",
    },
    "not_advice": {
        "fr": "Ne constitue pas un conseil en investissement.",
        "en": "Does not constitute investment advice.",
        "es": "No constituye asesoramiento de inversión.",
        "de": "Stellt keine Anlageberatung dar.",
        "it": "Non costituisce consulenza in materia di investimenti.",
        "pt": "Não constitui aconselhamento de investimento.",
    },
    "confidential_restricted": {
        "fr": "CONFIDENTIEL — Usage restreint",
        "en": "CONFIDENTIAL — Restricted use",
        "es": "CONFIDENCIAL — Uso restringido",
        "de": "VERTRAULICH — Eingeschränkte Nutzung",
        "it": "RISERVATO — Uso limitato",
        "pt": "CONFIDENCIAL — Uso restrito",
    },
    "source_finsight": {
        "fr": "Source : FinSight IA",
        "en": "Source: FinSight IA",
        "es": "Fuente: FinSight IA",
        "de": "Quelle: FinSight IA",
        "it": "Fonte: FinSight IA",
        "pt": "Fonte: FinSight IA",
    },
    "generated_by_ai": {
        "fr": "Document généré par IA. Ne constitue pas un conseil en investissement.",
        "en": "AI-generated document. Does not constitute investment advice.",
        "es": "Documento generado por IA. No constituye asesoramiento de inversión.",
        "de": "KI-generiertes Dokument. Stellt keine Anlageberatung dar.",
        "it": "Documento generato da IA. Non costituisce consulenza in materia di investimenti.",
        "pt": "Documento gerado por IA. Não constitui aconselhamento de investimento.",
    },
    "horizon_12m": {
        "fr": "Horizon : 12 mois",
        "en": "Horizon: 12 months",
        "es": "Horizonte: 12 meses",
        "de": "Horizont: 12 Monate",
        "it": "Orizzonte: 12 mesi",
        "pt": "Horizonte: 12 meses",
    },
}


def disclaimer(key: str, lang: str) -> str:
    """Libellé multilingue d'un disclaimer/mention légale."""
    lang = normalize_language(lang)
    spec = DISCLAIMERS.get(key)
    if not spec:
        return ""
    return spec.get(lang) or spec.get("en") or spec.get("fr") or ""


# ─── SIG (Soldes Intermédiaires de Gestion) PCG → IFRS mapping ────────────
SIG_LABELS: dict[str, dict[str, str]] = {
    "chiffre_affaires":       {"fr": "Chiffre d'affaires", "en": "Revenue",
                               "es": "Cifra de negocios", "de": "Umsatz",
                               "it": "Ricavi", "pt": "Volume de negócios"},
    "production_exercice":    {"fr": "Production de l'exercice",
                               "en": "Production for the period",
                               "es": "Producción del ejercicio",
                               "de": "Gesamtleistung",
                               "it": "Produzione dell'esercizio",
                               "pt": "Produção do exercício"},
    "valeur_ajoutee":         {"fr": "Valeur ajoutée (VA)", "en": "Value added",
                               "es": "Valor añadido", "de": "Wertschöpfung",
                               "it": "Valore aggiunto", "pt": "Valor acrescentado"},
    "ebe":                    {"fr": "Excédent brut d'exploitation (EBE)",
                               "en": "EBITDA",
                               "es": "EBITDA",
                               "de": "EBITDA",
                               "it": "EBITDA",
                               "pt": "EBITDA"},
    "resultat_exploitation":  {"fr": "Résultat d'exploitation (REX)",
                               "en": "Operating income (EBIT)",
                               "es": "Resultado de explotación",
                               "de": "Betriebsergebnis",
                               "it": "Risultato operativo",
                               "pt": "Resultado operacional"},
    "resultat_courant":       {"fr": "Résultat courant avant impôts (RCAI)",
                               "en": "Income before tax",
                               "es": "Resultado antes de impuestos",
                               "de": "Ergebnis vor Steuern",
                               "it": "Risultato prima delle imposte",
                               "pt": "Resultado antes de impostos"},
    "resultat_net":           {"fr": "Résultat net", "en": "Net income",
                               "es": "Beneficio neto", "de": "Jahresüberschuss",
                               "it": "Utile netto", "pt": "Lucro líquido"},
    "caf":                    {"fr": "Capacité d'autofinancement (CAF)",
                               "en": "Cash flow from operations (CFO)",
                               "es": "Capacidad de autofinanciación",
                               "de": "Cashflow aus operativer Tätigkeit",
                               "it": "Capacità di autofinanziamento",
                               "pt": "Capacidade de autofinanciamento"},
    "charges_personnel":      {"fr": "Charges personnel total",
                               "en": "Total staff costs",
                               "es": "Gastos de personal",
                               "de": "Personalkosten",
                               "it": "Costi del personale",
                               "pt": "Custos com pessoal"},
    "consommations_externes": {"fr": "Consommations externes",
                               "en": "External expenses",
                               "es": "Consumos externos",
                               "de": "Bezogene Leistungen",
                               "it": "Consumi esterni",
                               "pt": "Consumos externos"},
}


def sig_label(key: str, lang: str) -> str:
    """Libellé SIG multilingue (PCG FR → IFRS universel)."""
    lang = normalize_language(lang)
    spec = SIG_LABELS.get(key)
    if not spec:
        return key.replace("_", " ").capitalize()
    return spec.get(lang) or spec.get("en") or spec.get("fr") or key


# ─── Labels communs (tables, headers) ─────────────────────────────────────
COMMON_LABELS: dict[str, dict[str, str]] = {
    "indicateur":  {"fr": "Indicateur", "en": "Indicator",
                    "es": "Indicador", "de": "Indikator",
                    "it": "Indicatore", "pt": "Indicador"},
    "secteur":     {"fr": "Secteur", "en": "Sector",
                    "es": "Sector", "de": "Sektor",
                    "it": "Settore", "pt": "Setor"},
    "societe":     {"fr": "Société", "en": "Company",
                    "es": "Empresa", "de": "Unternehmen",
                    "it": "Società", "pt": "Empresa"},
    "score":       {"fr": "Score", "en": "Score",
                    "es": "Puntuación", "de": "Bewertung",
                    "it": "Punteggio", "pt": "Pontuação"},
    "signal":      {"fr": "Signal", "en": "Signal",
                    "es": "Señal", "de": "Signal",
                    "it": "Segnale", "pt": "Sinal"},
    "lecture":     {"fr": "Lecture", "en": "Reading",
                    "es": "Lectura", "de": "Auslegung",
                    "it": "Lettura", "pt": "Leitura"},
    "avantage":    {"fr": "Avantage", "en": "Advantage",
                    "es": "Ventaja", "de": "Vorteil",
                    "it": "Vantaggio", "pt": "Vantagem"},
    "ecart":       {"fr": "Écart", "en": "Gap",
                    "es": "Diferencia", "de": "Abweichung",
                    "it": "Scarto", "pt": "Diferença"},
    "date_analyse":{"fr": "Date d'analyse", "en": "Analysis date",
                    "es": "Fecha de análisis", "de": "Analysedatum",
                    "it": "Data di analisi", "pt": "Data da análise"},
    "horizon":     {"fr": "Horizon", "en": "Horizon",
                    "es": "Horizonte", "de": "Horizont",
                    "it": "Orizzonte", "pt": "Horizonte"},
    "rang":        {"fr": "Rang", "en": "Rank",
                    "es": "Rango", "de": "Rang",
                    "it": "Rango", "pt": "Classificação"},
    "ticker":      {"fr": "Ticker", "en": "Ticker",
                    "es": "Ticker", "de": "Ticker",
                    "it": "Ticker", "pt": "Ticker"},
    "poids":       {"fr": "Poids", "en": "Weight",
                    "es": "Peso", "de": "Gewicht",
                    "it": "Peso", "pt": "Peso"},
    "univers":     {"fr": "Univers", "en": "Universe",
                    "es": "Universo", "de": "Universum",
                    "it": "Universo", "pt": "Universo"},
    "nb_societes": {"fr": "Nb sociétés", "en": "Nb companies",
                    "es": "Nº empresas", "de": "Anz. Unternehmen",
                    "it": "N. società", "pt": "Nº empresas"},
    "valeur":      {"fr": "Valeur", "en": "Value",
                    "es": "Valor", "de": "Wert",
                    "it": "Valore", "pt": "Valor"},
    "interpretation":{"fr": "Interprétation", "en": "Interpretation",
                      "es": "Interpretación", "de": "Interpretation",
                      "it": "Interpretazione", "pt": "Interpretação"},
    "denomination": {"fr": "Dénomination", "en": "Company name",
                     "es": "Denominación", "de": "Firmenname",
                     "it": "Denominazione", "pt": "Denominação"},
    "siren":        {"fr": "SIREN", "en": "SIREN (FR registry)",
                     "es": "SIREN", "de": "SIREN", "it": "SIREN", "pt": "SIREN"},
    "forme_jur":    {"fr": "Forme juridique", "en": "Legal form",
                     "es": "Forma jurídica", "de": "Rechtsform",
                     "it": "Forma giuridica", "pt": "Forma jurídica"},
    "code_naf":     {"fr": "Code NAF", "en": "NAF code (industry)",
                     "es": "Código NAF", "de": "NAF-Code",
                     "it": "Codice NAF", "pt": "Código NAF"},
    "ville_siege":  {"fr": "Ville du siège", "en": "Head office city",
                     "es": "Ciudad sede", "de": "Hauptsitz",
                     "it": "Città sede", "pt": "Cidade da sede"},
    "date_creation":{"fr": "Date de création", "en": "Incorporation date",
                     "es": "Fecha de constitución", "de": "Gründungsdatum",
                     "it": "Data di costituzione", "pt": "Data de constituição"},
    "capital_social":{"fr": "Capital social", "en": "Share capital",
                      "es": "Capital social", "de": "Grundkapital",
                      "it": "Capitale sociale", "pt": "Capital social"},
    "penalty_bodacc":{"fr": "Pénalité BODACC", "en": "BODACC penalty",
                      "es": "Penalización BODACC", "de": "BODACC-Strafe",
                      "it": "Penalità BODACC", "pt": "Penalidade BODACC"},
}


def common_label(key: str, lang: str) -> str:
    """Libellé commun multilingue (headers de tables, mots usuels)."""
    lang = normalize_language(lang)
    spec = COMMON_LABELS.get(key)
    if not spec:
        return key.replace("_", " ").capitalize()
    return spec.get(lang) or spec.get("en") or spec.get("fr") or key


# ─── Benchmark ranks (positionnement quartile vs peers) ───────────────────
BENCHMARK_RANKS: dict[str, dict[str, str]] = {
    "top_25":       {"fr": "Top 25%", "en": "Top 25%",
                     "es": "Top 25%", "de": "Top 25%",
                     "it": "Top 25%", "pt": "Top 25%"},
    "above_median": {"fr": "Au-dessus médiane", "en": "Above median",
                     "es": "Sobre mediana", "de": "Über Median",
                     "it": "Sopra mediana", "pt": "Acima da mediana"},
    "below_median": {"fr": "Sous médiane", "en": "Below median",
                     "es": "Bajo mediana", "de": "Unter Median",
                     "it": "Sotto mediana", "pt": "Abaixo da mediana"},
    "bottom_25":    {"fr": "Bottom 25%", "en": "Bottom 25%",
                     "es": "Bottom 25%", "de": "Bottom 25%",
                     "it": "Bottom 25%", "pt": "Bottom 25%"},
}


def benchmark_rank_label(rank: str, lang: str) -> str:
    """Libellé multilingue d'un rang de benchmark (top_25 → 'Top 25%')."""
    lang = normalize_language(lang)
    spec = BENCHMARK_RANKS.get(rank)
    if not spec:
        return rank or "—"
    return spec.get(lang) or spec.get("en") or spec.get("fr") or rank


# ─── Scoring labels (PME + société) ───────────────────────────────────────
SCORING_LABELS: dict[str, dict[str, str]] = {
    "altman_z_private": {"fr": "Altman Z-Score (non coté)",
                         "en": "Altman Z-Score (private)",
                         "es": "Altman Z-Score (no cotizada)",
                         "de": "Altman Z-Score (nicht börsennotiert)",
                         "it": "Altman Z-Score (non quotata)",
                         "pt": "Altman Z-Score (não cotada)"},
    "altman_verdict":   {"fr": "Verdict Altman", "en": "Altman verdict",
                         "es": "Veredicto Altman", "de": "Altman-Urteil",
                         "it": "Verdetto Altman", "pt": "Veredicto Altman"},
    "health_score":     {"fr": "Score santé FinSight (0-100)",
                         "en": "FinSight health score (0-100)",
                         "es": "Puntuación de salud FinSight (0-100)",
                         "de": "FinSight-Gesundheitswert (0-100)",
                         "it": "Punteggio salute FinSight (0-100)",
                         "pt": "Pontuação saúde FinSight (0-100)"},
    "bankability_score":{"fr": "Score bankabilité (0-100)",
                         "en": "Bankability score (0-100)",
                         "es": "Puntuación bankabilidad (0-100)",
                         "de": "Bankbarkeitswert (0-100)",
                         "it": "Punteggio bancabilità (0-100)",
                         "pt": "Pontuação bancabilidade (0-100)"},
    "debt_capacity":    {"fr": "Capacité dette additionnelle",
                         "en": "Additional debt capacity",
                         "es": "Capacidad deuda adicional",
                         "de": "Zusätzliche Verschuldungskapazität",
                         "it": "Capacità debito aggiuntivo",
                         "pt": "Capacidade dívida adicional"},
    "bodacc_total":     {"fr": "BODACC — Annonces totales",
                         "en": "BODACC — Total announcements",
                         "es": "BODACC — Anuncios totales",
                         "de": "BODACC — Gesamtanzahl Bekanntmachungen",
                         "it": "BODACC — Annunci totali",
                         "pt": "BODACC — Anúncios totais"},
    "bodacc_collective":{"fr": "BODACC — Procédures collectives",
                         "en": "BODACC — Collective proceedings",
                         "es": "BODACC — Procedimientos colectivos",
                         "de": "BODACC — Sammelverfahren",
                         "it": "BODACC — Procedure collettive",
                         "pt": "BODACC — Processos coletivos"},
    "bodacc_strike":    {"fr": "BODACC — Radiée",
                         "en": "BODACC — Struck off",
                         "es": "BODACC — Cancelada",
                         "de": "BODACC — Gelöscht",
                         "it": "BODACC — Cancellata",
                         "pt": "BODACC — Cancelada"},
    "bodacc_penalty":   {"fr": "BODACC — Pénalité scoring",
                         "en": "BODACC — Scoring penalty",
                         "es": "BODACC — Penalización scoring",
                         "de": "BODACC — Scoring-Strafe",
                         "it": "BODACC — Penalità scoring",
                         "pt": "BODACC — Penalidade scoring"},
}


def scoring_label(key: str, lang: str) -> str:
    """Libellé multilingue d'un indicateur de scoring."""
    lang = normalize_language(lang)
    spec = SCORING_LABELS.get(key)
    if not spec:
        return key.replace("_", " ").capitalize()
    return spec.get(lang) or spec.get("en") or spec.get("fr") or key
