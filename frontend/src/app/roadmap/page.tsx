import type { Metadata } from "next";
import Link from "next/link";
import { CheckCircle, Clock, Target, ArrowRight } from "lucide-react";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Roadmap",
  description:
    "Ce que nous livrons, ce que nous préparons, ce que nous visons à long terme. Transparence totale sur le développement de FinSight IA.",
};

interface RoadmapItem {
  title: string;
  description: string;
  status: "shipped" | "wip" | "planned";
  date?: string;
}

const SHIPPED: RoadmapItem[] = [
  {
    title: "Pipeline 7 agents (LangGraph)",
    description:
      "Fetch + quant + synthesis + qa + devil + entry zone + outputs en parallèle. Chaque chiffre déterministe, jamais inventé par un LLM.",
    date: "Mars 2026",
    status: "shipped",
  },
  {
    title: "Site vitrine complet",
    description:
      "Homepage style Anthropic, méga-menus, tarification, FAQ, pages institutionnelles (méthodologie, sécurité, mentions légales, RGPD).",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Auth Google OAuth + email/password",
    description:
      "Authentification Supabase avec OAuth Google et fallback email/password. Comptes utilisateurs prêts pour la persistance.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Portrait d'entreprise (V1)",
    description:
      "Rapport qualitatif PDF 15 pages avec photos dirigeants Wikipedia, pipeline LLM cascade, sections histoire/vision/marché/risques.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Optimisations performance",
    description:
      "Cache yfinance, pre-warming Railway, fail-fast Groq sur rate limit, PDF DPI optimisé. Analyses société < 90s.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Mode édition dashboard (V1 visuel)",
    description:
      "Ctrl+Alt+E pour activer le mode édition. Bordures pointillées sur les blocs. V1 visuelle, drag & drop en V2.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Page admin monitoring",
    description:
      "Tableau de bord interne avec timings par node, providers LLM utilisés, warnings audit, breakdown par writer.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Mode édition dashboard (V2 fonctionnel)",
    description:
      "Drag & drop réel des blocs via react-grid-layout. Layout persisté par utilisateur dans localStorage. Resize visuel. Activable via Ctrl+Alt+E.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Comptes utilisateurs + historique d'analyses",
    description:
      "Sauvegarde des analyses dans Supabase, sidebar latérale avec historique renommable, favoris (étoiles), suppression. Ré-ouverture instantanée sans relancer le pipeline.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Multi-clés Groq + LLM cascade enrichi",
    description:
      "Rotation automatique entre plusieurs clés Groq + cascade Mistral Large → Cerebras Qwen → Anthropic Haiku → Gemini en fallback. Plus aucun blocage rate limit.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "API publique v1 (pay-per-use)",
    description:
      "Endpoints documentés (snapshot, ratios, analyse, livrables) avec authentification clé fsk_*, rate limits Redis 30/min — 1000/jour, tarification 0,05–2 €/appel.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Extension Chrome \"Analyser sur FinSight\"",
    description:
      "Bouton injecté sur Yahoo Finance, TradingView, Boursorama, Investing, Bloomberg, MarketWatch, Seeking Alpha. Détection auto du ticker, 1 clic = analyse complète.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "PWA installable + mobile responsive",
    description:
      "FinSight installable comme app native (iOS, Android, Windows). Manifest + service worker. Pages lecture optimisées smartphone (share, vitrine, résultats).",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Système de rappels post-analyse",
    description:
      "6 triggers : prix cible, earnings, dividende, news, date custom, résultats trimestriels. Notification email (Resend) + push browser (VAPID/pywebpush).",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Partage public d'analyse",
    description:
      "URL publique partageable + boutons LinkedIn / Reddit / Facebook / Gmail / Copy. Growth loop : 10 partages LinkedIn = 3 analyses gratuites.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "FEC parser (B2B comptable français)",
    description:
      "Import du Fichier des Écritures Comptables (arrêté 29 juillet 2013), reconstruction P&L et bilan depuis le PCG, base pour intégrations Pennylane / Sage.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Système Sentinelle (monitoring prod auto)",
    description:
      "Capture automatique des erreurs pipeline (table pipeline_errors), déduplication 1h, wake-up Claude Code via routine sur incident — diagnostic + fix sans intervention humaine.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Stripe intégration + plans payants",
    description:
      "Checkout Stripe en live, customer portal, webhooks pour synchronisation des abonnements. Plans Découverte gratuit, Essentiel 34,99€, Pro 44,99€, Équipe 199€/siège, Enterprise 299–499€/siège.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "RGPD + CGU + cookies + mentions légales",
    description:
      "Banner cookies conforme, droit à l'oubli (art.17), portabilité (art.20 export JSON), CGU complètes, charte de confidentialité, mentions légales. Audit complet réalisé.",
    date: "Avril 2026",
    status: "shipped",
  },
  {
    title: "Mode sombre + i18n 6 langues",
    description:
      "Dark mode avec logo blanc adapté. Interface et livrables (PDF/PPTX/XLSX) traduits en FR, EN, ES, DE, IT, PT. Conversion devise live (EUR/USD/GBP/CHF/JPY/CAD).",
    date: "Avril 2026",
    status: "shipped",
  },
];

const WIP: RoadmapItem[] = [
  {
    title: "Streaming des réponses LLM (SSE)",
    description:
      "Affichage progressif des synthèses LLM au lieu d'attendre la fin. UX premium type ChatGPT pour les sections éditoriales longues.",
    date: "Q2 2026",
    status: "wip",
  },
  {
    title: "Bibliothèque de blocs additionnels (palette)",
    description:
      "Permettre à l'utilisateur d'ajouter / remplacer des blocs depuis une palette : compte de résultat simplifié, bilan agrégé, performance ETF vs paniers, calendrier earnings, etc.",
    date: "Q2 2026",
    status: "wip",
  },
  {
    title: "Connecteurs Pennylane et Sage",
    description:
      "Import direct des comptes via API Pennylane et Sage Cloud (suite logique du parser FEC). Permet aux cabinets comptables d'analyser leurs clients en un clic.",
    date: "Q2 2026",
    status: "wip",
  },
];

