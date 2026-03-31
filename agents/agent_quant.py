# =============================================================================
# FinSight IA — Agent Quant
# agents/agent_quant.py
#
# 33 ratios financiers — Python pur, zéro LLM, zéro API.
# Principe Intel/Watt (brief §5) : "Ne jamais utiliser un LLM pour ce
# qu'un script Python peut faire."
#
# Ratios couverts (33) :
#   Profitabilité (8) : gross_margin, ebitda_margin, ebit_margin, net_margin,
#                       roe, roa, roic, fcf_margin
#   Croissance (4)    : revenue_growth, ebitda_growth, gp_growth, fcf_growth
#   Levier (3)        : debt_equity, net_debt_ebitda, interest_coverage
#   Liquidité (2)     : current_ratio, quick_ratio
#   Efficacité (5)    : asset_turnover, dso, dio, dpo, ccc
#   Valorisation (5)  : pe_ratio, ev_ebitda, ev_revenue, pb_ratio, fcf_yield
#   Capital alloc.(3) : capex_ratio, rd_ratio, dividend_payout
#   Risque (3)        : altman_z, beneish_m, net_debt_ev
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional

from data.models import FinancialSnapshot, FinancialYear, MarketData

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper : division sécurisée
# ---------------------------------------------------------------------------

def _s(num, den, dp: int = 4, default=None):
    """Safe division. Retourne default si None ou division par zéro."""
    try:
        if num is None or den is None or den == 0:
            return default
        v = num / den
        return round(v, dp) if dp is not None else v
    except (TypeError, ZeroDivisionError):
        return default


def _pct(num, den, dp: int = 4):
    """Ratio en pourcentage (0.0 à 1.0)."""
    return _s(num, den, dp=dp)


def _g(v):
    """None-safe abs pour éviter ZeroDivision sur base = 0."""
    return v if v and v != 0 else None


# ---------------------------------------------------------------------------
# Dataclasses résultat
# ---------------------------------------------------------------------------

@dataclass
class YearRatios:
    """Tous les ratios calculés pour une année."""
    year: str

    # --- Valeurs intermédiaires (utiles pour le template Excel / Agent Quant) ---
    gross_profit:             Optional[float] = None
    ebit:                     Optional[float] = None
    ebitda:                   Optional[float] = None
    net_income:               Optional[float] = None
    fcf:                      Optional[float] = None
    total_current_assets:     Optional[float] = None
    total_current_liabilities:Optional[float] = None
    total_assets:             Optional[float] = None
    total_liabilities:        Optional[float] = None
    total_equity:             Optional[float] = None
    total_debt:               Optional[float] = None
    net_debt:                 Optional[float] = None
    market_cap:               Optional[float] = None
    ev:                       Optional[float] = None

    # --- Profitabilité (8) ---
    gross_margin:   Optional[float] = None   # GP / Revenue
    ebitda_margin:  Optional[float] = None   # EBITDA / Revenue
    ebit_margin:    Optional[float] = None   # EBIT / Revenue
    net_margin:     Optional[float] = None   # NI / Revenue
    roe:            Optional[float] = None   # NI / Equity
    roa:            Optional[float] = None   # NI / Total Assets
    roic:           Optional[float] = None   # NOPAT / (Equity + Net Debt)
    fcf_margin:     Optional[float] = None   # FCF / Revenue

    # --- Croissance YoY (4) ---
    revenue_growth:     Optional[float] = None
    ebitda_growth:      Optional[float] = None
    gp_growth:          Optional[float] = None
    fcf_growth:         Optional[float] = None

    # --- Levier (3) ---
    debt_equity:        Optional[float] = None   # Total Debt / Equity
    net_debt_ebitda:    Optional[float] = None   # Net Debt / EBITDA
    interest_coverage:  Optional[float] = None   # EBIT / Interest Expense

    # --- Liquidité (2) ---
    current_ratio:  Optional[float] = None   # CA / CL
    quick_ratio:    Optional[float] = None   # (CA - Inventory) / CL

    # --- Efficacité (5) ---
    asset_turnover:     Optional[float] = None   # Revenue / TA
    dso:                Optional[float] = None   # AR / Rev * 365
    dio:                Optional[float] = None   # Inv / COGS * 365
    dpo:                Optional[float] = None   # AP / COGS * 365
    ccc:                Optional[float] = None   # DSO + DIO - DPO

    # --- Valorisation (5) ---
    pe_ratio:   Optional[float] = None   # Market Cap / NI
    ev_ebitda:  Optional[float] = None   # EV / EBITDA
    ev_revenue: Optional[float] = None   # EV / Revenue
    pb_ratio:   Optional[float] = None   # Market Cap / Equity
    fcf_yield:  Optional[float] = None   # FCF / Market Cap

    # --- Capital allocation (3) ---
    capex_ratio:      Optional[float] = None   # |CapEx| / Revenue
    rd_ratio:         Optional[float] = None   # R&D / Revenue
    dividend_payout:  Optional[float] = None   # Dividends / NI

    # --- Risque (3) ---
    altman_z:       Optional[float] = None   # Altman Z-Score (public)
    altman_z_model: Optional[str]   = None   # "original_1968" | "nonmfg_1995"
    beneish_m:      Optional[float] = None   # Beneish M-Score (8-var)
    net_debt_ev:    Optional[float] = None   # Net Debt / EV

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RatiosResult:
    ticker:      str
    years:       dict         # {"2022": YearRatios, ...}
    latest_year: str
    projections: dict = field(default_factory=dict)  # {"2025F": FinancialYear, "2026F": FinancialYear}
    meta:        dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker":      self.ticker,
            "years":       {k: v.to_dict() for k, v in self.years.items()},
            "latest_year": self.latest_year,
            "meta":        self.meta,
        }


