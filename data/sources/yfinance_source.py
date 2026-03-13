# =============================================================================
# FinSight IA — Source 1 : yfinance (primaire)
# data/sources/yfinance_source.py
#
# Cotées uniquement. Illimité. Données annuelles + temps réel.
# Années collectées : 5 derniers exercices disponibles (auto-détection).
# =============================================================================

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf

from data.models import (
    CompanyInfo, FinancialYear, FinancialSnapshot, MarketData, StockPoint,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping robuste : champ FinSight → noms alternatifs dans yfinance
# IMPORTANT : yfinance utilise des noms qui varient selon la version et
# le ticker. Ordonnés du plus probable au moins probable.
# ---------------------------------------------------------------------------

_IS_MAP: dict[str, list[str]] = {
    "revenue":          ["Total Revenue", "Revenue", "Operating Revenue"],
    "cogs":             ["Cost Of Revenue", "Reconciled Cost Of Revenue",
                         "Cost of Goods Sold"],
    "sga":              ["Selling General And Administration",        # yfinance actuel
                         "Selling General And Administrative",        # ancien nom
                         "Selling General Administrative",
                         "Selling And Marketing Expense"],
    "rd":               ["Research And Development", "Research Development"],
    "da":               ["Reconciled Depreciation",
                         "Depreciation And Amortization In Income Statement",
                         "Depreciation Amortization Depletion"],
    "interest_expense": ["Interest Expense Non Operating",
                         "Interest Expense"],
    "interest_income":  ["Interest Income Non Operating",
                         "Interest Income"],
    "tax_expense_real": ["Tax Provision", "Income Tax Expense"],
    "dividends":        ["Common Stock Dividends"],
    # Agrégats directs (override calcul partiel)
    "gross_profit_yf":  ["Gross Profit"],
    "ebit_yf":          ["EBIT"],
    "net_income_yf":    ["Net Income From Continuing Operation Net Minority Interest",
                         "Net Income Continuous Operations",
                         "Net Income Common Stockholders",
                         "Net Income"],
}

_BSA_MAP: dict[str, list[str]] = {
    "cash":                 ["Cash And Cash Equivalents",
                             "Cash Cash Equivalents And Short Term Investments",
                             "Cash And Short Term Investments"],
    "accounts_receivable":  ["Accounts Receivable", "Net Receivables"],
    "inventories":          ["Inventory", "Inventories"],
    "other_current_assets": ["Other Current Assets"],
    "ppe_net":              ["Net PPE", "Net Property Plant And Equipment",
                             "Property Plant And Equipment Net"],
    "intangibles":          ["Goodwill And Other Intangible Assets", "Goodwill",
                             "Intangible Assets"],
    "other_lt_assets":      ["Other Non Current Assets", "Other Long Term Assets"],
    # Agrégats directs BS
    "total_equity_yf":      ["Common Stock Equity", "Stockholders Equity",
                             "Total Stockholders Equity"],
    "total_assets_yf":      ["Total Assets"],
    "total_liabilities_yf": ["Total Liabilities Net Minority Interest",
                             "Total Liabilities"],
    "retained_earnings_yf": ["Retained Earnings", "Retained Earnings Total Equity"],
}

_BSL_MAP: dict[str, list[str]] = {
    "accounts_payable":      ["Accounts Payable", "Payables"],
    "short_term_debt":       ["Current Debt", "Short Term Debt",
                              "Current Debt And Capital Lease Obligation"],
    "income_tax_payable":    ["Income Tax Payable", "Total Tax Payable"],
    "other_current_liab":    ["Other Current Liabilities"],
    "long_term_debt":        ["Long Term Debt",
                              "Long Term Debt And Capital Lease Obligation"],
    # common_equity_paid_in calculé séparément (Capital Stock + APIC)
}

_CF_MAP: dict[str, list[str]] = {
    "change_accounts_receivable": ["Change In Receivables", "Changes In Account Receivables",
                                   "Change In Accounts Receivable"],
    "change_inventories":         ["Change In Inventory", "Change In Inventories"],
    "change_accounts_payable":    ["Change In Payable", "Changes In Payable",
                                   "Change In Accounts Payable"],
    # D74 : autres flux opérationnels (hors AR/Inv/AP déjà en D71-D73)
    # "Change In Working Capital" exclu → doublon avec les lignes 71-73
    "other_wc_changes":           ["Other Operating Activities",
                                   "Other Non Cash Items"],
    "capex":                      ["Capital Expenditure", "Capital Expenditures",
                                   "Purchase Of PPE"],
    "other_investing":            ["Other Investing Activities",
                                   "Other Investing Cash Flow"],
    "change_lt_debt":             ["Long Term Debt Issuance", "Issuance Of Debt",
                                   "Net Long Term Debt Issuance"],
    "change_common_equity":       ["Common Stock Issuance", "Net Common Stock Issuance",
                                   "Issuance Of Capital Stock"],
    "dividends_paid":             ["Payment Of Dividends", "Common Stock Payments",
                                   "Cash Dividends Paid"],
    "beginning_cash":             ["Beginning Cash Position", "Cash At Beginning Of Period"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(df: pd.DataFrame, names: list[str], col) -> Optional[float]:
    """Récupère la première valeur non-NaN depuis un DataFrame yfinance."""
    if df is None or df.empty or col is None:
        return None
    for name in names:
        if name in df.index:
            try:
                val = df.at[name, col]
                if pd.notna(val):
                    return float(val)
            except (KeyError, TypeError):
                continue
    return None


def _m(val: Optional[float]) -> Optional[float]:
    """Valeur brute → millions, arrondi 2 décimales."""
    if val is None:
        return None
    try:
        return round(val / 1_000_000, 2)
    except (TypeError, ZeroDivisionError):
        return None


def _col_for_year(df: pd.DataFrame, target_year: int):
    """Retourne la colonne d'un DataFrame yfinance correspondant à une année."""
    if df is None or df.empty:
        return None
    for col in df.columns:
        try:
            if hasattr(col, "year") and col.year == target_year:
                return col
        except Exception:
            pass
    return None


def _detect_years(df: pd.DataFrame, max_years: int = 5) -> list[int]:
    """
    Détecte les années disponibles (desc) dans un DataFrame yfinance.
    Exclut l'année civile en cours : yfinance peut retourner une colonne TTM
    avec la date du jour (ex. 2026-03-07 → année 2026) qui n'est pas un
    exercice fiscal complet. On ne conserve que les exercices clos.
    """
    if df is None or df.empty:
        return []
    current_year = date.today().year
    years = []
    for col in df.columns:
        try:
            if hasattr(col, "year") and col.year < current_year:
                years.append(col.year)
        except Exception:
            pass
    # Plus récent en premier, on prend les max_years plus récents
    return sorted(set(years), reverse=True)[:max_years]


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

def fetch(ticker: str) -> Optional[FinancialSnapshot]:
    """
    Collecte complète via yfinance.
    Auto-détecte les 3 exercices les plus récents disponibles.
    """
    try:
        tk   = yf.Ticker(ticker)
        info = {}
        try:
            info = tk.info or {}
        except Exception as e:
            log.warning(f"[yfinance] '{ticker}' tk.info failed: {e}")

        # Fallback fast_info si info vide ou sans prix
        price_check = info.get("currentPrice") or info.get("regularMarketPrice")
        name_check  = info.get("longName") or info.get("shortName")
        if not price_check or not name_check:
            try:
                fi = tk.fast_info
                if not price_check:
                    price_check = getattr(fi, "last_price", None)
                    if price_check:
                        info["currentPrice"] = float(price_check)
                if not name_check:
                    name_check = ticker  # au pire on utilise le ticker comme nom
                    info.setdefault("longName", ticker)
            except Exception as e:
                log.warning(f"[yfinance] '{ticker}' fast_info failed: {e}")

        if not price_check and not name_check:
            log.warning(f"[yfinance] '{ticker}' : aucune donnée de base")
            return None

        # --- Fetch parallèle ---
        def _fetch_is():   return tk.income_stmt
        def _fetch_bs():   return tk.balance_sheet
        def _fetch_cf():   return tk.cashflow
        def _fetch_hist(): return tk.history(period="1y", interval="1mo")
        def _fetch_rfr():
            """Taux sans risque = US 10Y Treasury (^TNX) / 100."""
            try:
                tnx = yf.Ticker("^TNX").history(period="5d")
                if not tnx.empty:
                    return round(float(tnx["Close"].iloc[-1]) / 100.0, 4)
            except Exception:
                pass
            return 0.04  # fallback 4%

        with ThreadPoolExecutor(max_workers=5) as pool:
            f_is   = pool.submit(_fetch_is)
            f_bs   = pool.submit(_fetch_bs)
            f_cf   = pool.submit(_fetch_cf)
            f_hist = pool.submit(_fetch_hist)
            f_rfr  = pool.submit(_fetch_rfr)

        is_df  = f_is.result()
        bs_df  = f_bs.result()
        cf_df  = f_cf.result()
        hist   = f_hist.result()
        rfr    = f_rfr.result()

        # --- Détection automatique des années disponibles ---
        available_years = _detect_years(is_df, max_years=5)
        if not available_years:
            log.warning(f"[yfinance] '{ticker}' : aucun exercice disponible dans IS")
            return None

        # Libellés FinSight pour les 3 exercices (du plus ancien au plus récent)
        # Ex : [2022, 2023, 2024] → ["2022", "2023", "2024"]  (plain years, no LTM suffix)
        available_years_asc = sorted(available_years)  # croissant
        year_labels = [str(y) for y in available_years_asc]

        base_year = available_years_asc[-1]  # année la plus récente (ex: 2024)

        log.info(f"[yfinance] '{ticker}' : exercices {available_years_asc} → {year_labels}")

        # --- Company Info ---
        company_info = CompanyInfo(
            company_name  = info.get("longName") or info.get("shortName", ticker),
            ticker        = ticker.upper(),
            sector        = info.get("sector") or info.get("industryDisp", ""),
            base_year     = base_year,
            currency      = info.get("currency", "USD"),
            units         = "M",
            analysis_date = date.today().isoformat(),
        )

        # --- Données financières par année ---
        years_data: dict[str, FinancialYear] = {}

        for year_int, year_label in zip(available_years_asc, year_labels):
            is_col = _col_for_year(is_df, year_int)
            bs_col = _col_for_year(bs_df, year_int)
            cf_col = _col_for_year(cf_df, year_int)

            fy = FinancialYear(year=year_label)

            # Income Statement — champs manuels
            if is_col is not None:
                fy.revenue          = _m(_get(is_df, _IS_MAP["revenue"],          is_col))
                # Coûts toujours positifs (yfinance retourne parfois des valeurs négatives)
                _cogs = _m(_get(is_df, _IS_MAP["cogs"],             is_col))
                fy.cogs             = abs(_cogs) if _cogs is not None else None
                _sga = _m(_get(is_df, _IS_MAP["sga"],              is_col))
                fy.sga              = abs(_sga) if _sga is not None else None
                _rd = _m(_get(is_df, _IS_MAP["rd"],               is_col))
                fy.rd               = abs(_rd) if _rd is not None else None
                fy.da               = _m(_get(is_df, _IS_MAP["da"],               is_col))
                # D16 fallback : D&A depuis le Cash Flow si absent de l'IS
                if fy.da is None and cf_col is not None:
                    _da_cf = _m(_get(cf_df, [
                        "Depreciation And Amortization",
                        "Depreciation Amortization Depletion",
                        "Reconciled Depreciation",
                    ], cf_col))
                    fy.da = abs(_da_cf) if _da_cf is not None else None
                _ie = _m(_get(is_df, _IS_MAP["interest_expense"], is_col))
                fy.interest_expense = abs(_ie) if _ie is not None else None
                fy.interest_income  = _m(_get(is_df, _IS_MAP["interest_income"],  is_col))
                _tax = _m(_get(is_df, _IS_MAP["tax_expense_real"], is_col))
                fy.tax_expense_real = abs(_tax) if _tax is not None else None
                fy.dividends        = _m(_get(is_df, _IS_MAP["dividends"],        is_col))

                # Agrégats IS directs (override calcul partiel)
                fy.gross_profit_yf  = _m(_get(is_df, _IS_MAP["gross_profit_yf"],  is_col))
                fy.ebit_yf          = _m(_get(is_df, _IS_MAP["ebit_yf"],          is_col))
                fy.net_income_yf    = _m(_get(is_df, _IS_MAP["net_income_yf"],    is_col))

            # Balance Sheet — Assets
            if bs_col is not None:
                fy.cash                 = _m(_get(bs_df, _BSA_MAP["cash"],                bs_col))
                fy.accounts_receivable  = _m(_get(bs_df, _BSA_MAP["accounts_receivable"], bs_col))
                fy.inventories          = _m(_get(bs_df, _BSA_MAP["inventories"],         bs_col))
                fy.other_current_assets = _m(_get(bs_df, _BSA_MAP["other_current_assets"],bs_col))
                fy.ppe_net              = _m(_get(bs_df, _BSA_MAP["ppe_net"],             bs_col))
                fy.intangibles          = _m(_get(bs_df, _BSA_MAP["intangibles"],         bs_col))
                fy.other_lt_assets      = _m(_get(bs_df, _BSA_MAP["other_lt_assets"],     bs_col))

                # Agrégats BS directs
                fy.total_equity_yf      = _m(_get(bs_df, _BSA_MAP["total_equity_yf"],     bs_col))
                fy.total_assets_yf      = _m(_get(bs_df, _BSA_MAP["total_assets_yf"],     bs_col))
                fy.total_liabilities_yf = _m(_get(bs_df, _BSA_MAP["total_liabilities_yf"],bs_col))
                fy.retained_earnings_yf = _m(_get(bs_df, _BSA_MAP["retained_earnings_yf"],bs_col))

            # Balance Sheet — Liabilities
            if bs_col is not None:
                fy.accounts_payable   = _m(_get(bs_df, _BSL_MAP["accounts_payable"],   bs_col))

                # D48 : dette financière CT uniquement, sans lease obligations
                _std_pure  = _m(_get(bs_df, ["Current Debt", "Short Term Borrowings"], bs_col))
                _std_combo = _m(_get(bs_df, ["Current Debt And Capital Lease Obligation"], bs_col))
                _std_lease = _m(_get(bs_df, ["Current Capital Lease Obligation"], bs_col))
                if _std_pure is not None:
                    fy.short_term_debt = _std_pure
                elif _std_combo is not None and _std_lease is not None:
                    fy.short_term_debt = max(0.0, _std_combo - _std_lease)
                else:
                    fy.short_term_debt = _std_combo  # dernier recours (peut inclure leases)

                fy.income_tax_payable = _m(_get(bs_df, _BSL_MAP["income_tax_payable"], bs_col))
                fy.other_current_liab = _m(_get(bs_df, _BSL_MAP["other_current_liab"], bs_col))
                fy.long_term_debt     = _m(_get(bs_df, _BSL_MAP["long_term_debt"],     bs_col))

                # D58 : Paid-In Capital = Capital Stock (par value) + APIC
                _cap_stock = _m(_get(bs_df, ["Capital Stock", "Common Stock"], bs_col))
                _apic      = _m(_get(bs_df, ["Additional Paid In Capital",
                                             "Additional Paid-In Capital"], bs_col))
                if _cap_stock is not None or _apic is not None:
                    fy.common_equity_paid_in = (_cap_stock or 0.0) + (_apic or 0.0)

            # Cash Flow
            if cf_col is not None:
                fy.change_accounts_receivable = _m(_get(cf_df, _CF_MAP["change_accounts_receivable"], cf_col))
                fy.change_inventories         = _m(_get(cf_df, _CF_MAP["change_inventories"],         cf_col))
                fy.change_accounts_payable    = _m(_get(cf_df, _CF_MAP["change_accounts_payable"],    cf_col))
                fy.other_wc_changes           = _m(_get(cf_df, _CF_MAP["other_wc_changes"],           cf_col))
                fy.capex                      = _m(_get(cf_df, _CF_MAP["capex"],                      cf_col))
                fy.other_investing            = _m(_get(cf_df, _CF_MAP["other_investing"],            cf_col))
                fy.change_lt_debt             = _m(_get(cf_df, _CF_MAP["change_lt_debt"],             cf_col))
                fy.change_common_equity       = _m(_get(cf_df, _CF_MAP["change_common_equity"],       cf_col))
                fy.dividends_paid             = _m(_get(cf_df, _CF_MAP["dividends_paid"],             cf_col))
                fy.beginning_cash             = _m(_get(cf_df, _CF_MAP["beginning_cash"],             cf_col))

            years_data[year_label] = fy

        # --- D90 : reconstituer beginning_cash si absent du CF ---
        # beginning_cash(N) = ending_cash(N-1) = cash BS(N-1) si CF indispo
        for i, year_label in enumerate(year_labels):
            if i == 0:
                continue  # pas d'exercice précédent
            fy = years_data[year_label]
            if fy.beginning_cash is not None:
                continue
            prev_label    = year_labels[i - 1]
            prev_year_int = available_years_asc[i - 1]
            prev_fy       = years_data.get(prev_label)
            prev_cf_col   = _col_for_year(cf_df, prev_year_int)
            # Essai 1 : Ending Cash dans le CF de l'exercice précédent
            if prev_cf_col is not None:
                ending = _m(_get(cf_df, [
                    "Ending Cash Position",
                    "Cash At End Of Period",
                    "End Cash Position",
                ], prev_cf_col))
                if ending is not None:
                    fy.beginning_cash = ending
                    log.debug(f"[yfinance] {year_label} beginning_cash reconstruit depuis Ending CF {prev_label}")
                    continue
            # Essai 2 : Cash du bilan de l'exercice précédent (proxy)
            if prev_fy and prev_fy.cash is not None:
                fy.beginning_cash = prev_fy.cash
                log.debug(f"[yfinance] {year_label} beginning_cash reconstruit depuis BS cash {prev_label}")

        # --- Market Data ---
        price      = info.get("currentPrice") or info.get("regularMarketPrice")
        shares_raw = info.get("sharesOutstanding")

        market = MarketData(
            share_price    = round(float(price), 2) if price else None,
            shares_diluted = _m(float(shares_raw)) if shares_raw else None,
            beta_levered   = info.get("beta"),
            risk_free_rate = rfr,   # ^TNX / 100 récupéré en parallèle
        )

        # --- Historique mensuel cours ---
        # Format MMM-YY locale-independant (ex: "Mar-26") via table fixe anglaise
        _MON = ["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"]
        stock_history: list[StockPoint] = []
        if hist is not None and not hist.empty:
            for dt, row in hist.iterrows():
                month_str = f"{_MON[dt.month - 1]}-{dt.strftime('%y')}"
                stock_history.append(StockPoint(
                    month=month_str,
                    price=round(float(row["Close"]), 2),
                ))
        stock_history = stock_history[-13:]

        return FinancialSnapshot(
            ticker        = ticker.upper(),
            company_info  = company_info,
            years         = years_data,
            market        = market,
            stock_history = stock_history,
            meta          = {
                "source":      "yfinance",
                "year_labels": year_labels,
                "base_year":   base_year,
            },
        )

    except Exception as e:
        log.error(f"[yfinance] Erreur sur '{ticker}': {e}")
        import traceback; log.debug(traceback.format_exc())
        return None