const PLANNED: RoadmapItem[] = [
  {
    title: "Portrait d'entreprise non cotées (Pappers V2)",
    description:
      "Branchement à Pappers V2 pour analyser les 3,5 millions d'entreprises françaises non cotées : PME, ETI, deals M&A. Disponible Q2 2026.",
    date: "Q2 2026",
    status: "planned",
  },
  {
    title: "Watchlists + alertes prix consolidées",
    description:
      "Watchlists thématiques (ex: \"Luxe européen\", \"Cloud US\"), alertes prix configurables par ticker, dashboard de suivi quotidien.",
    date: "Courant 2026",
    status: "planned",
  },
  {
    title: "Score FinSight propriétaire",
    description:
      "Note d'investissement composite (qualité, valorisation, momentum, gouvernance). Vocation : signal alternatif de référence pour gérants et family offices.",
    date: "Fin 2026",
    status: "planned",
  },
  {
    title: "Dataset FinSight Trends (signal alternatif)",
    description:
      "Stockage anonymisé des tickers/secteurs analysés → dataset vendable aux hedge funds. Signal d'attention investisseur retail/PME en temps réel.",
    date: "Fin 2026",
    status: "planned",
  },
  {
    title: "White-label Enterprise + on-premise",
    description:
      "Personnalisation complète (logo, charte, sous-domaine) pour banques, conseillers, cabinets. Déploiement on-premise via Docker Compose pour les exigences de souveraineté.",
    date: "Fin 2026",
    status: "planned",
  },
  {
    title: "Bibliothèque comptable simplifiée (CR + bilan)",
    description:
      "Compte de résultat simplifié et bilan agrégé sectoriel directement dans l'interface post-analyse, calculés à partir des consolidés des sociétés couvertes.",
    date: "Q3 2026",
    status: "planned",
  },
  {
    title: "Mode collaboratif équipe",
    description:
      "Espaces partagés multi-utilisateurs, commentaires sur les analyses, annotations sur les livrables, workflow d'approbation pour les comités d'investissement.",
    date: "Q3 2026",
    status: "planned",
  },
];

export default function RoadmapPage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="container-vitrine pt-20 md:pt-28 pb-16 max-w-4xl">
          <div className="label-vitrine mb-5">Roadmap</div>
          <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-4xl md:text-6xl font-bold">
            Ce qu&apos;on livre.
            <br />
            <span className="text-text-muted">
              Ce qu&apos;on prépare.
              <br />
              Ce qu&apos;on vise.
            </span>
          </h1>
          <p className="mt-8 text-lg text-text-secondary leading-relaxed">
            Transparence totale. Voici l&apos;état exact du développement
            FinSight, mis à jour à chaque livraison. Aucune feature listée ici
            n&apos;est garantie dans les délais — nous évoluons vite et
            ré-priorisons selon les retours.
          </p>
        </section>

        <Section
          title="Livré"
          icon={<CheckCircle className="w-4 h-4 text-signal-buy" />}
          items={SHIPPED}
          tone="shipped"
        />

        <Section
          title="En cours"
          icon={<Clock className="w-4 h-4 text-amber-600" />}
          items={WIP}
          tone="wip"
        />

        <Section
          title="Prochainement"
          icon={<Target className="w-4 h-4 text-accent-primary" />}
          items={PLANNED}
          tone="planned"
        />

        {/* CTA */}
        <section className="bg-surface-inverse text-text-inverse">
          <div className="container-vitrine py-20 md:py-24 max-w-3xl text-center">
            <h2 className="font-serif text-3xl md:text-4xl font-semibold tracking-tight mb-4">
              Une feature manque ? Suggérez-la.
            </h2>
            <p className="text-text-inverse/70 mb-8">
              Nous priorisons en fonction des retours utilisateurs. Si quelque
              chose vous manque, dites-le.
            </p>
            <Link
              href="/contact?type=suggestion"
              className="inline-flex items-center gap-2 px-5 py-3 bg-accent-primary text-accent-primary-fg text-sm font-medium rounded-md hover:bg-accent-primary-hover transition-colors"
            >
              Proposer une feature
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}

function Section({
  title,
  icon,
  items,
  tone,
}: {
  title: string;
  icon: React.ReactNode;
  items: RoadmapItem[];
  tone: "shipped" | "wip" | "planned";
}) {
  const bg = tone === "shipped" ? "bg-surface" : tone === "wip" ? "bg-surface-muted" : "bg-surface";
  const border = "border-border-default";
  return (
    <section className={`${bg} border-y ${border}`}>
      <div className="container-vitrine py-20 md:py-24 max-w-5xl">
        <div className="flex items-center gap-3 mb-12">
          {icon}
          <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
            {title}
          </h2>
          <span className="text-sm text-text-muted ml-auto">{items.length} entrées</span>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((item) => (
            <article
              key={item.title}
              className="card-vitrine flex flex-col h-full"
            >
              <div className="flex items-baseline justify-between gap-3 mb-2">
                <h3 className="text-base font-semibold text-text-primary leading-tight">
                  {item.title}
                </h3>
                {item.date && (
                  <span className="text-2xs uppercase tracking-widest text-text-muted shrink-0">
                    {item.date}
                  </span>
                )}
              </div>
              <p className="text-sm text-text-muted leading-relaxed">
                {item.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
