# =============================================================================
# FinSight IA — Excel Mapping v2
# config/excel_mapping.py
#
# Contrat entre Python et TEMPLATE.xlsx — VERSION CORRIGÉE
# Colonnes : D=N-4, E=N-3, F=N-2, G=N-1, H=N (5 exercices historiques)
# RÈGLES CRITIQUES :
#   - Valeurs négatives : COGS, SG&A, R&D, D&A, Interest Expense, CapEx, Dividends
#   - Pourcentages en décimal : 0.21 pour 21%
#   - Montants en millions : 1 milliard = 1_000
#   - D117 = entier année (ex: 2025) — pilote tous les en-têtes dynamiques
#   - NE JAMAIS écrire dans une cellule contenant une formule
# =============================================================================

COLS = ["D", "E", "F", "G", "H"]

# -----------------------------------------------------------------------------
# CELLULES FORMULE — NE PAS TOUCHER
# IS  : D11 Gross Profit, D13 Total OpEx, D17 EBIT, D19/D22 EBT, D24 Tax auto, D26 Net Income, D30 EBITDA
# BS  : D38 Total Current Assets, D44 Total Assets, D51 Total Current Liab,
#        D55 Total Liab, D59 Retained Earnings, D60 Total Equity, D63 L&E
# CF  : D69 Net Income, D70 D&A, D75 CFO, D80 CFI, D86 CFF, D89 Net Change, D91 Ending Cash
# MKT : D97 Market Cap, D98 EV, D102 Cost of Equity, D105 After-Tax Kd, D108 WACC
# -----------------------------------------------------------------------------
FORMULA_CELLS = [
    "D11","E11","F11","G11","H11",  # Gross Profit
    "D13","E13","F13","G13","H13",  # Total OpEx
    "D17","E17","F17","G17","H17",  # EBIT
    "D19","E19","F19","G19","H19",  # EBT intermédiaire
    "D22","E22","F22","G22","H22",  # EBT final
    "D24","E24","F24","G24","H24",  # Tax auto 21%
    "D26","E26","F26","G26","H26",  # Net Income
    "D30","E30","F30","G30","H30",  # EBITDA
    "D38","E38","F38","G38","H38",  # Total Current Assets
    "D44","E44","F44","G44","H44",  # Total Assets
    "D51","E51","F51","G51","H51",  # Total Current Liab
    "D55","E55","F55","G55","H55",  # Total Liab
    "D60","E60","F60","G60","H60",  # Total Equity (=D58+D59)
    "D63","E63","F63","G63","H63",  # L&E
    "D69","E69","F69","G69","H69",  # Net Income (CF)
    "D70","E70","F70","G70","H70",  # D&A (CF)
    "D75","E75","F75","G75","H75",  # CFO
    "D80","E80","F80","G80","H80",  # CFI
    "D86","E86","F86","G86","H86",  # CFF
    "D89","E89","F89","G89","H89",  # Net Change in Cash
    "D91","E91","F91","G91","H91",  # Ending Cash
    "D97","E97","F97","G97","H97",  # Market Cap
    "D98","E98","F98","G98","H98",  # EV
    "D102","E102","F102","G102","H102",  # Cost of Equity
    "D105","E105","F105","G105","H105",  # After-Tax Kd
    "D108","E108","F108","G108","H108",  # WACC
]

_FORMULA_CELLS_SET = set(FORMULA_CELLS)  # lookup O(1)

# -----------------------------------------------------------------------------
# COMPANY INFORMATION
# -----------------------------------------------------------------------------
COMPANY_INFO = {
    "company_name":  "D114",   # str
    "ticker":        "D115",   # str
    "sector":        "D116",   # str
    "base_year":     "D117",   # int ex: 2025 — CRITIQUE, pilote tous les en-têtes
    "currency":      "D118",   # str ex: "USD"
    "units":         "D119",   # str ex: "M"
    "analysis_date": "D120",   # str ex: "2025-01-31"
}

# -----------------------------------------------------------------------------
# INCOME STATEMENT — colonnes D→H — valeurs en millions
# Charges : injecter en NÉGATIF
# -----------------------------------------------------------------------------
INCOME_STATEMENT = {
    "revenue":          {"D":"D9",  "E":"E9",  "F":"F9",  "G":"G9",  "H":"H9"},   # positif
    "cogs":             {"D":"D10", "E":"E10", "F":"F10", "G":"G10", "H":"H10"},  # NÉGATIF
    "sga":              {"D":"D14", "E":"E14", "F":"F14", "G":"G14", "H":"H14"},  # NÉGATIF
    "rd":               {"D":"D15", "E":"E15", "F":"F15", "G":"G15", "H":"H15"},  # NÉGATIF
    "da":               {"D":"D16", "E":"E16", "F":"F16", "G":"G16", "H":"H16"},  # NÉGATIF — fallback depuis CF si absent IS
    "interest_expense": {"D":"D20", "E":"E20", "F":"F20", "G":"G20", "H":"H20"},  # NÉGATIF
    "interest_income":  {"D":"D21", "E":"E21", "F":"F21", "G":"G21", "H":"H21"},  # positif
    "tax_expense_real": {"D":"D25", "E":"E25", "F":"F25", "G":"G25", "H":"H25"},  # NÉGATIF — informatif
    "dividends":        {"D":"D29", "E":"E29", "F":"F29", "G":"G29", "H":"H29"},  # NÉGATIF
}

