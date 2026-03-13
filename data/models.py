# =============================================================================
# FinSight IA — Modèles de données
# data/models.py
#
# Structure cible : tous les champs mappent directement sur config/excel_mapping.py
# Unités : MILLIONS (M) — les sources convertissent avant de remplir ces champs
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class FinancialYear:
    """
    Données financières pour une année — champs en correspondance exacte
    avec config/excel_mapping.py (INCOME_STATEMENT, BALANCE_SHEET_*, CASH_FLOW).
    Unité : millions (M).
    """
    year: str  # "2022" | "2023" | "2024_LTM"

    # --- Income Statement (lignes manuelles uniquement) ---
    revenue: Optional[float] = None           # D9–H9
    cogs: Optional[float] = None              # D10–H10
    sga: Optional[float] = None               # D14–H14
    rd: Optional[float] = None                # D15–H15
    da: Optional[float] = None                # D16–H16
    interest_expense: Optional[float] = None  # D20–H20
    interest_income: Optional[float] = None   # D21–H21
    tax_expense_real: Optional[float] = None  # D25–H25
    dividends: Optional[float] = None         # D29–H29

    # --- Balance Sheet Assets ---
    cash: Optional[float] = None                   # D34–H34
    accounts_receivable: Optional[float] = None    # D35–H35
    inventories: Optional[float] = None            # D36–H36
    other_current_assets: Optional[float] = None   # D37–H37
    ppe_net: Optional[float] = None                # D41–H41
    intangibles: Optional[float] = None            # D42–H42
    other_lt_assets: Optional[float] = None        # D43–H43

    # --- Balance Sheet Liabilities ---
    accounts_payable: Optional[float] = None       # D47–H47
    short_term_debt: Optional[float] = None        # D48–H48
    income_tax_payable: Optional[float] = None     # D49–H49
    other_current_liab: Optional[float] = None     # D50–H50
    long_term_debt: Optional[float] = None         # D54–H54
    common_equity_paid_in: Optional[float] = None  # D58–H58

    # --- Cash Flow Statement ---
    change_accounts_receivable: Optional[float] = None  # D71–H71
    change_inventories: Optional[float] = None          # D72–H72
    change_accounts_payable: Optional[float] = None     # D73–H73
    other_wc_changes: Optional[float] = None            # D74–H74
    capex: Optional[float] = None                       # D78–H78
    other_investing: Optional[float] = None             # D79–H79
    change_lt_debt: Optional[float] = None              # D83–H83
    change_common_equity: Optional[float] = None        # D84–H84
    dividends_paid: Optional[float] = None              # D85–H85
    beginning_cash: Optional[float] = None              # D90–H90

    # --- Agrégats directs yfinance (override calcul partiel dans AgentQuant) ---
    # Evite les erreurs dues au bilan partiel (equity, total_assets)
    gross_profit_yf:       Optional[float] = None  # Gross Profit directement IS
    ebit_yf:               Optional[float] = None  # EBIT directement IS
    net_income_yf:         Optional[float] = None  # Net Income (from Continuing Ops)
    total_equity_yf:       Optional[float] = None  # Stockholders Equity directement BS
    total_assets_yf:       Optional[float] = None  # Total Assets directement BS
    total_liabilities_yf:  Optional[float] = None  # Total Liabilities directement BS
    retained_earnings_yf:  Optional[float] = None  # Retained Earnings directement BS

    def coverage(self) -> float:
        """Fraction de champs non-None — niveau de confiance constitutionnel."""
        all_fields = [f for f in self.__dataclass_fields__ if f != "year"]
        filled = sum(1 for f in all_fields if getattr(self, f) is not None)
        return filled / len(all_fields) if all_fields else 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompanyInfo:
    """Informations société — champs COMPANY_INFO (lignes 114–120)."""
    company_name: str = ""
    ticker: str = ""
    sector: str = ""
    base_year: int = 2022
    currency: str = "USD"
    units: str = "M"
    analysis_date: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarketData:
    """
    Données marché / valorisation — champs MARKET_DATA (lignes 95–110).
    risk_free_rate / erp / wacc / terminal_growth : à remplir manuellement
    ou par Agent Quant en Phase 3.
    """
    share_price: Optional[float] = None         # D95–H95
    shares_diluted: Optional[float] = None      # D96–H96  (millions)
    beta_levered: Optional[float] = None        # D99–H99
    risk_free_rate: Optional[float] = None      # D100–H100
    erp: Optional[float] = None                 # D101–H101  equity risk premium
    cost_of_debt_pretax: Optional[float] = None # D103–H103
    tax_rate: Optional[float] = None            # D104–H104
    weight_equity: Optional[float] = None       # D106–H106
    weight_debt: Optional[float] = None         # D107–H107
    wacc: Optional[float] = None                # D108–H108
    terminal_growth: Optional[float] = None     # D109–H109
    days_in_period: Optional[int] = None        # D110–H110

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StockPoint:
    """Point mensuel historique — onglet STOCK_DATA (B3:C15)."""
    month: str   # ex. "Mar-25"
    price: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FinancialSnapshot:
    """
    Résultat complet de l'Agent Data pour un ticker.
    Contient tout ce dont l'Agent Quant a besoin pour injecter dans le TEMPLATE.xlsx.
    """
    ticker: str
    company_info: CompanyInfo
    years: dict  # {"2022": FinancialYear, "2023": FinancialYear, "2024_LTM": FinancialYear}
    market: MarketData
    stock_history: list  # list[StockPoint], 13 points max
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "company_info": self.company_info.to_dict(),
            "years": {k: v.to_dict() for k, v in self.years.items()},
            "market": self.market.to_dict(),
            "stock_history": [p.to_dict() for p in self.stock_history],
            "meta": self.meta,
        }
