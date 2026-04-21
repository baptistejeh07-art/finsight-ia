"use client";

import { useEffect, useState, useMemo, use } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  AlertTriangle,
} from "lucide-react";
import { Footer } from "@/components/footer";
import { getFileUrl, getJob } from "@/lib/api";

import type { AnalysisData, RawData, RatiosData, Synthesis } from "@/components/dashboard/types";
import { HeaderSociete } from "@/components/dashboard/header-societe";
import { RecoCard } from "@/components/dashboard/reco-card";
import { FinSightScoreBadge } from "@/components/dashboard/finsight-score-badge";
import { CommentsPanel } from "@/components/dashboard/comments-panel";
import { CoursChart } from "@/components/dashboard/cours-chart";
import { PerformanceCard } from "@/components/dashboard/performance-card";
import { ValorisationCards } from "@/components/dashboard/valorisation-cards";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { CapexFcfChart } from "@/components/dashboard/capex-fcf-chart";
import { PeersTable } from "@/components/dashboard/peers-table";
import { MktCapDonut } from "@/components/dashboard/mktcap-donut";
import { CompareCard } from "@/components/dashboard/compare-card";
import { SyntheseCard } from "@/components/dashboard/synthese-card";
import { QAChat } from "@/components/dashboard/qa-chat";
import { PourAllerPlusLoin } from "@/components/dashboard/pour-aller-plus-loin";
import { PortraitCard } from "@/components/dashboard/portrait-card";
import { Glossaire } from "@/components/dashboard/glossaire";
import { RevealOnScroll } from "@/components/dashboard/reveal-on-scroll";
import { Editable } from "@/components/editable";
import { WarningsBanner } from "@/components/dashboard/warnings-banner";
import { SortableSections } from "@/components/dashboard/sortable-sections";
import { EditableGrid, type GridBlock } from "@/components/dashboard/editable-grid";
import { SectorTickersTable } from "@/components/dashboard/sector-tickers-table";
import { SectorMktCapDonut } from "@/components/dashboard/sector-mktcap-donut";
import { IndiceSectorsDonut } from "@/components/dashboard/indice-sectors-donut";
import { SectorPortraitCard } from "@/components/dashboard/sector-portrait-card";
import { SectorCompareLauncher } from "@/components/dashboard/sector-compare-launcher";
import { IndiceSecteursTable } from "@/components/dashboard/indice-secteurs-table";
import { SaveToHistoryCard } from "@/components/dashboard/save-to-history-card";
import { ShareCard } from "@/components/dashboard/share-card";
import { AlertCard } from "@/components/dashboard/alert-card";
import { DocumentUploadBox } from "@/components/dashboard/document-upload-box";
import {
  PmeIdentiteCard,
  PmeDirigeantsCard,
  PmeBodaccCard,
  PmeScoresCard,
  PmeNoAccountsNotice,
} from "@/components/dashboard/pme-blocks";
import { useEditMode } from "@/components/edit-mode-provider";
import { useI18n } from "@/i18n/provider";

interface AnalysisResult {
  success: boolean;
  request_id: string;
  elapsed_ms: number;
  data?: AnalysisData;
  files?: { pdf?: string; pptx?: string; xlsx?: string };
  error?: string;
  kind?: "societe" | "secteur" | "indice" | "comparatif" | "pme";
  label?: string;
}

function mapBackendKind(kind: string): "societe" | "secteur" | "indice" | "comparatif" | "pme" {
  if (kind.startsWith("cmp/")) return "comparatif";
  if (kind === "pme" || kind.includes("pme")) return "pme";
  if (kind.includes("indice")) return "indice";
  if (kind.includes("secteur")) return "secteur";
  return "societe";
}

