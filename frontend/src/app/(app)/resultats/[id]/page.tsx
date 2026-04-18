"use client";

import { useEffect, useState, use } from "react";
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

interface AnalysisResult {
  success: boolean;
  request_id: string;
  elapsed_ms: number;
  data?: AnalysisData;
  files?: { pdf?: string; pptx?: string; xlsx?: string };
  error?: string;
  kind?: "societe" | "secteur" | "indice" | "comparatif";
  label?: string;
}

function mapBackendKind(kind: string): "societe" | "secteur" | "indice" | "comparatif" {
  if (kind.startsWith("cmp/")) return "comparatif";
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
    | "comparatif";
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [notFound, setNotFound] = useState(false);

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

            {/* Layout principal 2 colonnes : 65/35 */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-5">
              {/* COLONNE GAUCHE */}
              <div className="xl:col-span-2 space-y-4">
                {/* Row 1 : (Reco + Valo empilés à gauche) | Cours large à droite */}
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
                  <div className="lg:col-span-2 space-y-4 flex flex-col">
                    <RecoCard recommendation={recommendation} conviction={conviction} />
                    {/* Valorisation limitée à la largeur de la col Reco (pas de débordement) */}
                    <ValorisationCards
                      bull={synthesis?.target_bull}
                      base={synthesis?.target_base}
                      bear={synthesis?.target_bear}
                      sharePrice={sharePrice}
                      currency={currency}
                    />
                  </div>
                  <div className="lg:col-span-3">
                    <CoursChart
                      ticker={tickerStr}
                      history={rawData?.stock_history || []}
                      sector={ci.sector}
                    />
                  </div>
                </div>

                {/* Row 3 : Ratios clés (bandeau compact, anim au scroll) */}
                <RevealOnScroll>
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
                      Ratios clés ({latestYear})
                    </div>
                    <KpiGrid ratios={latestRatios} />
                  </div>
                </RevealOnScroll>

                {/* Row 4 : CapEx + Donut (REMONTÉ ici, anim au scroll) */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {rawData?.years && (
                    <RevealOnScroll>
                      <CapexFcfChart
                        years={rawData.years}
                        ratios={ratios?.years}
                        currency={currency}
                      />
                    </RevealOnScroll>
                  )}
                  {synthesis?.comparable_peers && synthesis.comparable_peers.length > 0 && (
                    <RevealOnScroll>
                      <MktCapDonut
                        peers={synthesis.comparable_peers}
                        targetTicker={tickerStr}
                        targetName={ci.company_name}
                        targetMarketCapMds={
                          latestRatios?.market_cap ? latestRatios.market_cap / 1000 : null
                        }
                        sectorLabel={`Secteur ${ci.sector || ""}`}
                      />
                    </RevealOnScroll>
                  )}
                </div>
              </div>

              {/* COLONNE DROITE — Synthèse (limitée) + Q&A + Compare */}
              <div className="space-y-4">
                {synthesis && <SyntheseCard synthesis={synthesis} />}
                <QAChat jobId={id} ticker={tickerStr} />
                {synthesis?.comparable_peers && synthesis.comparable_peers.length > 0 && (
                  <CompareCard targetTicker={tickerStr} />
                )}
              </div>
            </div>

            {/* Comparatif sectoriel — pleine largeur, compact, anim au scroll */}
            {synthesis?.comparable_peers && synthesis.comparable_peers.length > 0 && (
              <RevealOnScroll className="mb-5 block">
                <PeersTable
                  peers={synthesis.comparable_peers}
                  targetTicker={tickerStr}
                  targetName={ci.company_name}
                  targetRatios={latestRatios}
                />
              </RevealOnScroll>
            )}

            {/* Pour aller plus loin + Portrait */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
              {synthesis && <PourAllerPlusLoin synthesis={synthesis} />}
              <PortraitCard ticker={tickerStr} companyName={ci.company_name} />
            </section>

            {/* Glossaire */}
            <section className="mb-5">
              <Glossaire />
            </section>
          </>
        )}

        {/* SECTION : Secteur / Indice / Comparatif (V1 = card simple + downloads) */}
        {!isSociete && (
          <>
            <header className="border-b border-ink-200 pb-6 mb-8">
              <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
                {kind === "indice"
                  ? "Indice boursier"
                  : kind === "comparatif"
                  ? "Comparatif société"
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
            <section className="mb-8">
              <div className="card bg-navy-50 border-navy-200">
                <p className="text-sm text-ink-700 leading-relaxed">
                  {kind === "indice"
                    ? "Analyse complète de l'indice générée. Le rapport PDF contient l'analyse macro, les comparatifs inter-secteurs et l'allocation optimale."
                    : kind === "comparatif"
                    ? "Comparatif société généré. Les livrables PDF, PPTX et Excel contiennent les analyses parallèles, ratios comparés et verdict relatif."
                    : "Analyse sectorielle générée. Le rapport PDF compare les principales sociétés du secteur sur l'univers sélectionné."}
                </p>
              </div>
            </section>
          </>
        )}

        {/* Downloads pour secteur/indice/comparatif (sociétés ont la sidebar) */}
        {!isSociete && result.files && (
          <section className="mb-8">
            <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
              Livrables
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {result.files.pdf && (
                <DownloadCard
                  icon={<FileText className="w-5 h-5" />}
                  label="Rapport PDF"
                  description="Format institutionnel"
                  href={getFileUrl(result.files.pdf)}
                />
              )}
              {result.files.pptx && (
                <DownloadCard
                  icon={<Presentation className="w-5 h-5" />}
                  label="Pitchbook PPTX"
                  description="Style Bloomberg"
                  href={getFileUrl(result.files.pptx)}
                />
              )}
              {result.files.xlsx && (
                <DownloadCard
                  icon={<FileSpreadsheet className="w-5 h-5" />}
                  label="Modèle Excel"
                  description="DCF · Ratios · Comparables"
                  href={getFileUrl(result.files.xlsx)}
                />
              )}
            </div>
          </section>
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

function DownloadCard({
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
      className="card-hover flex items-start gap-3 group"
    >
      <div className="text-navy-500">{icon}</div>
      <div className="flex-1">
        <div className="text-sm font-semibold text-ink-900 group-hover:text-navy-500 transition-colors">
          {label}
        </div>
        <div className="text-xs text-ink-500 mt-0.5">{description}</div>
      </div>
      <Download className="w-4 h-4 text-ink-400 group-hover:text-navy-500 transition-colors" />
    </a>
  );
}
