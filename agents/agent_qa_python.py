# =============================================================================
# FinSight IA — Agent QA Python
# agents/agent_qa_python.py
#
# Validations statistiques et logiques pures (zero LLM).
# Input  : FinancialSnapshot + RatiosResult + SynthesisResult
# Output : QAResult (flags, warnings, score)
#
# Checks :
#   - Coherence ratios (Net Margin <= Gross Margin, etc.)
#   - Cibles prix realistes vs cours actuel
#   - Recommandation vs profil financier
#   - Altman Z / Beneish M flags
#   - Constitution : confidence_score + invalidation_conditions
# =============================================================================

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modele de resultat
# ---------------------------------------------------------------------------

@dataclass
class QAFlag:
    """Un probleme detecte par le QA Python."""
    level:    str    # "INFO" | "WARNING" | "ERROR"
    code:     str    # identifiant court ex. "MARGIN_INCONSISTENCY"
    message:  str


@dataclass
class QAResult:
    """
    Resultat Agent QA Python.
    Constitution S1 : confidence_score + invalidation_conditions presents.
    """
    ticker:            str
    passed:            bool           # True = aucune erreur bloquante
    flags:             List[QAFlag]   = field(default_factory=list)
    qa_score:          float          = 1.0   # [0,1] degradé par flags
    confidence_score:  float          = 0.9   # par defaut élevé (règles deterministes)
    invalidation_conditions: str      = "Si les données sources sont erronées ou falsifiées."
    meta:              dict           = field(default_factory=dict)

    @property
    def warnings(self) -> List[QAFlag]:
        return [f for f in self.flags if f.level == "WARNING"]

    @property
    def errors(self) -> List[QAFlag]:
        return [f for f in self.flags if f.level == "ERROR"]

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "passed": self.passed,
            "qa_score": self.qa_score,
            "flags": [{"level": f.level, "code": f.code, "message": f.message}
                      for f in self.flags],
            "confidence_score": self.confidence_score,
            "invalidation_conditions": self.invalidation_conditions,
            "meta": self.meta,
        }


# ---------------------------------------------------------------------------
# Agent QA Python
# ---------------------------------------------------------------------------