export default function ResultatsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const search = useSearchParams();
  const router = useRouter();
  const ticker = search.get("ticker") || "";
  const kindParam = (search.get("kind") || "societe") as
    | "societe"
    | "secteur"
    | "indice"
    | "comparatif"
    | "pme";
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [notFound, setNotFound] = useState(false);
  const { enabled: editEnabled } = useEditMode();
  const { t, locale } = useI18n();

  useEffect(() => {
    const stored = sessionStorage.getItem(`analysis_${id}`);
    if (stored) {
      try {
        setResult(JSON.parse(stored));
        return;
      } catch {
        /* fallback */
      }
    }

    (async () => {
      try {
        const job = await getJob(id);
        if (job.status === "done" && job.result) {
          const elapsedMs =
            job.finished_at && job.started_at
              ? new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()
              : 0;
          const r: AnalysisResult = {
            success: true,
            request_id: id,
            elapsed_ms: elapsedMs,
            data: job.result.data,
            files: job.result.files,
            kind: mapBackendKind(job.kind),
            label: ticker || undefined,
          };
          setResult(r);
          try {
            sessionStorage.setItem(`analysis_${id}`, JSON.stringify(r));
          } catch {}
        } else if (job.status === "error") {
          setNotFound(true);
        } else {
          router.push(`/analyse?q=${encodeURIComponent(ticker)}`);
        }
      } catch {
        setNotFound(true);
      }
    })();
  }, [id, router, ticker]);

  if (notFound) {
    return (
      <div className="min-h-screen flex flex-col">
        <main className="flex-1 max-w-2xl mx-auto px-6 py-20 w-full text-center">
          <AlertTriangle className="w-12 h-12 text-signal-sell mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-ink-900 mb-2">{t("results.not_found_title")}</h1>
          <p className="text-sm text-ink-600 mb-6">
            {t("results.not_found_desc")}
          </p>
          <button onClick={() => router.push("/app")} className="btn-primary">
            {t("results.back_home")}
          </button>
        </main>
        <Footer />
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-ink-500">{t("common.loading")}</div>
      </div>
    );
  }

  const kind = result.kind || kindParam;
  const isSociete = kind === "societe";
  const data: AnalysisData = result.data || {};
  const synthesis: Synthesis | null = (data.synthesis as Synthesis) || null;
  const rawData: RawData | null = (data.raw_data as RawData) || null;
  const ratios: RatiosData | null = (data.ratios as RatiosData) || null;

  // company_info source : raw_data en priorité, sinon legacy snapshot
  const ci = rawData?.company_info || data.snapshot?.company_info;
  const market = rawData?.market || data.snapshot?.market;

  const recommendation = (data.recommendation as string) || synthesis?.recommendation || "HOLD";
  const conviction = synthesis?.conviction ?? 0.5;
  const sharePrice = market?.share_price as number | undefined;
  const currency = ci?.currency || "USD";
  const tickerStr = data.ticker || ci?.ticker || ticker;

  const latestYear = ratios?.latest_year || (ratios?.years ? Object.keys(ratios.years).sort().pop() : undefined);
  const latestRatios = latestYear && ratios?.years ? ratios.years[latestYear] : null;

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 w-full px-4 lg:px-6 py-6">
        {/* Back */}
        <button
          onClick={() => router.push("/app")}
          className="btn-ghost text-xs mb-4 -ml-3"
        >
          <ArrowLeft className="w-3 h-3 mr-1" />
          {t("results.new_analysis_btn")}
        </button>

        {/* SECTION : Société (full BI dashboard) */}
        {isSociete && ci && (
          <>
            {/* Header */}
            <header className="mb-5">
              <HeaderSociete
                ci={ci}
                elapsedMs={result.elapsed_ms}
                finsightScore={result.data?.finsight_score}
              />
            </header>

            {/* Warnings audit (data manquante détectée par AgentDataAudit)
                + détection livrables manquants (pdf_error/pptx_error/files) */}
            {(() => {
              type W = { field: string; severity: "info" | "warning" | "error"; hint: string };
              const dataObj = data as {
                warnings?: W[];
                pdf_error?: string | null;
                pptx_error?: string | null;
              };
              const w: W[] = [...(dataObj.warnings || [])];
              const files = result.files || {};
              if (!files.pdf) {
                w.push({
                  field: "files.pdf",
                  severity: "error",
                  hint: dataObj.pdf_error
                    ? `PDF indisponible — ${dataObj.pdf_error.slice(0, 180)}`
                    : "PDF indisponible — le writer a échoué lors de la génération. Relance l'analyse.",
                });
              }
              if (!files.pptx) {
                w.push({
                  field: "files.pptx",
                  severity: "warning",
                  hint: dataObj.pptx_error
                    ? `PowerPoint indisponible — ${dataObj.pptx_error.slice(0, 180)}`
                    : "PowerPoint indisponible.",
                });
              }
              if (!files.xlsx) {
                w.push({
                  field: "files.xlsx",
                  severity: "warning",
                  hint: "Excel indisponible.",
                });
              }
              return w.length > 0 ? <WarningsBanner warnings={w} /> : null;
            })()}

            {/* EditableGrid : toujours utilisé. En mode édition (Ctrl+Alt+E) :
                drag/resize ON. Hors édition : positions sauvegardées appliquées
                en lecture seule. */}
              <EditableGrid
                storageKey="finsight-dashboard-grid-societe-v2"
                blocks={[
                  {
                    id: "reco",
                    label: t("results.block_reco"),
                    default: { x: 0, y: 0, w: 4, h: 4 },
                    render: () => (
                      <RecoCard
                        recommendation={recommendation}
                        conviction={conviction}
                      />
                    ),
                  },
                  ...(result.data?.finsight_score
                    ? [
                        {
                          id: "fs-score",
                          label: "Score FinSight",
                          default: { x: 9, y: 0, w: 3, h: 6 },
                          render: () => (
                            <FinSightScoreBadge
                              score={result.data!.finsight_score!}
                              variant="full"
                            />
                          ),
                        } satisfies GridBlock,
                      ]
                    : []),
                  {
                    id: "cours",
                    label: t("results.block_price"),
                    default: { x: 4, y: 0, w: 5, h: 6 },
                    render: () => (
                      <CoursChart
                        ticker={tickerStr}
                        history={rawData?.stock_history || []}
                        sector={ci.sector}
                      />
                    ),
                  },
                  {
                    id: "performance",
                    label: "Performance comparée",
                    default: { x: 4, y: 6, w: 5, h: 6 },
                    render: () => (
                      <PerformanceCard
                        ticker={tickerStr}
                        currency={ci.currency || "EUR"}
                        sector={ci.sector || ""}
                      />
                    ),
                  },
                  {
                    id: "synthese",
                    label: t("results.block_synthesis"),
                    default: { x: 9, y: 0, w: 3, h: 10 },
                    render: () =>
                      synthesis ? <SyntheseCard synthesis={synthesis} /> : <div />,
                  },
                  {
                    id: "valo",
                    label: t("results.block_valuation"),
                    default: { x: 0, y: 4, w: 4, h: 3 },
                    render: () => (
                      <ValorisationCards
                        bull={synthesis?.target_bull}
                        base={synthesis?.target_base}
                        bear={synthesis?.target_bear}
                        sharePrice={sharePrice}
                        currency={currency}
                      />
                    ),
                  },
                  {
                    id: "ratios",
                    label: t("results.block_ratios"),
                    default: { x: 0, y: 7, w: 9, h: 4 },
                    render: () => (
                      <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
                        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
                          {t("results.ratios_key_year")} ({latestYear})
                        </div>
                        <KpiGrid ratios={latestRatios} />
                      </div>
                    ),
                  },
                  ...(rawData?.years
                    ? [
                        {
                          id: "capex",
                          label: t("results.block_capital_alloc"),
                          default: { x: 0, y: 11, w: 4, h: 5 },
                          render: () => (
                            <CapexFcfChart
                              years={rawData.years!}
                              ratios={ratios?.years}
                              currency={currency}
                            />
                          ),
                        },
                      ]
                    : []),
                  ...(synthesis?.comparable_peers && synthesis.comparable_peers.length > 0
                    ? [
                        {
                          id: "donut",
                          label: t("results.block_mktcap_weight"),
                          default: { x: 4, y: 11, w: 5, h: 5 },
                          render: () => (
                            <MktCapDonut
                              peers={synthesis.comparable_peers!}
                              targetTicker={tickerStr}
                              targetName={ci.company_name}
                              targetMarketCapMds={
                                latestRatios?.market_cap
                                  ? latestRatios.market_cap / 1000
                                  : null
                              }
                              sectorLabel={`${t("results.sector_prefix")} ${ci.sector || ""}`}
                            />
                          ),
                        },
                      ]
                    : []),
                  {
                    id: "qa",
                    label: t("results.block_qa"),
                    default: { x: 9, y: 10, w: 3, h: 6 },
                    render: () => <QAChat jobId={id} ticker={tickerStr} />,
                  },
                  ...(synthesis?.comparable_peers && synthesis.comparable_peers.length > 0
                    ? [
                        {
                          id: "compare",
                          label: t("results.block_compare"),
                          default: { x: 9, y: 16, w: 3, h: 3 },
                          render: () => <CompareCard targetTicker={tickerStr} />,
                        },
                        {
                          id: "peers",
                          label: t("results.block_sector_compare"),
                          default: { x: 0, y: 16, w: 9, h: 6 },
                          render: () => (
                            <PeersTable
                              peers={synthesis.comparable_peers!}
                              targetTicker={tickerStr}
                              targetName={ci.company_name}
                              targetRatios={latestRatios}
                            />
                          ),
                        },
                      ]
                    : []),
                  {
                    id: "pour-loin",
                    label: t("results.block_go_further"),
                    default: { x: 0, y: 22, w: 6, h: 5 },
                    render: () =>
                      synthesis ? (
                        <PourAllerPlusLoin synthesis={synthesis} />
                      ) : (
                        <div />
                      ),
                  },
                  {
                    id: "save-history",
                    label: t("results.block_save"),
                    default: { x: 9, y: 19, w: 3, h: 8 },
                    render: () => (
                      <div className="grid grid-rows-3 gap-2 h-full">
                        <SaveToHistoryCard
                          jobId={id}
                          kind="societe"
                          label={tickerStr}
                          ticker={tickerStr}
                        />
                        <ShareCard
                          jobId={id}
                          kind="societe"
                          label={tickerStr}
                          ticker={tickerStr}
                        />
                        <AlertCard
                          jobId={id}
                          kind="societe"
                          label={tickerStr}
                          ticker={tickerStr}
                        />
                      </div>
                    ),
                  },
                  {
                    id: "portrait",
                    label: t("results.block_portrait"),
                    default: { x: 6, y: 22, w: 6, h: 5 },
                    render: () => (
                      <PortraitCard
                        ticker={tickerStr}
                        companyName={ci.company_name}
                      />
                    ),
                  },
                  {
                    id: "glossaire",
                    label: t("results.block_glossary"),
                    default: { x: 0, y: 27, w: 12, h: 6 },
                    render: () => <Glossaire />,
                  },
                ] satisfies GridBlock[]}
              />

          </>
        )}

        {/* SECTION : Secteur / Indice / Comparatif — interface modulable EditableGrid */}
        {!isSociete && (
          <>
            <header className="border-b border-ink-200 pb-6 mb-8">
              <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
                {kind === "indice"
                  ? t("results.kind_indice")
                  : kind === "comparatif"
                  ? t("results.kind_comparison")
                  : kind === "pme"
                  ? t("results.kind_pme_label")
                  : t("results.kind_sector")}
              </div>
              <h1 className="text-2xl font-bold text-ink-900 tracking-tight">
                {result.label || ticker}
              </h1>
              <div className="text-xs text-ink-600 font-mono mt-1">
                {new Date().toLocaleDateString(locale)}
                {result.elapsed_ms > 0 ? ` · ${(result.elapsed_ms / 1000).toFixed(1)}s` : ""}
              </div>
            </header>

            <EditableGrid
              storageKey={`finsight-dashboard-grid-${kind}-v1`}
              blocks={[
                // Description générique : uniquement pour indice/comparatif/pme
                // (le secteur a son propre SectorPortraitCard plus riche).
                ...(kind !== "secteur"
                  ? [
                      {
                        id: "description",
                        label: t("results.block_description"),
                        default: { x: 0, y: 0, w: 8, h: 4 },
                        render: () => {
                          const dynamicSummary =
                            kind === "indice"
                              ? result.data?.indice_summary
                              : null;
                          const fallback =
                            kind === "indice"
                              ? t("results.synthesis_indice_desc")
                              : kind === "comparatif"
                              ? t("results.synthesis_comparison_desc")
                              : kind === "pme"
                              ? t("results.synthesis_pme_desc")
                              : t("results.synthesis_sector_desc");
                          return (
                            <div className="bg-navy-50 border border-navy-200 rounded-md p-5 h-full overflow-auto">
                              <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-navy-700 mb-2">
                                {t("results.block_synthesis")}
                              </div>
                              <p className="text-sm text-ink-700 leading-relaxed">
                                {dynamicSummary || fallback}
                              </p>
                            </div>
                          );
                        },
                      } satisfies GridBlock,
                    ]
                  : []),
                {
                  id: "qa",
                  label: t("results.block_qa"),
                  default: { x: 8, y: 0, w: 4, h: 8 },
                  render: () => (
                    <QAChat jobId={id} ticker={result.label || ticker} />
                  ),
                },
                {
                  id: "save-history",
                  label: t("results.block_save"),
                  default: { x: 8, y: 8, w: 4, h: 8 },
                  render: () => (
                    <div className="grid grid-rows-3 gap-2 h-full">
                      <SaveToHistoryCard
                        jobId={id}
                        kind={kind as "secteur" | "indice" | "comparatif" | "pme"}
                        label={result.label || ticker}
                      />
                      <ShareCard
                        jobId={id}
                        kind={kind as "secteur" | "indice" | "comparatif" | "pme"}
                        label={result.label || ticker}
                      />
                      <AlertCard
                        jobId={id}
                        kind={kind as "secteur" | "indice" | "comparatif" | "pme"}
                        label={result.label || ticker}
                        ticker={result.data?.raw_data?.company_info?.ticker || ticker}
                      />
                    </div>
                  ),
                },
                // ═══ Blocs spécifiques PME ═══
                ...(kind === "pme" && result.data?.has_accounts === false
                  ? [
                      {
                        id: "pme-no-accounts",
                        label: t("results.block_pme_no_accounts"),
                        default: { x: 0, y: 4, w: 8, h: 4 },
                        render: () => <PmeNoAccountsNotice data={result.data!} />,
                      } satisfies GridBlock,
                    ]
                  : []),
                ...(kind === "pme"
                  ? [
                      {
                        id: "pme-identite",
                        label: t("results.block_pme_identity"),
                        default: { x: 0, y: 8, w: 4, h: 6 },
                        render: () => <PmeIdentiteCard data={result.data!} />,
                      } satisfies GridBlock,
                      {
                        id: "pme-dirigeants",
                        label: t("results.block_pme_directors"),
                        default: { x: 4, y: 8, w: 4, h: 6 },
                        render: () => <PmeDirigeantsCard data={result.data!} />,
                      } satisfies GridBlock,
                      {
                        id: "pme-bodacc",
                        label: t("results.block_pme_bodacc"),
                        default: { x: 8, y: 11, w: 4, h: 5 },
                        render: () => <PmeBodaccCard data={result.data!} />,
                      } satisfies GridBlock,
                      {
                        id: "pme-scores",
                        label: t("results.block_pme_scoring"),
                        default: { x: 0, y: 14, w: 8, h: 5 },
                        render: () => <PmeScoresCard data={result.data!} />,
                      } satisfies GridBlock,
                    ]
                  : []),
                {
                  id: "documents-upload",
                  label: t("results.block_docs"),
                  default: { x: 8, y: 16, w: 4, h: 6 },
                  render: () => <DocumentUploadBox analysisId={id} />,
                } satisfies GridBlock,
                // Downloads PDF/PPTX/XLSX : dans la sidebar uniquement (Baptiste)
                // Bloc secteur : Portrait (HHI + PE + ROIC narratif)
                ...(kind === "secteur"
                  ? [
                      {
                        id: "sector-portrait",
                        label: "Portrait secteur",
                        default: { x: 0, y: 0, w: 8, h: 6 },
                        render: () => (
                          <SectorPortraitCard
                            sector={result.data?.sector}
                            universe={result.data?.universe}
                            summary={result.data?.sector_summary}
                            analytics={result.data?.sector_analytics}
                            etf={result.data?.sector_etf}
                            tickersCount={result.data?.tickers?.length}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                // Bloc secteur : Cours de l'ETF sectoriel (parité avec Cours société)
                ...(kind === "secteur" && result.data?.sector_etf?.ticker
                  ? [
                      {
                        id: "sector-cours",
                        label: `Cours ETF ${result.data.sector_etf.ticker}`,
                        default: { x: 0, y: 6, w: 8, h: 6 },
                        render: () => (
                          <PerformanceCard
                            ticker={result.data!.sector_etf!.ticker}
                            sector={result.data?.sector || ""}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                // Bloc secteur : bouton lancer une comparaison sectorielle
                ...(kind === "secteur"
                  ? [
                      {
                        id: "sector-compare",
                        label: "Comparer ce secteur",
                        default: { x: 0, y: 12, w: 4, h: 4 },
                        render: () => (
                          <SectorCompareLauncher
                            sector={result.data?.sector || ""}
                            universe={result.data?.universe || ""}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                // Bloc spécifique secteur : market cap donut (top 5 + autres)
                ...(kind === "secteur" && result.data?.tickers && result.data.tickers.length > 0
                  ? [
                      {
                        id: "sector-mktcap",
                        label: t("results.block_mktcap_distribution") || "Répartition Market Cap",
                        default: { x: 4, y: 12, w: 8, h: 8 },
                        render: () => (
                          <SectorMktCapDonut
                            tickers={result.data!.tickers!}
                            sectorLabel={result.data?.sector}
                            centerLabel={result.data?.sector}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                // Bloc spécifique secteur : table des sociétés
                ...(kind === "secteur" && result.data?.tickers && result.data.tickers.length > 0
                  ? [
                      {
                        id: "sector-tickers",
                        label: t("results.block_sector_companies"),
                        default: { x: 0, y: 12, w: 12, h: 8 },
                        render: () => (
                          <SectorTickersTable
                            tickers={result.data!.tickers!}
                            sectorLabel={result.data?.sector}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                // Bloc spécifique indice : donut pondération sectorielle
                ...(kind === "indice" && result.data?.secteurs && result.data.secteurs.length > 0
                  ? [
                      {
                        id: "indice-mktcap",
                        label: t("results.block_sector_weights") || "Pondération sectorielle",
                        default: { x: 0, y: 4, w: 6, h: 8 },
                        render: () => (
                          <IndiceSectorsDonut
                            secteurs={result.data!.secteurs!}
                            universe={result.data?.universe}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                // Bloc spécifique indice : cartographie sectorielle (table)
                ...(kind === "indice" && result.data?.secteurs && result.data.secteurs.length > 0
                  ? [
                      {
                        id: "indice-secteurs",
                        label: t("results.block_sector_map"),
                        default: { x: 0, y: 12, w: 12, h: 8 },
                        render: () => (
                          <IndiceSecteursTable
                            secteurs={result.data!.secteurs!}
                            universe={result.data?.universe}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                ...(result.files?.pdf
                  ? [
                      {
                        id: "pdf-preview",
                        label: t("results.block_pdf_preview"),
                        default: { x: 4, y: 16, w: 8, h: 12 },
                        render: () => (
                          <div className="bg-white border border-ink-200 rounded-md h-full overflow-hidden flex flex-col">
                            <div className="px-3 py-2 border-b border-ink-100 text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 flex-none">
                              {t("results.pdf_preview_label")}
                            </div>
                            <iframe
                              src={getFileUrl(result.files!.pdf!)}
                              className="flex-1 w-full"
                              title={t("results.block_pdf_preview")}
                            />
                          </div>
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
              ]}
            />
          </>
        )}

        <div className="text-xs text-ink-500 mt-8 text-center">
          {t("results.generated_in")} {(result.elapsed_ms / 1000).toFixed(1)}s · ID{" "}
          {result.request_id.slice(0, 8)}
        </div>
      </main>
      <Footer />
      {/* Discussion collaborative — FAB en bas à droite, panneau slide-in */}
      <CommentsPanel jobId={id} />
    </div>
  );
}

