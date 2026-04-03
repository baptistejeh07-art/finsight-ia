# =============================================================================
# FinSight IA -- Agent Macro
# agents/agent_macro.py
#
# Regime de marche + probabilite de recession via yfinance (gratuit, sans cle).
# Principe : zero API key, zero dependance externe supplementaire.
#
# Indicateurs utilises :
#   ^VIX  : Fear gauge (CBOE Volatility Index)
#   ^TNX  : US 10Y Treasury yield
#   ^IRX  : US 13-week T-Bill yield (proxy 3M)
#   ^GSPC : S&P 500 (tendance + MA50/MA200)
# =============================================================================

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# --- Seuils regime ---------------------------------------------------------
_VIX_STRESS   = 25.0   # VIX > 25 = stress eleve
_VIX_ELEVATED = 20.0   # VIX > 20 = vigilance
_VIX_CALM     = 18.0   # VIX < 18 = environnement calme
_SPREAD_INVERT = -0.20  # spread 10Y-3M < -0.20% = inversion significative


def _last(series) -> Optional[float]:
    """Derniere valeur non-NaN d'une serie pandas."""
    try:
        v = series.dropna().iloc[-1]
        return float(v)
    except (IndexError, TypeError, ValueError, AttributeError):
        return None


class AgentMacro:
    """
    Calcule le regime de marche et la probabilite de recession.
    Utilise uniquement yfinance -- zero API key requise.
    """

    def analyze(self, index_ticker: str = "^GSPC") -> dict:
        """
        Retourne un dict avec toutes les donnees macro.
        En cas d'echec, retourne un dict de fallback sans lever d'exception.
        """
        try:
            return self._compute()
        except Exception as e:
            log.warning("[AgentMacro] Erreur: %s -- fallback utilise", e)
            return self._fallback()

    # -------------------------------------------------------------------------

    def _compute(self) -> dict:
        import yfinance as yf
        import pandas as pd

        # Telecharger les 4 series en une fois pour limiter les appels reseau
        tickers_str = "^VIX ^TNX ^IRX ^GSPC"
        raw = yf.download(tickers_str, period="1y", interval="1d",
                          progress=False, auto_adjust=True)

        close = raw["Close"] if "Close" in raw.columns else raw

        vix   = _last(close["^VIX"])   if "^VIX"  in close.columns else None
        tnx   = _last(close["^TNX"])   if "^TNX"  in close.columns else None
        irx   = _last(close["^IRX"])   if "^IRX"  in close.columns else None

        spx_series = close["^GSPC"].dropna() if "^GSPC" in close.columns else pd.Series()
        spx_last   = _last(spx_series)
        ma200 = float(spx_series.tail(200).mean()) if len(spx_series) >= 40 else None
        ma50  = float(spx_series.tail(50).mean())  if len(spx_series) >= 20 else None

        # --- Spread 10Y - 3M ------------------------------------------------
        spread = round(tnx - irx, 2) if (tnx is not None and irx is not None) else None

        # --- S&P vs MA200 ---------------------------------------------------
        sp_vs_ma200 = None
        sp500_trend = "Inconnu"
        if spx_last and ma200 and ma200 > 0:
            sp_vs_ma200 = round((spx_last - ma200) / ma200 * 100, 1)
            sp500_trend = "Haussier" if sp_vs_ma200 > 0 else "Baissier"

        # --- Momentum 6M (perf depuis 126 jours) ----------------------------
        sp_mom_6m = None
        if len(spx_series) >= 126:
            p0 = float(spx_series.iloc[-126])
            p1 = float(spx_series.iloc[-1])
            if p0 > 0:
                sp_mom_6m = round((p1 - p0) / p0 * 100, 1)

        # --- Regime ---------------------------------------------------------
        regime = self._classify_regime(vix, spread, sp_vs_ma200)

        # --- Recession ------------------------------------------------------
        rec_data = self._recession_score(vix, spread, sp_vs_ma200, sp_mom_6m)

        return {
            "regime":               regime,
            "vix":                  round(vix, 1)   if vix   is not None else None,
            "tnx_10y":              round(tnx, 2)   if tnx   is not None else None,
            "irx_3m":               round(irx, 2)   if irx   is not None else None,
            "yield_spread_10y_3m":  spread,
            "sp500_vs_ma200":       sp_vs_ma200,
            "sp500_trend":          sp500_trend,
            "sp500_mom_6m":         sp_mom_6m,
            **rec_data,
        }

    # -------------------------------------------------------------------------

    def _classify_regime(self, vix, spread, sp_vs_ma200) -> str:
        if vix is None:
            return "Inconnu"
        inverted  = spread is not None and spread < _SPREAD_INVERT
        above_ma  = sp_vs_ma200 is not None and sp_vs_ma200 > 0
        stressed  = vix > _VIX_STRESS
        elevated  = vix > _VIX_ELEVATED

        if not elevated and above_ma and not inverted:
            return "Bull"
        elif stressed and not above_ma:
            return "Bear"
        elif elevated or (inverted and not above_ma):
            return "Volatile"
        else:
            return "Transition"

    # -------------------------------------------------------------------------

    def _recession_score(self, vix, spread, sp_vs_ma200, sp_mom_6m) -> dict:
        """
        Probabilite de recession indicative a 6M et 12M.
        Basee sur 4 indicateurs de marche gratuits.
        Note : indicateur de marche, pas un modele econometrique.
        """
        score     = 0
        max_score = 0
        drivers   = []

        # -- Critere 1 : Courbe des taux (poids 40) --------------------------
        if spread is not None:
            max_score += 40
            if spread < -0.50:
                score += 40
                drivers.append(f"Courbe inversee ({spread:+.1f}% spread 10Y-3M) -- signal recessif fort")
            elif spread < 0:
                score += 25
                drivers.append(f"Courbe plate/inversee ({spread:+.1f}%)")
            elif spread < 0.80:
                score += 10

        # -- Critere 2 : VIX (poids 25) -------------------------------------
        if vix is not None:
            max_score += 25
            if vix > 30:
                score += 25
                drivers.append(f"VIX a {vix:.0f} -- stress de marche eleve")
            elif vix > _VIX_STRESS:
                score += 16
                drivers.append(f"VIX a {vix:.0f} -- vigilance")
            elif vix > _VIX_ELEVATED:
                score += 8

        # -- Critere 3 : S&P vs MA200 (poids 20) ----------------------------
        if sp_vs_ma200 is not None:
            max_score += 20
            if sp_vs_ma200 < -10:
                score += 20
                drivers.append(f"S&P 500 {sp_vs_ma200:.1f}% sous la MA200")
            elif sp_vs_ma200 < -3:
                score += 12
                drivers.append(f"S&P 500 sous la MA200 ({sp_vs_ma200:.1f}%)")
            elif sp_vs_ma200 < 0:
                score += 5

        # -- Critere 4 : Momentum 6M (poids 15) -----------------------------
        if sp_mom_6m is not None:
            max_score += 15
            if sp_mom_6m < -15:
                score += 15
                drivers.append(f"Momentum 6M negatif ({sp_mom_6m:+.1f}%)")
            elif sp_mom_6m < -5:
                score += 8
            elif sp_mom_6m < 0:
                score += 3

        if max_score == 0:
            return {
                "recession_prob_6m":   None,
                "recession_prob_12m":  None,
                "recession_level":     "Inconnu",
                "recession_drivers":   [],
            }

        raw = score / max_score * 100
        prob_6m  = round(raw, 0)
        prob_12m = round(min(raw * 1.25, 100), 0)

        level = ("Faible" if prob_6m < 25 else
                 "Modérée" if prob_6m < 55 else "Élevée")

        return {
            "recession_prob_6m":   int(prob_6m),
            "recession_prob_12m":  int(prob_12m),
            "recession_level":     level,
            "recession_drivers":   drivers[:3],
        }

    # -------------------------------------------------------------------------

    @staticmethod
    def _fallback() -> dict:
        return {
            "regime":               "Inconnu",
            "vix":                  None,
            "tnx_10y":              None,
            "irx_3m":               None,
            "yield_spread_10y_3m":  None,
            "sp500_vs_ma200":       None,
            "sp500_trend":          "Inconnu",
            "sp500_mom_6m":         None,
            "recession_prob_6m":    None,
            "recession_prob_12m":   None,
            "recession_level":      "Inconnu",
            "recession_drivers":    [],
        }