# -----------------------------------------------------------------------------
# BALANCE SHEET ACTIFS — colonnes D→H — valeurs en millions
# -----------------------------------------------------------------------------
BALANCE_SHEET_ASSETS = {
    "cash":                 {"D":"D34", "E":"E34", "F":"F34", "G":"G34", "H":"H34"},
    "accounts_receivable":  {"D":"D35", "E":"E35", "F":"F35", "G":"G35", "H":"H35"},
    "inventories":          {"D":"D36", "E":"E36", "F":"F36", "G":"G36", "H":"H36"},
    "other_current_assets": {"D":"D37", "E":"E37", "F":"F37", "G":"G37", "H":"H37"},
    "ppe_net":              {"D":"D41", "E":"E41", "F":"F41", "G":"G41", "H":"H41"},
    "intangibles":          {"D":"D42", "E":"E42", "F":"F42", "G":"G42", "H":"H42"},
    "other_lt_assets":      {"D":"D43", "E":"E43", "F":"F43", "G":"G43", "H":"H43"},
}

# -----------------------------------------------------------------------------
# BALANCE SHEET PASSIFS — colonnes D→H — valeurs en millions
# D58 : Paid-In Capital = Capital Stock + APIC (PAS total_equity)
# -----------------------------------------------------------------------------
BALANCE_SHEET_LIABILITIES = {
    "accounts_payable":      {"D":"D47", "E":"E47", "F":"F47", "G":"G47", "H":"H47"},
    "short_term_debt":       {"D":"D48", "E":"E48", "F":"F48", "G":"G48", "H":"H48"},  # dette financière CT, sans leases
    "income_tax_payable":    {"D":"D49", "E":"E49", "F":"F49", "G":"G49", "H":"H49"},
    "other_current_liab":    {"D":"D50", "E":"E50", "F":"F50", "G":"G50", "H":"H50"},
    "long_term_debt":        {"D":"D54", "E":"E54", "F":"F54", "G":"G54", "H":"H54"},
    "common_equity_paid_in": {"D":"D58", "E":"E58", "F":"F58", "G":"G58", "H":"H58"},  # Capital Stock + APIC
}

# -----------------------------------------------------------------------------
# CASH FLOW STATEMENT — colonnes D→H — valeurs en millions
# -----------------------------------------------------------------------------
CASH_FLOW = {
    "change_accounts_receivable": {"D":"D71", "E":"E71", "F":"F71", "G":"G71", "H":"H71"},
    "change_inventories":         {"D":"D72", "E":"E72", "F":"F72", "G":"G72", "H":"H72"},
    "change_accounts_payable":    {"D":"D73", "E":"E73", "F":"F73", "G":"G73", "H":"H73"},
    "other_wc_changes":           {"D":"D74", "E":"E74", "F":"F74", "G":"G74", "H":"H74"},
    "capex":                      {"D":"D78", "E":"E78", "F":"F78", "G":"G78", "H":"H78"},  # NÉGATIF
    "other_investing":            {"D":"D79", "E":"E79", "F":"F79", "G":"G79", "H":"H79"},
    "change_lt_debt":             {"D":"D83", "E":"E83", "F":"F83", "G":"G83", "H":"H83"},
    "change_common_equity":       {"D":"D84", "E":"E84", "F":"F84", "G":"G84", "H":"H84"},
    "dividends_paid":             {"D":"D85", "E":"E85", "F":"F85", "G":"G85", "H":"H85"},  # NÉGATIF
    "beginning_cash":             {"D":"D90", "E":"E90", "F":"F90", "G":"G90", "H":"H90"},  # = Ending Cash N-1
}

# -----------------------------------------------------------------------------
# MARKET & VALUATION DATA — colonne H uniquement (données point-in-time)
# D-G : tirets dans le template (pas injectés)
# Pourcentages en décimal : 0.21 pour 21%
# H108 WACC = FORMULE Excel — ne jamais injecter
# -----------------------------------------------------------------------------
MARKET_DATA = {
    "share_price":          {"H":"H95"},
    "shares_diluted":       {"H":"H96"},
    "beta_levered":         {"H":"H99"},
    "risk_free_rate":       {"H":"H100"},
    "erp":                  {"H":"H101"},
    "cost_of_debt_pretax":  {"H":"H103"},
    "tax_rate":             {"H":"H104"},
    "weight_equity":        {"H":"H106"},
    "weight_debt":          {"H":"H107"},
    # H108 WACC = FORMULE Excel — ne pas injecter
    "terminal_growth":      {"H":"H109"},
    "days_in_period":       {"H":"H110"},
}

# -----------------------------------------------------------------------------
# STOCK_DATA — onglet séparé, 13 points mensuels trailing 52 semaines
# Format mois : "Jan-25", "Feb-25" ... (MMM-YY en anglais, locale-indépendant)
# Toujours écrire 13 lignes (B3:C15), mettre None si moins de 13 points
# -----------------------------------------------------------------------------
STOCK_DATA = {
    "sheet_name": "STOCK_DATA",
    "month_col":  "B",
    "price_col":  "C",
    "start_row":  3,
    "end_row":    15,   # toujours aller jusqu'à 15 pour écraser les résidus template
    "month_format": "MMM-YY",  # ex: "Mar-26" — locale-indépendant (voir yfinance_source)
}

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def get_cell(section: dict, field: str, col: str) -> str:
    return section[field][col]

def get_column_cells(col: str) -> dict:
    result = {}
    for section in [INCOME_STATEMENT, BALANCE_SHEET_ASSETS,
                    BALANCE_SHEET_LIABILITIES, CASH_FLOW]:
        for field, cols in section.items():
            if col in cols:
                result[field] = cols[col]
    return result

def is_formula_cell(cell_ref: str) -> bool:
    """Retourne True si cell_ref est une cellule formule — ne jamais écrire dedans."""
    return cell_ref in _FORMULA_CELLS_SET
