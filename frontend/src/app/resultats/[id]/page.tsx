"use client";

import { useEffect, useState, use } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ArrowLeft, Download, FileText, Presentation, FileSpreadsheet, AlertTriangle } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { fmtCurrency, fmtPercent, signalColor, signalLabel } from "@/lib/utils";
import { getFileUrl, getJob } from "@/lib/api";

interface AnalysisResult {
  success: boolean;
  request_id: string;
  elapsed_ms: number;
  data?: Record<string, unknown>;
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
  const kindParam = (search.get("kind") || "societe") as "societe" | "secteur" | "indice" | "comparatif";
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    // 1. Essaye d'abord sessionStorage (analyse fraîche déjà stockée)
    const stored = sessionStorage.getItem(`analysis_${id}`);
    if (stored) {
      try {
        setResult(JSON.parse(stored));
        return;
      } catch {
        // JSON corrompu → fallback backend
      }
    }

    // 2. Sinon, fetch le job depuis le backend (refresh, lien direct)
    (async () => {
      try {
        const job = await getJob(id);
        if (job.status === "done" && job.result) {
          const elapsedMs = job.finished_at && job.started_at
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
          // Re-cache en sessionStorage pour prochaines navigations
          try { sessionStorage.setItem(`analysis_${id}`, JSON.stringify(r)); } catch {}
        } else if (job.status === "error") {
          setNotFound(true);
        } else {
          // Encore en cours → redirige vers la page d'analyse
          router.push(`/analyse?q=${encodeURIComponent(ticker)}`);
        }
      } catch {
        // 404 ou backend down → page not-found inline
        setNotFound(true);
      }
    })();
  }, [id, router, ticker]);

  if (notFound) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-2xl mx-auto px-6 py-20 w-full text-center">
          <AlertTriangle className="w-12 h-12 text-signal-sell mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-ink-900 mb-2">
            Analyse introuvable
          </h1>
          <p className="text-sm text-ink-600 mb-6">
            Cette analyse n&apos;est plus disponible en mémoire (redémarrage serveur ou lien expiré).
            Relancez une nouvelle analyse depuis l&apos;accueil.
          </p>
          <button onClick={() => router.push("/")} className="btn-primary">
            Retour à l&apos;accueil
          </button>
        </main>
        <Footer />
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-ink-500">Chargement...</div>
        </main>
        <Footer />
      </div>
    );
  }

  const kind = result.kind || kindParam;
  const isSociete = kind === "societe";

  // Extraire les données de l'analyse (uniquement société)
  const data = (result.data || {}) as Record<string, unknown>;
  const synthesis = (data.synthesis || {}) as Record<string, unknown>;
  const snapshot = (data.snapshot || {}) as Record<string, unknown>;
  const ci = (snapshot.company_info || {}) as Record<string, unknown>;
  const market = (snapshot.market || {}) as Record<string, unknown>;

  const reco = (synthesis.recommendation as string) || "HOLD";
  const conviction = (synthesis.conviction as number) || 0.5;
  const targetBase = synthesis.target_base as number | undefined;
  const summary = (synthesis.summary as string) || "";
  const currency = (ci.currency as string) || "USD";
  const sharePrice = market.share_price as number | undefined;
  const companyName = (ci.company_name as string) || ticker;
  const sector = (ci.sector as string) || (isSociete ? "—" : kind === "indice" ? "Indice boursier" : kind === "comparatif" ? "Comparatif société" : "Analyse sectorielle");

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        {/* Back */}
        <button
          onClick={() => router.push("/")}
          className="btn-ghost text-xs mb-4 -ml-3"
        >
          <ArrowLeft className="w-3 h-3 mr-1" />
          Nouvelle analyse
        </button>

        {/* Header */}
        <header className="border-b border-ink-200 pb-6 mb-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="section-label mb-2">{sector}</div>
              <h1 className="text-3xl font-bold text-ink-900 tracking-tight mb-1">
                {isSociete ? companyName : (result.label || ticker)}
              </h1>
              <div className="text-sm text-ink-600 font-mono">
                {isSociete ? `${ticker} · ${currency} · ` : ""}
                {new Date().toLocaleDateString("fr-FR")}
              </div>
            </div>
            {isSociete && (
              <div className="text-right">
                <div className="section-label mb-1">Cours actuel</div>
                <div className="text-2xl font-bold text-ink-900 font-mono">
                  {sharePrice ? fmtCurrency(sharePrice, currency, 2) : "—"}
                </div>
              </div>
            )}
          </div>
        </header>

        {/* Verdict KPIs (société uniquement pour V1) */}
        {isSociete && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <KpiCard label="Recommandation">
            <div className={`text-xl font-bold ${signalColor(reco)}`}>
              {signalLabel(reco)}
            </div>
          </KpiCard>
          <KpiCard label="Conviction IA">
            <div className="text-xl font-bold text-ink-900 font-mono">
              {Math.round(conviction * 100)} %
            </div>
            <div className="w-full h-1 bg-ink-100 rounded-full mt-2 overflow-hidden">
              <div
                className="h-full bg-navy-500 rounded-full"
                style={{ width: `${conviction * 100}%` }}
              />
            </div>
          </KpiCard>
          <KpiCard label="Cible 12 mois">
            <div className="text-xl font-bold text-navy-500 font-mono">
              {targetBase ? fmtCurrency(targetBase, currency, 0) : "—"}
            </div>
          </KpiCard>
          <KpiCard label="Upside potentiel">
            <div
              className={`text-xl font-bold font-mono ${
                targetBase && sharePrice && targetBase > sharePrice
                  ? "text-signal-buy"
                  : "text-signal-sell"
              }`}
            >
              {targetBase && sharePrice
                ? fmtPercent((targetBase - sharePrice) / sharePrice)
                : "—"}
            </div>
          </KpiCard>
        </section>
        )}

        {/* Message secteur/indice/comparatif : livrables téléchargeables */}
        {!isSociete && (
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
        )}

        {/* Synthèse */}
        {isSociete && summary && (
          <section className="mb-8">
            <div className="section-label mb-3">Synthèse de l&apos;analyse</div>
            <div className="card">
              <p className="text-sm text-ink-700 leading-relaxed">{summary}</p>
            </div>
          </section>
        )}

        {/* Downloads */}
        {result.files && (
          <section className="mb-8">
            <div className="section-label mb-3">Livrables</div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {result.files.pdf && (
                <DownloadCard
                  icon={<FileText className="w-5 h-5" />}
                  label="Rapport PDF"
                  description="20 pages · Format institutionnel"
                  href={getFileUrl(result.files.pdf)}
                />
              )}
              {result.files.pptx && (
                <DownloadCard
                  icon={<Presentation className="w-5 h-5" />}
                  label="Pitchbook PPTX"
                  description="20 slides · Style Bloomberg"
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

        {/* Footer info */}
        <div className="text-xs text-ink-500 mt-8 text-center">
          Analyse générée en {(result.elapsed_ms / 1000).toFixed(1)}s · ID {result.request_id.slice(0, 8)}
        </div>
      </main>
      <Footer />
    </div>
  );
}

function KpiCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4">
      <div className="section-label mb-2">{label}</div>
      <div>{children}</div>
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