class AgentQAPython:
    """
    Agent QA Python — validations deterministiques sans LLM.
    Chaque check ajoute un flag INFO/WARNING/ERROR.
    """

    # Penalites sur qa_score par flag level
    _PENALTIES = {"INFO": 0.0, "WARNING": 0.05, "ERROR": 0.15}

    def validate(
        self,
        snapshot,
        ratios,
        synthesis,
    ) -> QAResult:
        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ticker     = snapshot.ticker

        log.info(f"[AgentQAPython] Validation '{ticker}' — {request_id[:8]}")

        flags: List[QAFlag] = []

        latest = ratios.latest_year
        yr     = ratios.years.get(latest)
        ci     = snapshot.company_info
        mkt    = snapshot.market

        # ------------------------------------------------------------------
        # 1. Cohérence marges
        # ------------------------------------------------------------------
        if yr:
            gm = yr.gross_margin
            nm = yr.net_margin
            eb = yr.ebitda_margin
            op = yr.ebit_margin

            if gm is not None and nm is not None and nm > gm + 0.01:
                flags.append(QAFlag("ERROR", "MARGIN_INCONSISTENCY",
                    f"Net Margin ({nm:.1%}) > Gross Margin ({gm:.1%}) — impossible."))

            if gm is not None and eb is not None and eb > gm + 0.01:
                flags.append(QAFlag("ERROR", "MARGIN_INCONSISTENCY",
                    f"EBITDA Margin ({eb:.1%}) > Gross Margin ({gm:.1%}) — impossible."))

            if op is not None and eb is not None and op > eb + 0.01:
                flags.append(QAFlag("ERROR", "MARGIN_INCONSISTENCY",
                    f"EBIT Margin ({op:.1%}) > EBITDA Margin ({eb:.1%}) — impossible."))

            if nm is not None and nm < -0.50:
                flags.append(QAFlag("WARNING", "NEGATIVE_MARGIN_EXTREME",
                    f"Net Margin {nm:.1%} — perte extreme, verifier les donnees."))

            if nm is not None and nm > 0.60:
                flags.append(QAFlag("WARNING", "MARGIN_SUSPECT",
                    f"Net Margin {nm:.1%} — tres elevé, possible erreur de donnees."))

        # ------------------------------------------------------------------
        # 2. Altman Z-Score
        # ------------------------------------------------------------------
        if yr and yr.altman_z is not None:
            z = yr.altman_z
            if z < 1.81:
                flags.append(QAFlag("ERROR", "ALTMAN_DISTRESS",
                    f"Altman Z={z:.2f} < 1.81 — zone de detresse financiere."))
            elif z < 2.99:
                flags.append(QAFlag("WARNING", "ALTMAN_GREY",
                    f"Altman Z={z:.2f} entre 1.81 et 2.99 — zone grise."))
            else:
                flags.append(QAFlag("INFO", "ALTMAN_SAFE",
                    f"Altman Z={z:.2f} > 2.99 — situation financiere saine."))

        # ------------------------------------------------------------------
        # 3. Beneish M-Score
        # ------------------------------------------------------------------
        if yr and yr.beneish_m is not None:
            m = yr.beneish_m
            if m > -2.22:
                flags.append(QAFlag("WARNING", "BENEISH_MANIPULATION_RISK",
                    f"Beneish M={m:.3f} > -2.22 — risque de manipulation comptable."))
            else:
                flags.append(QAFlag("INFO", "BENEISH_OK",
                    f"Beneish M={m:.3f} <= -2.22 — pas de signal de manipulation."))

        # ------------------------------------------------------------------
        # 4. Levier financier
        # ------------------------------------------------------------------
        if yr and yr.net_debt_ebitda is not None:
            lev = yr.net_debt_ebitda
            if lev > 5.0:
                flags.append(QAFlag("ERROR", "LEVERAGE_EXTREME",
                    f"Net Debt/EBITDA={lev:.2f}x — levier critique (>5x)."))
            elif lev > 3.5:
                flags.append(QAFlag("WARNING", "LEVERAGE_HIGH",
                    f"Net Debt/EBITDA={lev:.2f}x — levier eleve (>3.5x)."))

        # ------------------------------------------------------------------
        # 5. Cibles prix vs cours actuel
        # ------------------------------------------------------------------
        if synthesis and mkt.share_price and mkt.share_price > 0:
            price = mkt.share_price

            def _check_target(name, target):
                if target is None:
                    return
                ratio = target / price
                if ratio < 0.20 or ratio > 5.0:
                    flags.append(QAFlag("WARNING", "TARGET_PRICE_EXTREME",
                        f"Cible {name}={target} vs cours={price:.2f} — ecart >80% suspect."))

            _check_target("base", synthesis.target_base)
            _check_target("bull", synthesis.target_bull)
            _check_target("bear", synthesis.target_bear)

            # bull > base > bear
            tb = synthesis.target_bull
            tbase = synthesis.target_base
            tbear = synthesis.target_bear
            if tb is not None and tbase is not None and tb < tbase:
                flags.append(QAFlag("ERROR", "TARGET_PRICE_ORDER",
                    f"Bull ({tb}) < Base ({tbase}) — ordre des scenarios incorrect."))
            if tbase is not None and tbear is not None and tbase < tbear:
                flags.append(QAFlag("ERROR", "TARGET_PRICE_ORDER",
                    f"Base ({tbase}) < Bear ({tbear}) — ordre des scenarios incorrect."))

        # ------------------------------------------------------------------
        # 6. Recommendation vs profil financier
        # ------------------------------------------------------------------
        if synthesis and yr:
            rec = synthesis.recommendation
            issues = []

            # BUY sur societe en detresse Altman ?
            if rec == "BUY" and yr.altman_z is not None and yr.altman_z < 1.81:
                issues.append(f"BUY avec Altman Z={yr.altman_z:.2f} (detresse)")

            # BUY avec levier excessif ET marge negative ?
            if (rec == "BUY"
                    and yr.net_debt_ebitda is not None and yr.net_debt_ebitda > 5
                    and yr.net_margin is not None and yr.net_margin < 0):
                issues.append(f"BUY avec levier {yr.net_debt_ebitda:.1f}x et marge negative")

            # SELL avec ROE > 20% et marge > 15% ?
            if (rec == "SELL"
                    and yr.roe is not None and yr.roe > 0.20
                    and yr.net_margin is not None and yr.net_margin > 0.15):
                issues.append(f"SELL avec ROE={yr.roe:.1%} et marge={yr.net_margin:.1%}")

            for issue in issues:
                flags.append(QAFlag("WARNING", "RECO_PROFILE_MISMATCH",
                    f"Recommandation vs profil : {issue}"))

        # ------------------------------------------------------------------
        # 7. Conviction et confidence_score
        # ------------------------------------------------------------------
        if synthesis:
            if synthesis.conviction < 0.3 and synthesis.recommendation in ("BUY", "SELL"):
                flags.append(QAFlag("WARNING", "LOW_CONVICTION",
                    f"Conviction {synthesis.conviction:.0%} faible pour une reco {synthesis.recommendation}."))

            if not synthesis.invalidation_conditions.strip():
                flags.append(QAFlag("ERROR", "MISSING_INVALIDATION",
                    "invalidation_conditions vide — condition constitutionnelle non respectee."))

            if synthesis.confidence_score < 0.3:
                flags.append(QAFlag("WARNING", "LOW_CONFIDENCE",
                    f"confidence_score {synthesis.confidence_score:.0%} tres faible."))

        # ------------------------------------------------------------------
        # 8. Données manquantes critiques
        # ------------------------------------------------------------------
        if yr:
            critical_fields = {
                "gross_margin": yr.gross_margin,
                "net_margin": yr.net_margin,
                "ebitda_margin": yr.ebitda_margin,
                "roe": yr.roe,
            }
            missing = [k for k, v in critical_fields.items() if v is None]
            if missing:
                flags.append(QAFlag("WARNING", "MISSING_CRITICAL_RATIOS",
                    f"Ratios critiques absents : {', '.join(missing)}"))
        else:
            flags.append(QAFlag("ERROR", "NO_RATIO_DATA",
                "Aucun ratio disponible — AgentQuant n'a pas produit de donnees."))

        # ------------------------------------------------------------------
        # 9. Qualité des bénéfices — Sloan Accruals / Cash Conversion / CapEx
        # ------------------------------------------------------------------
        sloan_ratio_val: Optional[float] = None
        all_labels_qa = sorted(
            ratios.years.keys(),
            key=lambda y: int(y.split("_")[0])
        )

        # 9a — Sloan Accruals Ratio
        # Accruals = (ΔActif courant - ΔTréso) - (ΔPassif courant - ΔDette CT - ΔImpôts)
        # Ratio    = Accruals / Actif total moyen — seuil > 5 % WARNING
        if len(all_labels_qa) >= 2:
            lp, lc = all_labels_qa[-2], all_labels_qa[-1]
            fyp = snapshot.years.get(lp)
            fyc = snapshot.years.get(lc)
            yrp = ratios.years.get(lp)
            yrc = ratios.years.get(lc)
            if fyp and fyc and yrp and yrc:
                ta_p = yrp.total_assets
                ta_c = yrc.total_assets
                ca_p = yrp.total_current_assets
                ca_c = yrc.total_current_assets
                cl_p = yrp.total_current_liabilities
                cl_c = yrc.total_current_liabilities
                if all(v is not None for v in [ta_p, ta_c, ca_p, ca_c, cl_p, cl_c]) and (ta_p + ta_c) > 0:
                    d_ca   = ca_c - ca_p
                    d_cash = (fyc.cash or 0) - (fyp.cash or 0)
                    d_cl   = cl_c - cl_p
                    d_std  = (fyc.short_term_debt or 0) - (fyp.short_term_debt or 0)
                    d_tax  = (fyc.income_tax_payable or 0) - (fyp.income_tax_payable or 0)
                    accruals = (d_ca - d_cash) - (d_cl - d_std - d_tax)
                    ta_avg   = (ta_p + ta_c) / 2
                    sloan_ratio_val = round(accruals / ta_avg, 4)
                    if abs(sloan_ratio_val) > 0.05:
                        flags.append(QAFlag("WARNING", "SLOAN_ACCRUALS_HIGH",
                            f"Sloan Accruals={sloan_ratio_val:.1%} > 5% — "
                            f"accruals eleves, qualite benefices a surveiller."))
                    else:
                        flags.append(QAFlag("INFO", "SLOAN_ACCRUALS_OK",
                            f"Sloan Accruals={sloan_ratio_val:.1%} — qualite benefices correcte."))

        # 9b — Cash Conversion Score : FCF / NI < 0.7 sur 3 ans consecutifs
        if len(all_labels_qa) >= 2:
            cc_series: list[float] = []
            for lbl in all_labels_qa:
                yr_r = ratios.years.get(lbl)
                if yr_r and yr_r.net_income and yr_r.net_income > 0 and yr_r.fcf is not None:
                    cc_series.append(yr_r.fcf / yr_r.net_income)
            if cc_series:
                consec = max_consec = 0
                for cc in cc_series:
                    if cc < 0.7:
                        consec += 1
                        max_consec = max(max_consec, consec)
                    else:
                        consec = 0
                if max_consec >= 3:
                    flags.append(QAFlag("WARNING", "CASH_CONVERSION_LOW",
                        f"FCF/NI < 0.7 sur {max_consec} ans consecutifs — "
                        f"benefices peu convertis en cash."))
                else:
                    avg_cc = sum(cc_series) / len(cc_series)
                    flags.append(QAFlag("INFO", "CASH_CONVERSION_OK",
                        f"Cash Conversion moyenne={avg_cc:.1%} — adequat."))

        # 9c — Divergence FCF vs Net Income
        if len(all_labels_qa) >= 2:
            lp2, lc2 = all_labels_qa[-2], all_labels_qa[-1]
            yrp2 = ratios.years.get(lp2)
            yrc2 = ratios.years.get(lc2)
            if yrp2 and yrc2:
                ni_p2 = yrp2.net_income
                ni_c2 = yrc2.net_income
                fcf_p2 = yrp2.fcf
                fcf_c2 = yrc2.fcf
                if (ni_p2 and ni_p2 > 0 and ni_c2 is not None
                        and fcf_p2 is not None and fcf_c2 is not None):
                    ni_growth = (ni_c2 - ni_p2) / abs(ni_p2)
                    fcf_delta = fcf_c2 - fcf_p2
                    if ni_growth > 0.20 and fcf_delta <= 0:
                        flags.append(QAFlag("WARNING", "FCF_NI_DIVERGENCE",
                            f"Net Income +{ni_growth:.0%} YoY mais FCF "
                            f"stagne/decline ({fcf_delta:+.0f}) — "
                            f"manipulation accruals probable."))

        # 9d — CapEx discipline : maintenance ≈ D&A, croissance = CapEx - D&A
        if latest in snapshot.years:
            fy_lat = snapshot.years[latest]
            if fy_lat.capex is not None and fy_lat.da and fy_lat.da > 0:
                capex_abs   = abs(fy_lat.capex)
                maint_capex = min(capex_abs, fy_lat.da)
                growth_capex = max(0.0, capex_abs - fy_lat.da)
                growth_pct  = growth_capex / capex_abs if capex_abs > 0 else 0
                flags.append(QAFlag("INFO", "CAPEX_DISCIPLINE",
                    f"CapEx: maintenance={maint_capex:.0f} ({1 - growth_pct:.0%}), "
                    f"croissance={growth_capex:.0f} ({growth_pct:.0%})."))

        # ------------------------------------------------------------------
        # Score et verdict
        # ------------------------------------------------------------------
        score = 1.0
        for f in flags:
            score -= self._PENALTIES.get(f.level, 0)
        score = max(0.0, score)

        has_errors = any(f.level == "ERROR" for f in flags)
        passed = not has_errors

        latency_ms = int((time.time() - t_start) * 1000)

        log.info(
            f"[AgentQAPython] '{ticker}' — passed={passed} "
            f"score={score:.2f} flags={len(flags)} ({latency_ms}ms)"
        )

        return QAResult(
            ticker   = ticker,
            passed   = passed,
            flags    = flags,
            qa_score = round(score, 3),
            meta = {
                "request_id":   request_id,
                "latency_ms":   latency_ms,
                "flags_count":  len(flags),
                "errors_count": sum(1 for f in flags if f.level == "ERROR"),
                "warnings_count": sum(1 for f in flags if f.level == "WARNING"),
                "latest_year":  latest,
                "sloan_ratio":  sloan_ratio_val,   # consommé par AgentEntryZone
            },
        )