# ---------------------------------------------------------------------------
# Agent Quant
# ---------------------------------------------------------------------------

# Secteurs asset-light où le Z-Score non-manufacturing (1995) est approprié
# (X5 = CA/Actifs exclu — pénalise injustement les sociétés à actifs intangibles)
_ASSET_LIGHT_SECTORS = {
    "information technology", "technology", "software",
    "communication services", "communications", "media", "internet",
    "healthcare", "health care", "financials", "financial services",
    "real estate", "services",
}


def _is_asset_light(sector: str) -> bool:
    """Retourne True si le secteur est dominé par les actifs intangibles."""
    return bool(sector) and sector.lower().strip() in _ASSET_LIGHT_SECTORS


class AgentQuant:
    """
    Calcule 33 ratios financiers à partir d'un FinancialSnapshot.
    Zéro LLM, zéro API. Python pur.

    Constitution §1 : confidence_score proportionnel au coverage des champs.
    """

    def compute(
        self,
        snapshot: FinancialSnapshot,
    ) -> RatiosResult:
        """Point d'entrée principal."""
        years_ratios: dict[str, YearRatios] = {}
        prev_yr: Optional[YearRatios] = None

        # Années disponibles dans le snapshot (ordre chronologique)
        all_labels = sorted(snapshot.years.keys(), key=lambda y: int(y.split("_")[0]))

        for year_label in all_labels:
            fy = snapshot.years.get(year_label)
            if fy is None:
                continue
            yr = self._compute_year(fy, snapshot.market,
                                   sector=snapshot.company_info.sector or "")
            years_ratios[year_label] = yr

        # Croissance YoY (nécessite l'année précédente)
        for i, year_label in enumerate(all_labels):
            if i == 0:
                prev_yr = years_ratios.get(year_label)
                continue
            curr_yr = years_ratios.get(year_label)
            p_yr    = years_ratios.get(all_labels[i - 1])
            if curr_yr and p_yr:
                self._compute_growth(curr_yr, p_yr)
            prev_yr = curr_yr

        # Beneish M-Score (nécessite 2 ans consécutifs)
        for i in range(1, len(all_labels)):
            prev_label = all_labels[i - 1]
            curr_label = all_labels[i]
            p = snapshot.years.get(prev_label)
            c = snapshot.years.get(curr_label)
            curr_yr = years_ratios.get(curr_label)
            if p and c and curr_yr:
                curr_yr.beneish_m = self._beneish(
                    p, c,
                    years_ratios.get(prev_label),
                    curr_yr,
                )

        # Année la plus récente disponible
        latest = all_labels[-1] if all_labels else "latest"

        # WACC & paramètres de valorisation (injecte dans snapshot.market)
        self._compute_wacc_params(snapshot, all_labels, years_ratios)

        # Projections 2025F / 2026F (sector-driven)
        projections = self._compute_projections(snapshot, all_labels, years_ratios)

        # DCF déterministe + Monte Carlo (10 000 simulations numpy)
        mc_meta = self._compute_dcf_montecarlo(snapshot, all_labels, years_ratios, projections)

        coverages = [self._coverage(yr) for yr in years_ratios.values()]
        confidence = round(sum(coverages) / len(coverages), 2) if coverages else 0.0

        meta = {
            "computed_at":    date.today().isoformat(),
            "confidence_score": confidence,
            "invalidation_conditions": (
                "Ratios invalides si : "
                "(1) restatement comptable post-collecte, "
                "(2) changement de méthode comptable, "
                "(3) coverage données < 50%"
            ),
        }
        meta.update(mc_meta)

        return RatiosResult(
            ticker      = snapshot.ticker,
            years       = years_ratios,
            latest_year = latest,
            projections = projections,
            meta        = meta,
        )

    # ------------------------------------------------------------------
    # Calcul par année
    # ------------------------------------------------------------------

    def _compute_year(self, fy: FinancialYear, mkt: MarketData, sector: str = "") -> YearRatios:
        yr = YearRatios(year=fy.year)

        # --- Valeurs intermédiaires ---

        # Convention signes (yfinance) :
        # revenue, cogs, sga, rd, da : positifs (coûts et revenus)
        # capex : NÉGATIF (cash outflow)
        # interest_expense : positif (coût)

        # --- Gross Profit : priorité yfinance direct ---
        if fy.gross_profit_yf is not None:
            yr.gross_profit = fy.gross_profit_yf
        elif fy.revenue and fy.cogs:
            # abs() : sécurité si COGS négatif (certains tickers yfinance)
            yr.gross_profit = round(fy.revenue - abs(fy.cogs), 2)

        da_val  = fy.da  or 0.0
        sga_val = fy.sga or 0.0
        rd_val  = fy.rd  or 0.0

        # --- EBIT : priorité yfinance direct ---
        if fy.ebit_yf is not None:
            yr.ebit = fy.ebit_yf
        elif yr.gross_profit is not None:
            yr.ebit = round(yr.gross_profit - sga_val - rd_val - da_val, 2)

        if yr.ebit is not None:
            yr.ebitda = round(yr.ebit + da_val, 2)

        ie = fy.interest_expense or 0.0
        ii = fy.interest_income  or 0.0
        tx = fy.tax_expense_real or 0.0

        # --- Net Income : priorité yfinance direct ---
        if fy.net_income_yf is not None:
            yr.net_income = fy.net_income_yf
        elif yr.ebit is not None:
            ebt = yr.ebit - ie + ii
            yr.net_income = round(ebt - tx, 2)

        # FCF = Net Income + D&A + CapEx (CapEx négatif → soustraction)
        if yr.net_income is not None and fy.capex is not None:
            yr.fcf = round(yr.net_income + da_val + fy.capex, 2)

        # Bilan — actifs
        ca_items = [fy.cash, fy.accounts_receivable, fy.inventories, fy.other_current_assets]
        lt_items = [fy.ppe_net, fy.intangibles, fy.other_lt_assets]
        ca = sum(x for x in ca_items if x is not None)
        lt = sum(x for x in lt_items if x is not None)
        yr.total_current_assets = round(ca, 2) if any(x is not None for x in ca_items) else None
        yr.total_assets = round(ca + lt, 2) if (yr.total_current_assets is not None) else None

        # Bilan — passifs
        cl_items = [fy.accounts_payable, fy.short_term_debt,
                    fy.income_tax_payable, fy.other_current_liab]
        cl = sum(x for x in cl_items if x is not None)
        yr.total_current_liabilities = round(cl, 2) if any(x is not None for x in cl_items) else None

        ltd = fy.long_term_debt or 0.0
        yr.total_liabilities = round(cl + ltd, 2) if yr.total_current_liabilities is not None else None

        if yr.total_assets and yr.total_liabilities is not None:
            yr.total_equity = round(yr.total_assets - yr.total_liabilities, 2)

        yr.total_debt = round((fy.short_term_debt or 0.0) + (fy.long_term_debt or 0.0), 2)
        yr.net_debt   = round(yr.total_debt - (fy.cash or 0.0), 2)

        # --- Equity, Total Assets, Total Liabilities : priorité yfinance direct ---
        if fy.total_equity_yf is not None:
            yr.total_equity = fy.total_equity_yf
        # (sinon déjà calculé ci-dessus depuis le bilan partiel)

        if fy.total_assets_yf is not None:
            yr.total_assets = fy.total_assets_yf

        if fy.total_liabilities_yf is not None:
            yr.total_liabilities = fy.total_liabilities_yf

        # Marché (utilise le cours actuel — même pour les années historiques en V1)
        if mkt.share_price and mkt.shares_diluted:
            yr.market_cap = round(mkt.share_price * mkt.shares_diluted, 2)
            yr.ev = round(yr.market_cap + yr.net_debt, 2) if yr.net_debt is not None else None

        # --- Ratios de profitabilité ---
        yr.gross_margin  = _pct(yr.gross_profit, fy.revenue)
        yr.ebitda_margin = _pct(yr.ebitda,       fy.revenue)
        yr.ebit_margin   = _pct(yr.ebit,          fy.revenue)
        yr.net_margin    = _pct(yr.net_income,    fy.revenue)
        yr.roe           = _pct(yr.net_income,    yr.total_equity)
        yr.roa           = _pct(yr.net_income,    yr.total_assets)
        yr.fcf_margin    = _pct(yr.fcf,            fy.revenue)

        # ROIC = NOPAT / IC   (NOPAT = EBIT*(1-tax_rate), IC = Equity + Net Debt)
        if yr.ebit and yr.total_equity and yr.net_debt is not None:
            tax_rate = _s(tx, yr.ebit - ie + ii + tx) if (yr.ebit - ie + ii) else 0.21
            tax_rate = tax_rate if (tax_rate and 0 < tax_rate < 1) else 0.21
            nopat = yr.ebit * (1 - tax_rate)
            ic    = (yr.total_equity or 0) + (yr.net_debt or 0)
            yr.roic = _pct(nopat, ic) if ic != 0 else None

        # --- Levier ---
        yr.debt_equity     = _s(yr.total_debt,  yr.total_equity)
        yr.net_debt_ebitda = _s(yr.net_debt,    yr.ebitda)
        yr.interest_coverage = _s(yr.ebit, ie) if ie > 0 else None

        # --- Liquidité ---
        if yr.total_current_assets and yr.total_current_liabilities:
            yr.current_ratio = _s(yr.total_current_assets, yr.total_current_liabilities)
            inv = fy.inventories or 0.0
            yr.quick_ratio   = _s(yr.total_current_assets - inv,
                                  yr.total_current_liabilities)

        # --- Efficacité ---
        # cogs_abs : toujours positif pour DSO/DIO/DPO
        cogs_abs = abs(fy.cogs) if fy.cogs else None
        yr.asset_turnover = _pct(fy.revenue, yr.total_assets)
        if fy.inventories and cogs_abs and cogs_abs > 0:
            yr.inventory_turnover = _s(cogs_abs, fy.inventories, dp=2)
        yr.dso = _s((fy.accounts_receivable or 0) * 365, fy.revenue, dp=1)
        yr.dio = _s((fy.inventories or 0) * 365, cogs_abs, dp=1) if cogs_abs and cogs_abs > 0 else None
        yr.dpo = _s((fy.accounts_payable  or 0) * 365, cogs_abs, dp=1) if cogs_abs and cogs_abs > 0 else None
        if yr.dso is not None and yr.dio is not None and yr.dpo is not None:
            yr.ccc = round(yr.dso + yr.dio - yr.dpo, 1)

        # --- Valorisation ---
        yr.pe_ratio   = _s(yr.market_cap, yr.net_income,    dp=2)
        yr.ev_ebitda  = _s(yr.ev,         yr.ebitda,        dp=2)
        yr.ev_revenue = _s(yr.ev,         fy.revenue,       dp=2)
        yr.pb_ratio   = _s(yr.market_cap, yr.total_equity,  dp=2)
        yr.fcf_yield  = _pct(yr.fcf,      yr.market_cap)
        yr.net_debt_ev = _pct(yr.net_debt, yr.ev)

        # --- Capital allocation ---
        # CapEx est négatif → prendre la valeur absolue
        capex_abs = abs(fy.capex) if fy.capex is not None else None
        yr.capex_ratio     = _pct(capex_abs,     fy.revenue)
        yr.rd_ratio        = _pct(fy.rd,          fy.revenue)
        yr.dividend_payout = _pct(fy.dividends,   yr.net_income)

        # --- Altman Z-Score (modèle sélectionné selon secteur) ---
        yr.altman_z, yr.altman_z_model = self._compute_altman(fy, yr, sector)

        return yr

    # ------------------------------------------------------------------
    # Croissance YoY
    # ------------------------------------------------------------------

    def _compute_growth(self, curr: YearRatios, prev: YearRatios) -> None:
        def _growth(c, p):
            if c is None or p is None or p == 0:
                return None
            return round((c - p) / abs(p), 4)

        curr.revenue_growth = _growth(
            _rev_from_yr(curr), _rev_from_yr(prev)
        )
        curr.ebitda_growth = _growth(curr.ebitda, prev.ebitda)
        curr.gp_growth     = _growth(curr.gross_profit, prev.gross_profit)
        curr.fcf_growth    = _growth(curr.fcf,    prev.fcf)


    # ------------------------------------------------------------------
    # Altman Z-Score
    # ------------------------------------------------------------------

    def _compute_altman(
        self, fy: FinancialYear, yr: YearRatios, sector: str = ""
    ) -> tuple[Optional[float], Optional[str]]:
        """
        Sélectionne et calcule le bon modèle Altman Z selon le secteur.
        - Secteurs asset-light (tech, services, finance...) → modèle non-manufacturing 1995
        - Autres → modèle original 1968
        Retourne (score, modele_utilise).
        """
        if _is_asset_light(sector):
            return self._altman_z_nonmfg(fy, yr), "nonmfg_1995"
        else:
            return self._altman_z(fy, yr), "original_1968"

    def _altman_z(self, fy: FinancialYear, yr: YearRatios) -> Optional[float]:
        """
        Altman Z-Score original (1968) — sociétés manufacturières cotées :
        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        Seuils : Z > 2.99 Sain | 1.81–2.99 Zone grise | < 1.81 Détresse
        """
        ta = yr.total_assets
        if not ta or ta == 0:
            return None

        wc = (yr.total_current_assets or 0) - (yr.total_current_liabilities or 0)
        x1 = _s(wc, ta)

        # X2 = Retained Earnings / TA — direct si disponible, sinon approx
        if fy.retained_earnings_yf is not None:
            re_val = fy.retained_earnings_yf
        else:
            re_val = (yr.total_equity or 0) - (fy.common_equity_paid_in or 0)
        x2 = _s(re_val, ta)

        x3 = _s(yr.ebit, ta)

        x4 = _s(yr.market_cap, yr.total_liabilities) if yr.total_liabilities else None

        x5 = _s(fy.revenue, ta)

        if any(v is None for v in [x1, x2, x3, x4, x5]):
            return None

        z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
        return round(z, 2)

    def _altman_z_nonmfg(self, fy: FinancialYear, yr: YearRatios) -> Optional[float]:
        """
        Altman Z'-Score non-manufacturing (1995) — adapté aux sociétés asset-light :
        Z' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
        X4 = Book Value Equity / Total Liabilities  (valeur comptable, pas boursière)
        X5 (CA/Actifs) EXCLU — ce ratio pénalise injustement les sociétés à actifs intangibles.
        Seuils : Z' > 2.6 Sain | 1.1–2.6 Zone grise | < 1.1 Détresse
        """
        ta = yr.total_assets
        if not ta or ta == 0:
            return None

        wc = (yr.total_current_assets or 0) - (yr.total_current_liabilities or 0)
        x1 = _s(wc, ta)

        if fy.retained_earnings_yf is not None:
            re_val = fy.retained_earnings_yf
        else:
            re_val = (yr.total_equity or 0) - (fy.common_equity_paid_in or 0)
        x2 = _s(re_val, ta)

        x3 = _s(yr.ebit, ta)

        # X4 = Book Value Equity / Total Liabilities (pas market cap)
        x4 = _s(yr.total_equity, yr.total_liabilities) if yr.total_liabilities else None

        if any(v is None for v in [x1, x2, x3, x4]):
            return None

        z = 6.56*x1 + 3.26*x2 + 6.72*x3 + 1.05*x4
        return round(z, 2)

    # ------------------------------------------------------------------
    # Beneish M-Score (8 variables, nécessite 2 ans)
    # ------------------------------------------------------------------

    def _beneish(
        self,
        fy_prev: FinancialYear, fy_curr: FinancialYear,
        yr_prev: YearRatios,    yr_curr: YearRatios,
    ) -> Optional[float]:
        """
        Beneish M-Score 8 variables.
        M > -2.22 → possible manipulation comptable.
        """
        try:
            def _dsr():   # Days Sales Receivable Index
                if not fy_curr.revenue or not fy_prev.revenue: return None
                dso_c = _s((fy_curr.accounts_receivable or 0), fy_curr.revenue)
                dso_p = _s((fy_prev.accounts_receivable or 0), fy_prev.revenue)
                return _s(dso_c, dso_p)

            def _gmi():   # Gross Margin Index
                gm_c = _s((yr_curr.gross_profit or 0), fy_curr.revenue)
                gm_p = _s((yr_prev.gross_profit or 0), fy_prev.revenue)
                return _s(gm_p, gm_c)

            def _aqi():   # Asset Quality Index
                def aq(fy, yr):
                    if not yr.total_assets: return None
                    ca  = yr.total_current_assets or 0
                    ppe = fy.ppe_net or 0
                    return 1 - _s(ca + ppe, yr.total_assets)
                return _s(aq(fy_curr, yr_curr), aq(fy_prev, yr_prev))

            def _sgi():   # Sales Growth Index
                return _s(fy_curr.revenue, fy_prev.revenue)

            def _depi():  # Depreciation Index
                def dep_rate(fy):
                    return _s(fy.da or 0, (fy.da or 0) + (fy.ppe_net or 0))
                return _s(dep_rate(fy_prev), dep_rate(fy_curr))

            def _sgai():  # SGA Index
                return _s(
                    _s(fy_curr.sga or 0, fy_curr.revenue),
                    _s(fy_prev.sga or 0, fy_prev.revenue)
                )

            def _lvgi():  # Leverage Index
                lev_c = _s(yr_curr.total_liabilities, yr_curr.total_assets)
                lev_p = _s(yr_prev.total_liabilities, yr_prev.total_assets)
                return _s(lev_c, lev_p)

            def _tata():  # Total Accruals to Total Assets
                if not yr_curr.total_assets: return None
                d_ca   = (yr_curr.total_current_assets  or 0) - (yr_prev.total_current_assets  or 0)
                d_cash = (fy_curr.cash or 0) - (fy_prev.cash or 0)
                d_cl   = (yr_curr.total_current_liabilities or 0) - (yr_prev.total_current_liabilities or 0)
                d_std  = (fy_curr.short_term_debt or 0) - (fy_prev.short_term_debt or 0)
                da     = fy_curr.da or 0
                tata   = (d_ca - d_cash - d_cl + d_std - da) / yr_curr.total_assets
                return round(tata, 4)

            dsri = _dsr(); gmi = _gmi(); aqi = _aqi(); sgi = _sgi()
            depi = _depi(); sgai = _sgai(); lvgi = _lvgi(); tata = _tata()

            if any(v is None for v in [dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata]):
                return None

            m = (-4.84 + 0.92*dsri + 0.528*gmi + 0.404*aqi + 0.892*sgi
                 + 0.115*depi - 0.172*sgai + 4.679*tata - 0.327*lvgi)
            return round(m, 3)

        except Exception as e:
            log.debug(f"[AgentQuant] Beneish M-Score erreur : {e}")
            return None

    # ------------------------------------------------------------------
    # WACC & paramètres de valorisation
    # ------------------------------------------------------------------

    def _compute_wacc_params(self, snapshot, all_labels: list, years_ratios: dict) -> None:
        """
        Calcule et injecte dans snapshot.market :
          risk_free_rate (déjà présent depuis ^TNX), erp (0.055),
          cost_of_debt_pretax, tax_rate, weight_equity, weight_debt, wacc,
          terminal_growth (sector_ref), days_in_period=365.
        Modifie snapshot.market en place.
        """
        try:
            from config.sector_ref import get_sector_drivers
        except ImportError:
            log.warning("[AgentQuant] config.sector_ref introuvable — WACC non calculé")
            return

        mkt = snapshot.market
        if not all_labels:
            return

        try:
            latest_label = all_labels[-1]
            latest_fy    = snapshot.years.get(latest_label)
            latest_yr    = years_ratios.get(latest_label)
            if not latest_fy or not latest_yr:
                return

            sector = snapshot.company_info.sector or ""
            sd     = get_sector_drivers(sector)

            # --- ERP & RF ---
            erp = sd["erp"]          # prime de risque marché sectorielle
            mkt.erp = erp
            rf  = mkt.risk_free_rate or 0.04   # fallback 4% si ^TNX indispo
            if mkt.risk_free_rate is None:
                mkt.risk_free_rate = rf   # persiste le fallback pour affichage Streamlit

            # --- Coût des fonds propres (CAPM) ---
            beta = mkt.beta_levered or 1.0
            if mkt.beta_levered is None:
                mkt.beta_levered = beta   # fallback β=1 pour affichage
            ke   = rf + beta * erp

            # --- Coût de la dette pré-impôt ---
            ie         = abs(latest_fy.interest_expense or 0.0)
            total_debt = latest_yr.total_debt or 0.0
            if total_debt > 0 and ie > 0:
                kd = max(0.015, min(0.15, ie / total_debt))
            else:
                kd = rf + 0.015            # spread crédit par défaut +150 bps
            mkt.cost_of_debt_pretax = round(kd, 4)

            # --- Taux d'imposition effectif ---
            ie_val = abs(latest_fy.interest_expense or 0.0)
            ii_val = latest_fy.interest_income or 0.0
            ebt    = (latest_yr.ebit or 0.0) - ie_val + ii_val
            tax    = abs(latest_fy.tax_expense_real or 0.0)
            if ebt > 0 and tax > 0:
                tax_rate = max(0.05, min(0.40, round(tax / ebt, 4)))
            else:
                tax_rate = sd["tax_rate_default"]
            mkt.tax_rate = tax_rate

            # --- Pondérations capital ---
            mc = latest_yr.market_cap or 0.0
            if mc > 0:
                total_cap = mc + total_debt
                we = mc / total_cap
                wd = total_debt / total_cap
            else:
                we, wd = 0.70, 0.30
            mkt.weight_equity = round(we, 4)
            mkt.weight_debt   = round(wd, 4)

            # --- WACC ---
            kd_after = kd * (1 - tax_rate)
            wacc     = we * ke + wd * kd_after
            mkt.wacc = round(max(0.04, min(0.20, wacc)), 4)

            # --- Taux de croissance terminal ---
            mkt.terminal_growth = sd["terminal_growth"]

            # --- Jours dans la période ---
            mkt.days_in_period = 365

            log.info(
                f"[AgentQuant] WACC={mkt.wacc:.2%} "
                f"Ke={ke:.2%} Kd={kd:.2%} β={beta:.2f} "
                f"We={we:.0%} Wd={wd:.0%} TG={mkt.terminal_growth:.1%}"
            )
        except Exception as _e:
            log.error(f"[AgentQuant] _compute_wacc_params erreur : {_e}", exc_info=True)

    # ------------------------------------------------------------------
    # Projections 2025F / 2026F  — sector-driven
    # ------------------------------------------------------------------

    def _compute_projections(self, snapshot, all_labels: list, years_ratios: dict) -> dict:
        """
        Projette 2025F et 2026F en blendant CAGR historique + drivers sectoriels.
        Les marges convergent graduellement vers les cibles sectorielles.
        """
        from data.models import FinancialYear
        try:
            from config.sector_ref import get_sector_drivers
            sd = get_sector_drivers(snapshot.company_info.sector or "")
        except ImportError:
            sd = {
                "rev_growth": 0.05, "gross_margin_target": 0.35,
                "capex_pct_rev": 0.05, "da_pct_rev": 0.04, "sga_pct_rev": 0.14,
                "net_margin_target": 0.09,
            }

        if not all_labels:
            return {}

        latest_label = all_labels[-1]
        latest_fy    = snapshot.years.get(latest_label)
        latest_yr    = years_ratios.get(latest_label)
        if not latest_fy or not latest_fy.revenue:
            return {}

        rev0 = latest_fy.revenue

        # --- Taux de croissance : blend 60% historique / 40% sectoriel ---
        hist_cagr    = self._estimate_rev_growth(snapshot, all_labels)
        sector_growth = sd["rev_growth"]
        blended_growth = round(0.60 * hist_cagr + 0.40 * sector_growth, 4)

        def _r(v):
            return v / rev0 if (v is not None and rev0 > 0) else None

        # Ratios actuels (LTM)
        curr_gm    = (latest_yr.gross_margin   or 0) if latest_yr else 0
        curr_sga_r = _r(latest_fy.sga)
        curr_rd_r  = _r(latest_fy.rd)
        curr_da_r  = _r(latest_fy.da)  or sd["da_pct_rev"]
        curr_ie_r  = _r(abs(latest_fy.interest_expense or 0))
        curr_ii_r  = _r(latest_fy.interest_income or 0)
        curr_tx_r  = _r(abs(latest_fy.tax_expense_real or 0))

        # Cibles sectorielles
        tgt_gm  = sd["gross_margin_target"]
        tgt_capex_r = sd["capex_pct_rev"]   # positif, sera négativé à l'écriture
        tgt_sga_r   = sd.get("sga_pct_rev", curr_sga_r or 0.14)

        # Ratios bilan scalés sur revenue (stables)
        bs_ratios = {
            "cash":                 _r(latest_fy.cash),
            "accounts_receivable":  _r(latest_fy.accounts_receivable),
            "inventories":          _r(latest_fy.inventories),
            "other_current_assets": _r(latest_fy.other_current_assets),
            "ppe_net":              _r(latest_fy.ppe_net),
            "intangibles":          _r(latest_fy.intangibles),
            "other_lt_assets":      _r(latest_fy.other_lt_assets),
            "accounts_payable":     _r(latest_fy.accounts_payable),
            "short_term_debt":      _r(latest_fy.short_term_debt),
            "income_tax_payable":   _r(latest_fy.income_tax_payable),
            "other_current_liab":   _r(latest_fy.other_current_liab),
            "long_term_debt":       _r(latest_fy.long_term_debt),
            "common_equity_paid_in": _r(latest_fy.common_equity_paid_in),
        }

        projections = {}
        base_rev = rev0

        for i, proj_label in enumerate(["2025F", "2026F"]):
            # Taux légèrement décroissant à l'horizon 2
            growth   = blended_growth * (0.92 ** i)
            proj_rev = round(base_rev * (1 + growth), 2)
            # Facteur de convergence vers cibles sectorielles (0→yr1, 0.3→yr2)
            alpha = 0.15 + 0.15 * i

            def _blend(curr, tgt):
                if curr is None or curr == 0:
                    return tgt
                return curr * (1 - alpha) + tgt * alpha

            pfy = FinancialYear(year=proj_label)
            pfy.revenue = proj_rev

            # IS — marges projetées
            proj_gm = _blend(curr_gm, tgt_gm)
            pfy.cogs = round(proj_rev * (1 - proj_gm), 2)   # toujours positif en interne

            sga_r = _blend(curr_sga_r or tgt_sga_r, tgt_sga_r)
            pfy.sga = round(proj_rev * sga_r, 2) if sga_r else None

            pfy.rd               = round(proj_rev * curr_rd_r, 2) if curr_rd_r else None
            pfy.da               = round(proj_rev * curr_da_r, 2) if curr_da_r else None
            pfy.interest_expense = round(proj_rev * curr_ie_r, 2) if curr_ie_r else None
            pfy.interest_income  = round(proj_rev * curr_ii_r, 2) if curr_ii_r else None
            pfy.tax_expense_real = round(proj_rev * curr_tx_r, 2) if curr_tx_r else None

            # CapEx — cible sectorielle (positif en interne, sera négativé Excel)
            pfy.capex = -round(proj_rev * tgt_capex_r, 2)   # négatif (cash outflow)

            # Bilan — scalé sur revenue
            for field, ratio in bs_ratios.items():
                if ratio is not None:
                    setattr(pfy, field, round(proj_rev * ratio, 2))

            projections[proj_label] = pfy
            base_rev = proj_rev

        return projections

    def _estimate_rev_growth(self, snapshot, all_labels: list) -> float:
        """CAGR historique du CA, clampé entre -10% et +25%. Défaut 5%."""
        revs = []
        for label in all_labels:
            fy = snapshot.years.get(label)
            if fy and fy.revenue and fy.revenue > 0:
                revs.append(fy.revenue)

        if len(revs) >= 2:
            n = len(revs) - 1
            try:
                cagr = (revs[-1] / revs[0]) ** (1 / n) - 1
                return max(-0.10, min(0.25, round(cagr, 4)))
            except (ValueError, ZeroDivisionError):
                pass
        return 0.05

    def _coverage(self, yr: YearRatios) -> float:
        ratio_fields = [
            "gross_margin", "ebitda_margin", "ebit_margin", "net_margin",
            "roe", "roa", "fcf_margin", "debt_equity", "net_debt_ebitda",
            "current_ratio", "dso", "pe_ratio", "ev_ebitda", "capex_ratio",
            "altman_z",
        ]
        filled = sum(1 for f in ratio_fields if getattr(yr, f, None) is not None)
        return filled / len(ratio_fields)


    # ------------------------------------------------------------------
    # DCF déterministe — 5 ans + valeur terminale Gordon-Growth
    # ------------------------------------------------------------------

    def _compute_dcf(
        self,
        rev0: float,
        ebitda_margin0: float,
        capex_pct: float,
        da_pct: float,
        tax_rate: float,
        wacc: float,
        terminal_growth: float,
        rev_growth: float,
        n_years: int = 5,
    ) -> Optional[float]:
        """
        DCF déterministe par actualisation des FCF sur n_years.
        FCF = EBIT*(1-tax) + DA - CapEx  (approx NOPAT-based)
        Valeur terminale = FCF_n * (1+TG) / (WACC - TG)
        """
        if wacc <= terminal_growth or wacc <= 0 or rev0 <= 0:
            return None
        pv = 0.0
        rev = rev0
        for t in range(1, n_years + 1):
            rev     = rev * (1 + rev_growth)
            ebitda  = rev * ebitda_margin0
            da      = rev * da_pct
            ebit    = ebitda - da
            nopat   = ebit * (1 - tax_rate)
            capex   = rev * capex_pct
            fcf     = nopat + da - capex
            df      = (1 + wacc) ** t
            pv     += fcf / df

        # Valeur terminale (Gordon-Growth sur FCF de l'année n)
        fcf_tv = fcf * (1 + terminal_growth)
        tv     = fcf_tv / (wacc - terminal_growth)
        pv    += tv / ((1 + wacc) ** n_years)
        return pv

    # ------------------------------------------------------------------
    # Monte Carlo DCF — 10 000 simulations numpy vectorisé
    # ------------------------------------------------------------------

    def _compute_dcf_montecarlo(
        self,
        snapshot,
        all_labels: list,
        years_ratios: dict,
        projections: dict,
        n_sim: int = 10_000,
        n_years: int = 5,
    ) -> dict:
        """
        10 000 simulations Monte Carlo sur :
          - rev_growth    ~ Normal(mu=blended, sigma=sectorial)
          - ebitda_margin ~ Normal(mu=curr, sigma=sectorial)
          - wacc          ~ Triangular(low=wacc_min, mode=wacc, high=wacc_max)
        Output : dcf_value (P50), dcf_mc_p10, dcf_mc_p50, dcf_mc_p90 (par action)
        """
        try:
            import numpy as np
        except ImportError:
            log.warning("[AgentQuant] numpy absent — Monte Carlo DCF ignore")
            return {}

        try:
            from config.sector_ref import get_sector_drivers
            sd = get_sector_drivers(snapshot.company_info.sector or "")
        except ImportError:
            return {}

        if not all_labels:
            return {}

        latest_label = all_labels[-1]
        latest_fy    = snapshot.years.get(latest_label)
        latest_yr    = years_ratios.get(latest_label)
        mkt          = snapshot.market

        if not latest_fy or not latest_fy.revenue or latest_fy.revenue <= 0:
            return {}

        rev0          = latest_fy.revenue
        shares        = mkt.shares_diluted if mkt.shares_diluted and mkt.shares_diluted > 0 else None
        wacc_mode     = mkt.wacc          or 0.09
        terminal_growth = mkt.terminal_growth or sd["terminal_growth"]
        tax_rate      = mkt.tax_rate      or sd["tax_rate_default"]

        # Paramètres mu (valeurs observées blendées avec sectorielles)
        mu_rev_growth = (0.60 * self._estimate_rev_growth(snapshot, all_labels)
                         + 0.40 * sd["rev_growth"])
        mu_ebitda_margin = (latest_yr.ebitda_margin if latest_yr and latest_yr.ebitda_margin
                            else sd["ebitda_margin_target"])
        capex_pct     = sd["capex_pct_rev"]
        da_pct        = sd["da_pct_rev"]

        # Sigma sectoriels
        sigma_rev    = sd.get("sigma_rev_growth",    0.035)
        sigma_ebitda = sd.get("sigma_ebitda_margin", 0.030)
        wacc_low     = sd.get("wacc_min", max(0.04, wacc_mode - 0.025))
        wacc_high    = sd.get("wacc_max", min(0.20, wacc_mode + 0.025))

        # --- Génération des distributions (N_SIM vecteurs) ---
        rng = np.random.default_rng(seed=42)   # reproductible

        rev_growth_arr    = rng.normal(mu_rev_growth, sigma_rev, n_sim)
        ebitda_margin_arr = rng.normal(mu_ebitda_margin, sigma_ebitda, n_sim)
        # Triangulaire WACC
        wacc_arr = rng.triangular(wacc_low, wacc_mode, wacc_high, n_sim)

        # Clampage pour éviter les outliers aberrants
        rev_growth_arr    = np.clip(rev_growth_arr,    -0.15, 0.40)
        ebitda_margin_arr = np.clip(ebitda_margin_arr,  0.02, 0.80)
        wacc_arr          = np.clip(wacc_arr,           0.04, 0.20)

        # Filtre WACC > TG (nécessaire pour la valeur terminale)
        valid = wacc_arr > (terminal_growth + 0.005)

        # --- Calcul vectorisé des FCF sur n_years ---
        pv_total = np.zeros(n_sim)
        rev_sim  = np.full(n_sim, rev0, dtype=float)

        for t in range(1, n_years + 1):
            rev_sim  = rev_sim * (1 + rev_growth_arr)
            ebitda_s = rev_sim * ebitda_margin_arr
            da_s     = rev_sim * da_pct
            ebit_s   = ebitda_s - da_s
            nopat_s  = ebit_s * (1 - tax_rate)
            capex_s  = rev_sim * capex_pct
            fcf_s    = nopat_s + da_s - capex_s
            df       = (1 + wacc_arr) ** t
            pv_total += np.where(valid, fcf_s / df, 0.0)

        # Valeur terminale Gordon-Growth
        fcf_tv  = fcf_s * (1 + terminal_growth)
        tv_arr  = np.where(valid, fcf_tv / (wacc_arr - terminal_growth), 0.0)
        pv_total += np.where(valid, tv_arr / ((1 + wacc_arr) ** n_years), 0.0)

        # Valeur par action (si shares disponibles)
        if shares and shares > 0:
            # pv_total en unités de la devise (M ou B selon rev0 scale)
            pv_per_share = pv_total / shares
        else:
            pv_per_share = pv_total   # valeur totale (sans per-share)

        # Filtrer les valeurs invalides (wacc <= tg)
        valid_vals = pv_per_share[valid & (pv_per_share > 0)]

        if len(valid_vals) < 100:
            log.warning("[AgentQuant] Monte Carlo : trop peu de simulations valides")
            return {}

        # Percentiles P10 / P50 / P90 (P2/P98 pour clipper les extrêmes)
        p2, p10, p50, p90, p98 = np.percentile(valid_vals, [2, 10, 50, 90, 98])

        import time as _time
        log.info(
            f"[AgentQuant] Monte Carlo DCF — "
            f"P10={p10:.2f} P50={p50:.2f} P90={p90:.2f} "
            f"({len(valid_vals)}/{n_sim} simulations valides)"
        )

        # Echantillon 300 valeurs pour histogramme PDF (downsampled, compact)
        rng2 = np.random.default_rng(seed=99)
        _sample_idx = rng2.choice(len(valid_vals), size=min(300, len(valid_vals)), replace=False)
        mc_dist_sample = [round(float(v), 2) for v in valid_vals[_sample_idx]]

        return {
            "dcf_value":    round(float(p50), 2),
            "dcf_mc_p10":   round(float(p10), 2),
            "dcf_mc_p50":   round(float(p50), 2),
            "dcf_mc_p90":   round(float(p90), 2),
            "dcf_mc_p2":    round(float(p2),  2),
            "dcf_mc_p98":   round(float(p98), 2),
            "dcf_mc_n_sim": int(len(valid_vals)),
            "dcf_mc_n_valid": int(len(valid_vals)),
            "mc_dist":      mc_dist_sample,
            "dcf_mc_mu_rev_growth":    round(float(mu_rev_growth), 4),
            "dcf_mc_mu_ebitda_margin": round(float(mu_ebitda_margin), 4),
            "dcf_mc_wacc_mode":        round(float(wacc_mode), 4),
        }


def _rev_from_yr(yr: YearRatios) -> Optional[float]:
    """Revenue inféré depuis les ratios (pas stocké dans YearRatios)."""
    # Gross Profit / Gross Margin = Revenue
    if yr.gross_profit and yr.gross_margin:
        return _s(yr.gross_profit, yr.gross_margin)
    return None
