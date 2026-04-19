"use client";

import { useEffect, useState, useMemo, use } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  FileText,
  Presentation,
  FileSpreadsheet,
  AlertTriangle,
} from "lucide-react";
import { Footer } from "@/components/footer";
import { getFileUrl, getJob } from "@/lib/api";

import type { AnalysisData, RawData, RatiosData, Synthesis } from "@/components/dashboard/types";
import { HeaderSociete } from "@/components/dashboard/header-societe";
import { RecoCard } from "@/components/dashboard/reco-card";
import { CoursChart } from "@/components/dashboard/cours-chart";
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
import { IndiceSecteursTable } from "@/components/dashboard/indice-secteurs-table";
import { SaveToHistoryCard } from "@/components/dashboard/save-to-history-card";
import { useEditMode } from "@/components/edit-mode-provider";

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
          <h1 className="text-xl font-semibold text-ink-900 mb-2">Analyse introuvable</h1>
          <p className="text-sm text-ink-600 mb-6">
            Cette analyse n&apos;est plus disponible (lien expiré ou redémarrage serveur).
          </p>
          <button onClick={() => router.push("/app")} className="btn-primary">
            Retour à l&apos;accueil
          </button>
        </main>
        <Footer />
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-ink-500">Chargement...</div>
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
          Nouvelle analyse
        </button>

        {/* SECTION : Société (full BI dashboard) */}
        {isSociete && ci && (
          <>
            {/* Header */}
            <header className="mb-5">
              <HeaderSociete ci={ci} elapsedMs={result.elapsed_ms} />
            </header>

            {/* Warnings audit (data manquante détectée par AgentDataAudit) */}
            {(data as { warnings?: { field: string; severity: "info" | "warning" | "error"; hint: string }[] }).warnings && (
              <WarningsBanner warnings={(data as { warnings: { field: string; severity: "info" | "warning" | "error"; hint: string }[] }).warnings} />
            )}

            {/* EditableGrid : toujours utilisé. En mode édition (Ctrl+Alt+E) :
                drag/resize ON. Hors édition : positions sauvegardées appliquées
                en lecture seule. */}
              <EditableGrid
                storageKey="finsight-dashboard-grid-societe-v2"
                blocks={[
                  {
                    id: "reco",
                    label: "Recommandation",
                    default: { x: 0, y: 0, w: 4, h: 4 },
                    render: () => (
                      <RecoCard
                        recommendation={recommendation}
                        conviction={conviction}
                      />
                    ),
                  },
                  {
                    id: "cours",
                    label: "Cours bourse",
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
                    id: "synthese",
                    label: "Synthèse",
                    default: { x: 9, y: 0, w: 3, h: 10 },
                    render: () =>
                      synthesis ? <SyntheseCard synthesis={synthesis} /> : <div />,
                  },
                  {
                    id: "valo",
                    label: "Valorisation",
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
                    label: "Ratios clés",
                    default: { x: 0, y: 7, w: 9, h: 4 },
                    render: () => (
                      <div className="bg-white border border-ink-200 rounded-md p-4 h-full overflow-auto">
                        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
                          Ratios clés ({latestYear})
                        </div>
                        <KpiGrid ratios={latestRatios} />
                      </div>
                    ),
                  },
                  ...(rawData?.years
                    ? [
                        {
                          id: "capex",
                          label: "Capital alloué",
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
                          label: "Poids relatif Mkt Cap",
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
                              sectorLabel={`Secteur ${ci.sector || ""}`}
                            />
                          ),
                        },
                      ]
                    : []),
                  {
                    id: "qa",
                    label: "Q&A IA",
                    default: { x: 9, y: 10, w: 3, h: 6 },
                    render: () => <QAChat jobId={id} ticker={tickerStr} />,
                  },
                  ...(synthesis?.comparable_peers && synthesis.comparable_peers.length > 0
                    ? [
                        {
                          id: "compare",
                          label: "Comparer",
                          default: { x: 9, y: 16, w: 3, h: 3 },
                          render: () => <CompareCard targetTicker={tickerStr} />,
                        },
                        {
                          id: "peers",
                          label: "Comparatif sectoriel",
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
                    label: "Pour aller plus loin",
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
                    label: "Garder en mémoire",
                    default: { x: 9, y: 19, w: 3, h: 3 },
                    render: () => (
                      <SaveToHistoryCard
                        jobId={id}
                        kind="societe"
                        label={tickerStr}
                        ticker={tickerStr}
                      />
                    ),
                  },
                  {
                    id: "portrait",
                    label: "Portrait d'entreprise",
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
                    label: "Glossaire",
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
                  ? "Indice boursier"
                  : kind === "comparatif"
                  ? "Comparatif société"
                  : kind === "pme"
                  ? "PME non cotée — Analyse financière"
                  : "Analyse sectorielle"}
              </div>
              <h1 className="text-2xl font-bold text-ink-900 tracking-tight">
                {result.label || ticker}
              </h1>
              <div className="text-xs text-ink-600 font-mono mt-1">
                {new Date().toLocaleDateString("fr-FR")}
                {result.elapsed_ms > 0 ? ` · ${(result.elapsed_ms / 1000).toFixed(1)}s` : ""}
              </div>
            </header>

            <EditableGrid
              storageKey={`finsight-dashboard-grid-${kind}-v1`}
              blocks={[
                {
                  id: "description",
                  label: "Description",
                  default: { x: 0, y: 0, w: 8, h: 4 },
                  render: () => (
                    <div className="bg-navy-50 border border-navy-200 rounded-md p-5 h-full overflow-auto">
                      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-navy-700 mb-2">
                        Synthèse
                      </div>
                      <p className="text-sm text-ink-700 leading-relaxed">
                        {kind === "indice"
                          ? "Analyse complète de l'indice générée. Le rapport PDF contient l'analyse macro, les comparatifs inter-secteurs et l'allocation optimale (Markowitz)."
                          : kind === "comparatif"
                          ? "Comparatif société généré. Les livrables PDF, PPTX et Excel contiennent les analyses parallèles, ratios comparés et verdict relatif."
                          : kind === "pme"
                          ? "Analyse PME non cotée générée via Pappers + BODACC. Le rapport contient les SIG détaillés, 14 ratios clés, benchmark sectoriel, scoring Altman Z & santé FinSight, bankabilité. Approche contrôle de gestion."
                          : "Analyse sectorielle générée. Le rapport PDF compare les principales sociétés du secteur sur l'univers sélectionné, avec ratios, performance et allocation."}
                      </p>
                    </div>
                  ),
                },
                {
                  id: "qa",
                  label: "Q&A IA",
                  default: { x: 8, y: 0, w: 4, h: 8 },
                  render: () => (
                    <QAChat jobId={id} ticker={result.label || ticker} />
                  ),
                },
                {
                  id: "save-history",
                  label: "Garder en mémoire",
                  default: { x: 8, y: 8, w: 4, h: 3 },
                  render: () => (
                    <SaveToHistoryCard
                      jobId={id}
                      kind={kind as "secteur" | "indice" | "comparatif"}
                      label={result.label || ticker}
                    />
                  ),
                },
                ...(result.files?.pdf
                  ? [
                      {
                        id: "pdf",
                        label: "Rapport PDF",
                        default: { x: 0, y: 4, w: 4, h: 4 },
                        render: () => (
                          <FileBlock
                            icon={<FileText className="w-6 h-6" />}
                            label="Rapport PDF"
                            description="Format institutionnel"
                            href={getFileUrl(result.files!.pdf!)}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                ...(result.files?.pptx
                  ? [
                      {
                        id: "pptx",
                        label: "Pitchbook PPTX",
                        default: { x: 4, y: 4, w: 4, h: 4 },
                        render: () => (
                          <FileBlock
                            icon={<Presentation className="w-6 h-6" />}
                            label="Pitchbook PPTX"
                            description="Style Bloomberg"
                            href={getFileUrl(result.files!.pptx!)}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                ...(result.files?.xlsx
                  ? [
                      {
                        id: "xlsx",
                        label: "Modèle Excel",
                        default: { x: 0, y: 8, w: 4, h: 4 },
                        render: () => (
                          <FileBlock
                            icon={<FileSpreadsheet className="w-6 h-6" />}
                            label="Modèle Excel"
                            description="DCF · Ratios · Comparables"
                            href={getFileUrl(result.files!.xlsx!)}
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
                        label: "Sociétés du secteur",
                        default: { x: 0, y: 8, w: 12, h: 8 },
                        render: () => (
                          <SectorTickersTable
                            tickers={result.data!.tickers!}
                            sectorLabel={result.data?.sector}
                          />
                        ),
                      } satisfies GridBlock,
                    ]
                  : []),
                // Bloc spécifique indice : cartographie sectorielle
                ...(kind === "indice" && result.data?.secteurs && result.data.secteurs.length > 0
                  ? [
                      {
                        id: "indice-secteurs",
                        label: "Cartographie sectorielle",
                        default: { x: 0, y: 8, w: 12, h: 8 },
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
                        label: "Aperçu PDF",
                        default: { x: 4, y: 16, w: 8, h: 12 },
                        render: () => (
                          <div className="bg-white border border-ink-200 rounded-md h-full overflow-hidden flex flex-col">
                            <div className="px-3 py-2 border-b border-ink-100 text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 flex-none">
                              Aperçu rapport PDF
                            </div>
                            <iframe
                              src={getFileUrl(result.files!.pdf!)}
                              className="flex-1 w-full"
                              title="Aperçu PDF"
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
          Analyse générée en {(result.elapsed_ms / 1000).toFixed(1)}s · ID{" "}
          {result.request_id.slice(0, 8)}
        </div>
      </main>
      <Footer />
    </div>
  );
}

/**
 * FileBlock — version "card pleine hauteur" pour EditableGrid (secteur/indice/comparatif).
 * Remplit 100% du bloc, icône centrée + bouton download visible.
 */
function FileBlock({
  icon,
  label,
  description,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  href: string;
}) {
  return (
    <a
      href={href}
      download
      target="_blank"
      rel="noopener noreferrer"
      className="bg-white border border-ink-200 rounded-md p-5 h-full flex flex-col items-center justify-center text-center gap-2 hover:border-navy-500 hover:shadow-sm transition-all group"
    >
      <div className="text-navy-500">{icon}</div>
      <div className="text-sm font-semibold text-ink-900 group-hover:text-navy-500 transition-colors">
        {label}
      </div>
      <div className="text-xs text-ink-500">{description}</div>
      <div className="mt-1 flex items-center gap-1 text-[11px] text-navy-500 font-semibold">
        <Download className="w-3.5 h-3.5" />
        Télécharger
      </div>
    </a>
  );
}
