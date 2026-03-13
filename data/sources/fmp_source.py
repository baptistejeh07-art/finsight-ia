# =============================================================================
# FinSight IA — Source 2 : Financial Modeling Prep (FMP)
# data/sources/fmp_source.py
#
# Fondamentaux européens, non-cotées. 250 req/jour.
# URL : financialmodelingprep.com (NE PAS utiliser prepfmcloud.io — incorrect)
# Priorité 2 — gap-filler après yfinance.
# =============================================================================

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from data.models import (
    CompanyInfo, FinancialYear, FinancialSnapshot, MarketData, StockPoint,
)

log = logging.getLogger(__name__)

_BASE = "https://financialmodelingprep.com/api"
_TIMEOUT = 10


def _get(endpoint: str, api_key: str) -> Optional[list | dict]:
    """Appel HTTP FMP avec gestion d'erreur silencieuse."""
    sep = "&" if "?" in endpoint else "?"
    url = f"{_BASE}{endpoint}{sep}apikey={api_key}"
    try:
        r = httpx.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return data
        if isinstance(data, dict) and data and "Error Message" not in data:
            return data
        return None
    except Exception as e:
        log.warning(f"[FMP] {endpoint}: {e}")
        return None


def _m(val) -> Optional[float]:
    """Brut → millions."""
    try:
        return round(float(val) / 1_000_000, 2) if val is not None else None
    except (TypeError, ValueError):
        return None


def _by_year(items: list, year: int) -> Optional[dict]:
    """Retourne le statement correspondant à une année fiscale."""
    for item in items:
        cal = item.get("calendarYear") or str(item.get("date", ""))[:4]
        if str(cal) == str(year):
            return item
    return None


def fetch(ticker: str) -> Optional[FinancialSnapshot]:
    """Collecte via FMP. Complémentaire à yfinance pour les données manquantes."""
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        log.warning("[FMP] FMP_API_KEY non définie — source ignorée")
        return None

    profile     = _get(f"/v3/profile/{ticker}?",                      api_key)
    income_list = _get(f"/v3/income-statement/{ticker}?limit=5",       api_key)
    bs_list     = _get(f"/v3/balance-sheet-statement/{ticker}?limit=5", api_key)
    cf_list     = _get(f"/v3/cash-flow-statement/{ticker}?limit=5",     api_key)

    if not income_list:
        log.warning(f"[FMP] Aucun income statement pour '{ticker}'")
        return None

    years_data: dict[str, FinancialYear] = {}

    for year_label, year_int in [("2022", 2022), ("2023", 2023), ("2024", 2024)]:
        inc = _by_year(income_list, year_int) if income_list else None
        bs  = _by_year(bs_list, year_int)     if bs_list     else None
        cf  = _by_year(cf_list, year_int)     if cf_list     else None

        fy = FinancialYear(year=year_label)

        if inc:
            fy.revenue          = _m(inc.get("revenue"))
            fy.cogs             = _m(inc.get("costOfRevenue"))
            fy.sga              = _m(inc.get("sellingGeneralAndAdministrativeExpenses"))
            fy.rd               = _m(inc.get("researchAndDevelopmentExpenses"))
            fy.da               = _m(inc.get("depreciationAndAmortization"))
            fy.interest_expense = _m(inc.get("interestExpense"))
            fy.interest_income  = _m(inc.get("interestIncome"))
            fy.tax_expense_real = _m(inc.get("incomeTaxExpense"))

        if bs:
            fy.cash                  = _m(bs.get("cashAndCashEquivalents"))
            fy.accounts_receivable   = _m(bs.get("netReceivables"))
            fy.inventories           = _m(bs.get("inventory"))
            fy.other_current_assets  = _m(bs.get("otherCurrentAssets"))
            fy.ppe_net               = _m(bs.get("propertyPlantEquipmentNet"))
            fy.intangibles           = _m(bs.get("goodwillAndIntangibleAssets"))
            fy.other_lt_assets       = _m(bs.get("otherNonCurrentAssets"))
            fy.accounts_payable      = _m(bs.get("accountPayables"))
            fy.short_term_debt       = _m(bs.get("shortTermDebt"))
            fy.income_tax_payable    = _m(bs.get("taxPayables"))
            fy.other_current_liab    = _m(bs.get("otherCurrentLiabilities"))
            fy.long_term_debt        = _m(bs.get("longTermDebt"))
            fy.common_equity_paid_in = _m(bs.get("commonStock"))

        if cf:
            fy.change_inventories      = _m(cf.get("changeInInventory"))
            fy.change_accounts_payable = _m(cf.get("changeInAccountPayables"))
            fy.capex                   = _m(cf.get("capitalExpenditure"))
            fy.other_investing         = _m(cf.get("otherInvestingActivites"))
            fy.change_lt_debt          = _m(cf.get("longTermNetIssuancePayments"))
            fy.change_common_equity    = _m(cf.get("commonStockIssued"))
            fy.dividends_paid          = _m(cf.get("dividendsPaid"))

        years_data[year_label] = fy

    # --- Company Info ---
    prof = profile[0] if isinstance(profile, list) and profile else {}
    company_info = CompanyInfo(
        company_name  = prof.get("companyName", ticker),
        ticker        = ticker.upper(),
        sector        = prof.get("sector", ""),
        currency      = prof.get("currency", "EUR"),
        units         = "M",
    )

    # --- Market Data ---
    price   = prof.get("price")
    mkt_cap = prof.get("mktCap")
    shares  = None
    if price and mkt_cap and float(price) > 0:
        shares = _m(float(mkt_cap) / float(price))  # raw shares → millions

    market = MarketData(
        share_price    = round(float(price), 2) if price else None,
        shares_diluted = shares,
        beta_levered   = prof.get("beta"),
    )

    return FinancialSnapshot(
        ticker        = ticker.upper(),
        company_info  = company_info,
        years         = years_data,
        market        = market,
        stock_history = [],
        meta          = {"source": "fmp"},
    )
