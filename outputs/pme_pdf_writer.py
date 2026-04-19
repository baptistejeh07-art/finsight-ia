"""
PDF writer PME — rapport 12-15 pages style contrôle de gestion.

Structure :
  P1  : Couverture + résumé chiffres clés
  P2  : Identité + dirigeants + BODACC
  P3  : SIG détaillés 5 ans
  P4  : Rentabilité (marges + ROCE + ROE)
  P5  : Solidité financière + trésorerie
  P6  : Efficacité opérationnelle
  P7  : Croissance + trajectoire
  P8  : Scoring détresse (Altman + FinSight)
  P9  : Benchmark pairs sectoriels
  P10 : Bankabilité + capacité dette
  P11 : Synthèse
  P12 : Disclaimer MiFID II + sources

Pas de LLM côté PDF (le LLM écrit juste les commentaires narratifs injectés).
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from core.pappers.analytics import PmeAnalysis, YearAccounts, SIG, Ratios
from core.pappers.benchmark import BenchmarkResult
from core.pappers.bodacc_client import BodaccSummary
from core.pappers.sector_profiles import SectorProfile

log = logging.getLogger(__name__)


# ==============================================================================
# Styles
# ==============================================================================

NAVY = "#1B2A4A"
NAVY_LIGHT = "#3A5288"
INK_900 = "#171717"
INK_700 = "#404040"
INK_500 = "#737373"
INK_200 = "#E5E5E5"
INK_100 = "#F0F0F0"
GREEN = "#15803D"
AMBER = "#D97706"
RED = "#DC2626"


def _fmt_eur(v: float | None, unit: str = "€") -> str:
    if v is None:
        return "—"
    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"{v / 1_000_000_000:,.1f} Md{unit}".replace(",", " ")
    if abs_v >= 1_000_000:
        return f"{v / 1_000_000:,.1f} M{unit}".replace(",", " ")
    if abs_v >= 1_000:
        return f"{v / 1_000:,.0f} k{unit}".replace(",", " ")
    return f"{v:,.0f} {unit}".replace(",", " ")


def _fmt_pct(v: float | None, decimals: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v * 100:,.{decimals}f} %".replace(",", " ").replace(".", ",")


def _fmt_x(v: float | None, decimals: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{decimals}f}x".replace(",", " ").replace(".", ",")


def _fmt_days(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.0f} j"


def _color_for_rank(rank: str) -> str:
    return {"top_25": GREEN, "above_median": GREEN, "below_median": AMBER, "bottom_25": RED}.get(rank, INK_500)


def _color_for_score(score: float | None) -> str:
    if score is None:
        return INK_500
    if score >= 70:
        return GREEN
    if score >= 40:
        return AMBER
    return RED


# ==============================================================================
# PmePdfWriter
# ==============================================================================

@dataclass
class PmePdfContext:
    """Tout ce dont le writer a besoin pour produire le PDF."""
    siren: str
    denomination: str
    forme_juridique: str | None
    code_naf: str | None
    libelle_naf: str | None
    ville_siege: str | None
    date_creation: str | None
    capital: float | None
    dirigeants: list[dict[str, Any]]
    analysis: PmeAnalysis
    benchmark: BenchmarkResult
    yearly_accounts: list[YearAccounts]  # indispensable pour le CA / années
    bodacc: BodaccSummary | None = None
    commentaires: dict[str, str] | None = None  # {section_code: texte LLM}
    language: str = "fr"   # i18n : fr / en / es / de / it / pt
    currency: str = "EUR"  # devise d'affichage


class PmePdfWriter:
    """Générateur PDF ReportLab 12-15 pages."""

    def __init__(self, ctx: PmePdfContext):
        self.ctx = ctx
        # Helper i18n local : self._t("report.synthesis") → libellé selon langue
        from core.i18n import t as _i18n_t, field_label as _i18n_field, ratio_label as _i18n_ratio, sig_label as _i18n_sig, normalize_language
        self._lang = normalize_language(ctx.language)
        self._t = lambda key, default=None: _i18n_t(self._lang, key, default)
        self._field_label = lambda field: _i18n_field(field, self._lang)
        self._ratio_label = lambda key: _i18n_ratio(key, self._lang)
        self._sig_label = lambda key: _i18n_sig(key, self._lang)
        self._imports_ok = False
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, KeepTogether,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm, mm
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
            self.A4 = A4
            self.SimpleDocTemplate = SimpleDocTemplate
            self.Paragraph = Paragraph
            self.Spacer = Spacer
            self.Table = Table
            self.TableStyle = TableStyle
            self.PageBreak = PageBreak
            self.KeepTogether = KeepTogether
            self.getSampleStyleSheet = getSampleStyleSheet
            self.ParagraphStyle = ParagraphStyle
            self.cm = cm
            self.mm = mm
            self.colors = colors
            self.TA_LEFT = TA_LEFT
            self.TA_CENTER = TA_CENTER
            self.TA_JUSTIFY = TA_JUSTIFY
            self.TA_RIGHT = TA_RIGHT
            self._imports_ok = True
        except ImportError as e:
            log.error("[pme_pdf] reportlab non installé : %s", e)

    def generate(self, output_path: str | Path) -> Path:
        if not self._imports_ok:
            raise RuntimeError("reportlab requis : pip install reportlab")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = self.SimpleDocTemplate(
            str(output_path),
            pagesize=self.A4,
            leftMargin=self.cm * 2, rightMargin=self.cm * 2,
            topMargin=self.cm * 1.8, bottomMargin=self.cm * 1.8,
            title=f"Analyse financière — {self.ctx.denomination}",
        )

        story: list = []
        self._page_cover(story)
        story.append(self.PageBreak())
        self._page_identity(story)
        story.append(self.PageBreak())
        self._page_sig(story)
        story.append(self.PageBreak())
        self._page_rentabilite(story)
        story.append(self.PageBreak())
        self._page_solidite(story)
        story.append(self.PageBreak())
        self._page_efficacite(story)
        story.append(self.PageBreak())
        self._page_croissance(story)
        story.append(self.PageBreak())
        self._page_scoring(story)
        story.append(self.PageBreak())
        self._page_benchmark(story)
        story.append(self.PageBreak())
        self._page_bankabilite(story)
        story.append(self.PageBreak())
        self._page_synthese(story)
        story.append(self.PageBreak())
        self._page_disclaimer(story)

        doc.build(story)
        return output_path

    # ==========================================================================
    # Styles Paragraph
    # ==========================================================================

    def _styles(self):
        s = self.getSampleStyleSheet()
        return {
            "title": self.ParagraphStyle(
                "T", parent=s["Title"], fontSize=24, textColor=self.colors.HexColor(NAVY),
                alignment=self.TA_CENTER, spaceAfter=12, leading=28,
            ),
            "subtitle": self.ParagraphStyle(
                "ST", parent=s["Heading2"], fontSize=11, textColor=self.colors.HexColor(INK_500),
                alignment=self.TA_CENTER, spaceAfter=20,
            ),
            "h1": self.ParagraphStyle(
                "H1", parent=s["Heading1"], fontSize=16, textColor=self.colors.HexColor(NAVY),
                spaceBefore=6, spaceAfter=10, leading=20,
            ),
            "h2": self.ParagraphStyle(
                "H2", parent=s["Heading2"], fontSize=12, textColor=self.colors.HexColor(NAVY),
                spaceBefore=10, spaceAfter=6, leading=15,
            ),
            "body": self.ParagraphStyle(
                "B", parent=s["BodyText"], fontSize=10, textColor=self.colors.HexColor(INK_700),
                alignment=self.TA_JUSTIFY, spaceAfter=6, leading=14,
            ),
            "small": self.ParagraphStyle(
                "S", parent=s["BodyText"], fontSize=8, textColor=self.colors.HexColor(INK_500),
                leading=10,
            ),
            "header": self.ParagraphStyle(
                "HDR", parent=s["BodyText"], fontSize=9, textColor=self.colors.HexColor(INK_500),
                alignment=self.TA_RIGHT, spaceAfter=3,
            ),
        }

    def _kpi_table(self, items: list[tuple[str, str]]) -> Any:
        """Tableau 2 colonnes libellé | valeur (style KPI)."""
        data = [[k, v] for k, v in items]
        t = self.Table(data, colWidths=[self.cm * 7, self.cm * 5], hAlign="LEFT")
        t.setStyle(self.TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), self.colors.HexColor(INK_500)),
            ("TEXTCOLOR", (1, 0), (1, -1), self.colors.HexColor(INK_900)),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.3, self.colors.HexColor(INK_100)),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    # ==========================================================================
    # Pages
    # ==========================================================================

    def _page_cover(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Spacer(1, self.cm * 4))
        story.append(self.Paragraph(self._t("report.title"), st["subtitle"]))
        story.append(self.Paragraph(ctx.denomination, st["title"]))
        meta = []
        if ctx.forme_juridique: meta.append(ctx.forme_juridique)
        if ctx.ville_siege: meta.append(ctx.ville_siege)
        if ctx.libelle_naf: meta.append(ctx.libelle_naf)
        story.append(self.Paragraph(" · ".join(meta), st["subtitle"]))
        story.append(self.Spacer(1, self.cm * 2))

        # Chiffres clés
        last_year = max(ctx.analysis.sig_by_year.keys()) if ctx.analysis.sig_by_year else None
        if last_year:
            sig = ctx.analysis.sig_by_year[last_year]
            items = [
                (self._sig_label("chiffre_affaires"), _fmt_eur(
                    next((y.chiffre_affaires for _, y in self._yearly_iter() if y.annee == last_year), None)
                )),
                ("EBE", _fmt_eur(sig.ebe)),
                (self._sig_label("resultat_net"), _fmt_eur(sig.resultat_net)),
                ("Score santé FinSight",
                 f"{ctx.analysis.health_score:.0f} / 100" if ctx.analysis.health_score else "—"),
                ("Altman Z",
                 f"{ctx.analysis.altman_z:.2f} ({ctx.analysis.altman_verdict})" if ctx.analysis.altman_z else "—"),
            ]
            story.append(self._kpi_table(items))

        story.append(self.Spacer(1, self.cm * 3))
        story.append(self.Paragraph(
            f"SIREN {ctx.siren} · Profil sectoriel : {ctx.analysis.profile.name}",
            st["small"],
        ))
        story.append(self.Paragraph(
            f"Rapport généré le {date.today().strftime('%d/%m/%Y')} par FinSight IA",
            st["small"],
        ))

    def _page_identity(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.identity_governance"), st["h1"]))

        items = [
            ("Dénomination", ctx.denomination),
            ("SIREN", ctx.siren),
            ("Forme juridique", ctx.forme_juridique or "—"),
            ("Code NAF", f"{ctx.code_naf or '—'} · {ctx.libelle_naf or ''}"),
            ("Ville du siège", ctx.ville_siege or "—"),
            ("Date de création", ctx.date_creation or "—"),
            ("Capital social", _fmt_eur(ctx.capital)),
        ]
        story.append(self._kpi_table(items))

        story.append(self.Spacer(1, self.cm * 0.5))
        story.append(self.Paragraph(self._t("report.directors"), st["h2"]))
        if ctx.dirigeants:
            data = [["Nom", "Qualité", "Date prise de poste"]]
            for d in ctx.dirigeants[:10]:
                nom = f"{d.get('prenom', '')} {d.get('nom', '')}".strip() or d.get('denomination') or "—"
                data.append([nom, d.get('qualite') or "—", d.get('date_prise_de_poste') or "—"])
            t = self.Table(data, colWidths=[self.cm * 6, self.cm * 5, self.cm * 4], hAlign="LEFT")
            t.setStyle(self.TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), self.colors.HexColor(INK_100)),
                ("TEXTCOLOR", (0, 0), (-1, -1), self.colors.HexColor(INK_900)),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, self.colors.HexColor(INK_200)),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(t)

        if ctx.bodacc:
            story.append(self.Spacer(1, self.cm * 0.5))
            story.append(self.Paragraph(self._t("report.bodacc"), st["h2"]))
            b = ctx.bodacc
            bodacc_items = [
                ("Annonces totales", str(b.total_annonces)),
                ("Procédures collectives", str(len(b.procedures_collectives))),
                ("Dernière procédure", b.derniere_procedure or "Aucune"),
                ("Dernier dépôt de comptes", b.dernier_depot_comptes or "—"),
                ("Société radiée", "Oui" if b.radie else "Non"),
                ("Modifications récentes (2 ans)", str(b.modifications_recentes)),
            ]
            story.append(self._kpi_table(bodacc_items))

    def _page_sig(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.sig"), st["h1"]))
        story.append(self.Paragraph(
            "Les SIG décomposent la création de valeur : de la production à la CAF en passant "
            "par la VA et l'EBE. Conforme au Plan Comptable Général français.",
            st["body"],
        ))

        years = sorted(ctx.analysis.sig_by_year.keys())
        if not years:
            story.append(self.Paragraph(self._t("report.no_accounts_data"), st["body"]))
            return

        # Table SIG : ligne = indicateur, col = année
        headers = ["Indicateur"] + [str(y) for y in years]
        rows = [headers]
        sig_rows = [
            (self._sig_label("chiffre_affaires"), lambda y, s: next(
                (acc.chiffre_affaires for _, acc in self._yearly_iter() if acc.annee == y), None
            )),
            (self._sig_label("production_exercice"), lambda y, s: s.production_exercice),
            (self._sig_label("valeur_ajoutee"), lambda y, s: s.valeur_ajoutee),
            (self._sig_label("ebe"), lambda y, s: s.ebe),
            (self._sig_label("resultat_exploitation"), lambda y, s: s.resultat_exploitation),
            (self._sig_label("resultat_net"), lambda y, s: s.resultat_net),
            (self._sig_label("caf"), lambda y, s: s.capacite_autofinancement),
        ]
        for label, extractor in sig_rows:
            row = [label]
            for y in years:
                sig = ctx.analysis.sig_by_year[y]
                v = extractor(y, sig)
                row.append(_fmt_eur(v))
            rows.append(row)

        col_widths = [self.cm * 5] + [self.cm * 2.5] * len(years)
        t = self.Table(rows, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
        t.setStyle(self.TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), self.colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.colors.white),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 1), (-1, -2), 0.3, self.colors.HexColor(INK_100)),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)

        self._add_commentaire(story, "sig", st)

    def _page_rentabilite(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.profitability"), st["h1"]))

        last_year = max(ctx.analysis.ratios_by_year.keys()) if ctx.analysis.ratios_by_year else None
        if last_year is None:
            story.append(self.Paragraph(self._t("report.no_ratios"), st["body"]))
            return

        r = ctx.analysis.ratios_by_year[last_year]
        profile = ctx.analysis.profile
        items = [
            (self._ratio_label("marge_brute"), _fmt_pct(r.marge_brute)),
            (self._ratio_label("marge_ebitda"), _fmt_pct(r.marge_ebitda)),
            (self._ratio_label("marge_nette"), _fmt_pct(r.marge_nette)),
            (self._ratio_label("roce"), _fmt_pct(r.roce)),
            (self._ratio_label("roe"), _fmt_pct(r.roe)),
        ]
        story.append(self._kpi_table(items))

        self._add_commentaire(story, "rentabilite", st)

    def _page_solidite(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.solvency"), st["h1"]))

        last_year = max(ctx.analysis.ratios_by_year.keys()) if ctx.analysis.ratios_by_year else None
        if last_year is None:
            story.append(self.Paragraph(self._t("report.no_data"), st["body"]))
            return

        r = ctx.analysis.ratios_by_year[last_year]
        items = [
            (self._ratio_label("dette_nette_ebitda"), _fmt_x(r.dette_nette_ebitda)),
            (self._ratio_label("couverture_interets"), _fmt_x(r.couverture_interets)),
            (self._ratio_label("autonomie_financiere"), _fmt_pct(r.autonomie_financiere)),
            (self._ratio_label("bfr_jours_ca"), _fmt_days(r.bfr_jours_ca)),
            (self._ratio_label("tresorerie_nette"), _fmt_eur(r.tresorerie_nette)),
        ]
        story.append(self._kpi_table(items))

        self._add_commentaire(story, "solidite", st)

    def _page_efficacite(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.efficiency"), st["h1"]))

        last_year = max(ctx.analysis.ratios_by_year.keys()) if ctx.analysis.ratios_by_year else None
        if last_year is None:
            story.append(self.Paragraph(self._t("report.no_data"), st["body"]))
            return

        r = ctx.analysis.ratios_by_year[last_year]
        items = [
            (self._ratio_label("dso_jours"), _fmt_days(r.dso_jours)),
            (self._ratio_label("dpo_jours"), _fmt_days(r.dpo_jours)),
            (self._ratio_label("rotation_stocks"), _fmt_x(r.rotation_stocks, 1)),
            (self._ratio_label("ca_par_employe"), _fmt_eur(r.ca_par_employe)),
            (self._ratio_label("charges_perso_ca"), _fmt_pct(r.charges_perso_ca)),
        ]
        story.append(self._kpi_table(items))

        self._add_commentaire(story, "efficacite", st)

    def _page_croissance(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.growth_trajectory"), st["h1"]))

        g = ctx.analysis.growth
        items = [
            ("Période analysée", f"{g.nb_annees} années"),
            ("CAGR chiffre d'affaires", _fmt_pct(g.cagr_ca)),
            ("CAGR EBITDA", _fmt_pct(g.cagr_ebitda)),
            ("CAGR résultat net", _fmt_pct(g.cagr_resultat_net)),
            ("Évolution marge EBITDA",
             f"{g.tendance_marge_ebitda * 100:+.1f} pts" if g.tendance_marge_ebitda is not None else "—"),
        ]
        story.append(self._kpi_table(items))
        self._add_commentaire(story, "croissance", st)

    def _page_scoring(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.distress_scoring"), st["h1"]))

        items = [
            ("Altman Z-Score (non coté)",
             f"{ctx.analysis.altman_z:.2f}" if ctx.analysis.altman_z else "—"),
            ("Verdict Altman",
             {"safe": "Zone saine", "grey": "Zone grise", "distress": "Détresse probable",
              "non_calculable": "Non calculable"}.get(ctx.analysis.altman_verdict, "—")),
            ("Score santé FinSight",
             f"{ctx.analysis.health_score:.0f} / 100" if ctx.analysis.health_score is not None else "—"),
        ]
        if ctx.bodacc:
            items.append(("Pénalité BODACC",
                          f"{ctx.bodacc.bodacc_score_penalty:+.0f}" if ctx.bodacc.bodacc_score_penalty else "0"))
        story.append(self._kpi_table(items))

        story.append(self.Spacer(1, self.cm * 0.3))
        story.append(self.Paragraph(
            "Interprétation Altman Z (non-manufacturing) : <br/>"
            "• Z > 2.60 : zone saine (risque faible de défaillance à 2 ans)<br/>"
            "• 1.10 ≤ Z ≤ 2.60 : zone grise (vigilance)<br/>"
            "• Z < 1.10 : détresse probable (risque élevé)",
            st["small"],
        ))
        self._add_commentaire(story, "scoring", st)

    def _page_benchmark(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.sector_benchmark"), st["h1"]))

        bm = ctx.benchmark
        story.append(self.Paragraph(
            f"Source : {'peers réels' if bm.source == 'peers_real' else 'médianes sectorielles'} "
            f"({bm.n_peers} peers)",
            st["small"],
        ))

        # Table benchmark
        rows = [["Ratio", "Cible", "Médiane secteur", "Position"]]
        rank_labels = {
            "top_25": "Top 25%", "above_median": "Au-dessus médiane",
            "below_median": "Sous médiane", "bottom_25": "Bottom 25%",
            "unknown": "—",
        }
        for _, name, higher, label_fr in [
            ("marge_ebitda", "marge_ebitda", True, "Marge EBITDA"),
            ("marge_nette", "marge_nette", True, "Marge nette"),
            ("roce", "roce", True, "ROCE"),
            ("dette_nette_ebitda", "dette_nette_ebitda", False, "Dette/EBITDA"),
            ("autonomie_financiere", "autonomie_financiere", True, "Autonomie financière"),
            ("bfr_jours_ca", "bfr_jours_ca", False, "BFR jours"),
            ("charges_perso_ca", "charges_perso_ca", False, "Charges perso/CA"),
        ]:
            q = bm.ratios.get(name)
            if q is None:
                continue
            is_pct = name in {"marge_ebitda", "marge_nette", "roce", "roe", "marge_brute",
                              "autonomie_financiere", "charges_perso_ca"}
            if is_pct:
                val = _fmt_pct(q.value)
                med = _fmt_pct(q.q50)
            elif name in {"bfr_jours_ca", "dso_jours", "dpo_jours"}:
                val = _fmt_days(q.value)
                med = _fmt_days(q.q50)
            else:
                val = _fmt_x(q.value)
                med = _fmt_x(q.q50)
            rows.append([label_fr, val, med, rank_labels.get(q.rank, "—")])

        col_widths = [self.cm * 5, self.cm * 3, self.cm * 3.5, self.cm * 4]
        t = self.Table(rows, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
        t.setStyle(self.TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), self.colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.colors.white),
            ("ALIGN", (1, 0), (2, -1), "RIGHT"),
            ("LINEBELOW", (0, 1), (-1, -2), 0.3, self.colors.HexColor(INK_100)),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)

        if bm.forces:
            story.append(self.Spacer(1, self.cm * 0.3))
            story.append(self.Paragraph(
                "<b>Forces relatives :</b> " + ", ".join(bm.forces),
                st["body"],
            ))
        if bm.faiblesses:
            story.append(self.Paragraph(
                "<b>Faiblesses relatives :</b> " + ", ".join(bm.faiblesses),
                st["body"],
            ))

    def _page_bankabilite(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.bankability"), st["h1"]))
        items = [
            ("Score bankabilité",
             f"{ctx.analysis.bankability_score:.0f} / 100" if ctx.analysis.bankability_score is not None else "—"),
            ("Capacité d'endettement additionnel estimée (cible 3× EBITDA)",
             _fmt_eur(ctx.analysis.debt_capacity_estimate)),
        ]
        story.append(self._kpi_table(items))
        story.append(self.Spacer(1, self.cm * 0.3))
        story.append(self.Paragraph(
            "Le score bankabilité synthétise les 4 ratios que les banques regardent en priorité "
            "pour évaluer un dossier : dette nette/EBITDA, couverture des intérêts, "
            "autonomie financière, et CAF/CA.",
            st["body"],
        ))
        self._add_commentaire(story, "bankabilite", st)

    def _page_synthese(self, story: list) -> None:
        st = self._styles()
        ctx = self.ctx
        story.append(self.Paragraph(self._t("report.synthesis"), st["h1"]))
        synth = (ctx.commentaires or {}).get("synthese")
        if synth:
            story.append(self.Paragraph(synth, st["body"]))
        else:
            story.append(self.Paragraph(
                "Synthèse générée par l'analyse FinSight à partir des données Pappers et des "
                "ratios calculés. Consultez chaque section pour le détail.",
                st["body"],
            ))

    def _page_disclaimer(self, story: list) -> None:
        st = self._styles()
        story.append(self.Paragraph(self._t("report.warning_sources"), st["h1"]))
        story.append(self.Paragraph(
            "Cette analyse est basée sur les données publiques disponibles via les registres "
            "officiels (Pappers, recherche-entreprises.api.gouv.fr, BODACC) et sur les comptes "
            "fournis soit par l'utilisateur, soit par la liasse fiscale publiée au greffe.",
            st["body"],
        ))
        story.append(self.Spacer(1, self.cm * 0.3))
        story.append(self.Paragraph(
            "<b>Elle ne constitue pas un conseil en investissement, fiscal ou juridique</b> "
            "au sens de la directive MiFID II. Les ratios calculés, les benchmarks sectoriels "
            "et les scores sont fournis à titre indicatif et ne sauraient se substituer à une "
            "expertise comptable ou financière certifiée.",
            st["body"],
        ))
        story.append(self.Spacer(1, self.cm * 0.5))
        story.append(self.Paragraph(self._t("report.sources"), st["h2"]))
        story.append(self.Paragraph(
            "• <b>Pappers API v2</b> — identité, dirigeants, comptes annuels (liasses fiscales Cerfa 2050-2053)<br/>"
            "• <b>recherche-entreprises.api.gouv.fr</b> — annuaire officiel État FR (identification peers)<br/>"
            "• <b>BODACC open data</b> — procédures collectives, publications légales<br/>"
            "• <b>INSEE ESANE</b> — médianes sectorielles par NAF<br/>"
            "• <b>Moteur analytique FinSight</b> — SIG, ratios, scoring propriétaire",
            st["body"],
        ))

    # ==========================================================================
    # Utils
    # ==========================================================================

    def _yearly_iter(self):
        """Itère sur (annee, YearAccounts) depuis le contexte."""
        for acc in sorted(self.ctx.yearly_accounts, key=lambda a: a.annee):
            yield (acc.annee, acc)

    def _add_commentaire(self, story: list, section: str, st: dict) -> None:
        c = (self.ctx.commentaires or {}).get(section)
        if c:
            story.append(self.Spacer(1, self.cm * 0.3))
            story.append(self.Paragraph(c, st["body"]))


# ==============================================================================
# Helper public
# ==============================================================================

def write_pme_pdf(
    ctx: PmePdfContext,
    output_path: str | Path,
) -> Path:
    """Raccourci : instancie writer et génère."""
    return PmePdfWriter(ctx).generate(output_path)
