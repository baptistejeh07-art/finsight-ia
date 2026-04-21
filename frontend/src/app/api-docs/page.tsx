import type { Metadata } from "next";
import Link from "next/link";
import { Code2, Key, Gauge, FileDown, ArrowRight, ExternalLink } from "lucide-react";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Documentation API",
  description:
    "API FinSight : endpoints data, analyse et livrables. Authentification par clé fsk_*, rate limits, tarifs pay-per-use.",
};

const BASE_URL = "https://finsight-ia-production.up.railway.app";

export default function ApiDocsPage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <div className="inline-flex items-center gap-2 text-xs font-semibold text-accent-primary uppercase tracking-widest mb-4">
              <Code2 className="w-4 h-4" /> API publique v1
            </div>
            <h1 className="font-serif text-4xl md:text-5xl font-bold text-text-primary tracking-tight">
              Documentation API
            </h1>
            <p className="text-text-muted mt-4 text-base md:text-lg">
              Intégrez les analyses FinSight dans vos outils : endpoints data, analyse complète ou
              livrables PDF / PPTX / XLSX. Facturation à l&apos;appel.
            </p>
          </div>
        </section>

        <section className="container-vitrine py-16 max-w-3xl space-y-12">
          {/* Authentification */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <Key className="w-5 h-5 text-accent-primary" />
              <h2 className="font-serif text-2xl font-bold text-text-primary">Authentification</h2>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed mb-4">
              Chaque appel doit inclure une clé API dans le header{" "}
              <code className="bg-surface-muted px-1.5 py-0.5 rounded text-xs">X-API-Key</code>. Les
              clés commencent par <code className="bg-surface-muted px-1.5 py-0.5 rounded text-xs">fsk_</code>{" "}
              et se génèrent depuis votre espace <Link href="/parametres/api" className="text-accent-primary hover:underline">Paramètres → API</Link>.
            </p>
            <pre className="bg-text-primary text-surface rounded-md p-4 text-xs overflow-x-auto">
{`curl -H "X-API-Key: fsk_votre_clé" \\
     ${BASE_URL}/api/v1/snapshot/AAPL`}
            </pre>
          </div>

          {/* Rate limits */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <Gauge className="w-5 h-5 text-accent-primary" />
              <h2 className="font-serif text-2xl font-bold text-text-primary">Rate limits</h2>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed mb-4">
              Limites par défaut : 30 requêtes/minute et 1 000 requêtes/jour par clé. Les réponses
              incluent les headers{" "}
              <code className="bg-surface-muted px-1.5 py-0.5 rounded text-xs">X-RateLimit-Remaining-Min</code>{" "}
              et{" "}
              <code className="bg-surface-muted px-1.5 py-0.5 rounded text-xs">X-RateLimit-Remaining-Day</code>.
              Limites ajustables sur demande pour les plans Équipe et Enterprise.
            </p>
          </div>

          {/* Endpoints */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <FileDown className="w-5 h-5 text-accent-primary" />
              <h2 className="font-serif text-2xl font-bold text-text-primary">Endpoints principaux</h2>
            </div>
            <div className="space-y-4">
              <EndpointRow
                method="GET"
                path="/api/v1/snapshot/{ticker}"
                price="0,05 € / appel"
                description="Snapshot données brutes : cours, ratios LTM, market cap, profil."
              />
              <EndpointRow
                method="GET"
                path="/api/v1/ratios/{ticker}"
                price="0,05 € / appel"
                description="Ratios financiers multi-années (marges, ROE/ROIC, valorisation, solvabilité)."
              />
              <EndpointRow
                method="POST"
                path="/api/v1/analyze/{ticker}"
                price="0,50 € / appel"
                description="Analyse complète (synthèse IA + DCF + peers + thèse). Réponse JSON."
              />
              <EndpointRow
                method="POST"
                path="/api/v1/deliverables/{ticker}"
                price="2,00 € / appel"
                description="Génère les 3 livrables (PDF ~20 pages, PPTX 20 slides, XLSX DCF complet)."
              />
            </div>
          </div>

          {/* Référence complète */}
          <div className="border-t border-border-default pt-8">
            <h2 className="font-serif text-xl font-bold text-text-primary mb-3">
              Référence OpenAPI complète
            </h2>
            <p className="text-sm text-text-secondary mb-4">
              Spécification interactive auto-générée (Swagger UI) avec tous les paramètres, schémas
              et codes d&apos;erreur.
            </p>
            <a
              href={`${BASE_URL}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 btn-outline"
            >
              Ouvrir /docs <ExternalLink className="w-4 h-4" />
            </a>
          </div>

          {/* CTA contact */}
          <div className="bg-surface-muted border border-border-default rounded-md p-6">
            <h3 className="font-serif text-lg font-semibold text-text-primary mb-2">
              Besoin d&apos;un volume élevé ou d&apos;un SLA ?
            </h3>
            <p className="text-sm text-text-secondary mb-4">
              Quotas personnalisés, tarifs dégressifs, déploiement on-premise. Parlons-en.
            </p>
            <Link href="/contact?plan=api" className="inline-flex items-center gap-2 btn-cta">
              Nous contacter <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}

function EndpointRow({
  method,
  path,
  price,
  description,
}: {
  method: "GET" | "POST";
  path: string;
  price: string;
  description: string;
}) {
  return (
    <div className="border border-border-default rounded-md p-4 bg-surface-elevated">
      <div className="flex flex-wrap items-center gap-3 mb-1.5">
        <span
          className={
            "text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider " +
            (method === "GET"
              ? "bg-accent-primary/10 text-accent-primary"
              : "bg-emerald-100 text-emerald-700")
          }
        >
          {method}
        </span>
        <code className="text-xs font-mono text-text-primary">{path}</code>
        <span className="ml-auto text-xs text-text-muted">{price}</span>
      </div>
      <p className="text-sm text-text-secondary mt-1">{description}</p>
    </div>
  );
}
