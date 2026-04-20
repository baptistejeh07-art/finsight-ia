import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, Eye, Sparkles } from "lucide-react";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface ShareData {
  kind: string;
  label: string;
  ticker: string | null;
  created_at: string;
  views_count: number;
  payload: {
    data?: Record<string, unknown>;
    files?: Record<string, string>;
  };
}

async function fetchShare(token: string): Promise<ShareData | null> {
  try {
    const r = await fetch(`${API_URL}/share/${token}`, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as ShareData;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ token: string }> }): Promise<Metadata> {
  const { token } = await params;
  const data = await fetchShare(token);
  if (!data) return { title: "Analyse introuvable" };
  const title = `${data.label} — Analyse FinSight`;
  return {
    title,
    description: `Analyse ${data.kind} générée par FinSight IA. ${data.label}.`,
    openGraph: { title, description: `Analyse financière institutionnelle propulsée par IA.` },
  };
}

export default async function SharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const data = await fetchShare(token);
  if (!data) notFound();

  const d = data.payload?.data || {};
  const files = data.payload?.files || {};
  const fileUrl = (path: string) => path.startsWith("http") ? path : `${API_URL}/file/${path}`;
  const dCast = d as Record<string, unknown>;
  const summary = (dCast.summary || dCast.synthese || dCast.briefing || "") as string;
  const recommendation = (dCast.recommendation || dCast.recommandation || "") as string;
  const targetPrice = dCast.target_price_base || dCast.target;

  return (
    <main className="min-h-screen bg-surface text-text-primary">
      {/* Header public minimal */}
      <header className="border-b border-border-default sticky top-0 bg-surface/95 backdrop-blur z-10">
        <div className="container-vitrine py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 font-serif text-lg font-bold">
            FinSight <span className="text-accent-primary">IA</span>
          </Link>
          <Link
            href="/auth"
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-accent-primary text-accent-primary-fg font-semibold hover:opacity-90"
          >
            Lancer mon analyse <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </header>

      <article className="container-vitrine py-10 max-w-4xl">
        <div className="flex items-center gap-2 text-xs text-text-muted mb-3">
          <Sparkles className="w-3 h-3 text-accent-primary" />
          <span className="uppercase tracking-widest font-semibold text-accent-primary">
            Analyse partagée
          </span>
          <span>·</span>
          <span>{data.kind}</span>
          <span>·</span>
          <span className="flex items-center gap-1"><Eye className="w-3 h-3" />{data.views_count} vues</span>
        </div>
        <h1 className="font-serif text-3xl md:text-5xl font-bold tracking-tight mb-3">
          {data.label}
        </h1>
        <p className="text-sm text-text-muted">
          Générée le {new Date(data.created_at).toLocaleDateString("fr-FR", {
            day: "numeric", month: "long", year: "numeric",
          })}
        </p>

        {/* KPI synthèse */}
        {(recommendation || targetPrice) && (
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3">
            {recommendation && (
              <div className="card-vitrine !p-4">
                <div className="text-2xs uppercase tracking-widest text-text-muted">Recommandation</div>
                <div className="text-xl font-bold mt-1">{String(recommendation)}</div>
              </div>
            )}
            {targetPrice ? (
              <div className="card-vitrine !p-4">
                <div className="text-2xs uppercase tracking-widest text-text-muted">Cours cible</div>
                <div className="text-xl font-bold mt-1 font-mono">{String(targetPrice)}</div>
              </div>
            ) : null}
            <div className="card-vitrine !p-4">
              <div className="text-2xs uppercase tracking-widest text-text-muted">Modèle</div>
              <div className="text-xl font-bold mt-1">DCF + comparables</div>
            </div>
          </div>
        )}

        {/* Résumé */}
        {summary && (
          <section className="mt-10">
            <h2 className="font-serif text-xl font-semibold mb-3">Synthèse</h2>
            <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-line">
              {String(summary).slice(0, 2000)}
              {String(summary).length > 2000 ? "…" : ""}
            </div>
          </section>
        )}

        {/* Téléchargements */}
        {(files.pdf || files.pptx || files.xlsx) && (
          <section className="mt-10 border-t border-border-default pt-8">
            <h2 className="font-serif text-xl font-semibold mb-4">Livrables</h2>
            <div className="flex flex-wrap gap-3">
              {files.pdf && (
                <a href={fileUrl(files.pdf)} download className="px-4 py-2 rounded-md border border-border-default text-sm hover:bg-surface-muted">
                  Rapport PDF
                </a>
              )}
              {files.pptx && (
                <a href={fileUrl(files.pptx)} download className="px-4 py-2 rounded-md border border-border-default text-sm hover:bg-surface-muted">
                  Pitchbook PPTX
                </a>
              )}
              {files.xlsx && (
                <a href={fileUrl(files.xlsx)} download className="px-4 py-2 rounded-md border border-border-default text-sm hover:bg-surface-muted">
                  Modèle Excel
                </a>
              )}
            </div>
          </section>
        )}

        {/* CTA conversion */}
        <section className="mt-12 bg-accent-primary/5 border border-accent-primary/20 rounded-lg p-6 md:p-8 text-center">
          <h3 className="font-serif text-xl md:text-2xl font-semibold mb-2">
            Lancez votre propre analyse en 2 minutes
          </h3>
          <p className="text-sm text-text-secondary mb-5 max-w-xl mx-auto">
            DCF, ratios sectoriels, scénarios, comparables. Rapport PDF + pitchbook PPTX +
            modèle Excel prêts pour comité d&apos;investissement.
          </p>
          <Link
            href="/auth"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-accent-primary text-accent-primary-fg font-semibold hover:opacity-90"
          >
            Essayer FinSight gratuitement <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
