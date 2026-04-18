"use client";

import Link from "next/link";
import { useState } from "react";
import { Check } from "lucide-react";

type Tab = "individuel" | "entreprise" | "api";

interface Plan {
  name: string;
  tagline: string;
  price: string;
  priceUnit: string;
  cta: string;
  ctaHref: string;
  highlight?: boolean;
  features: string[];
}

const PLANS_INDIVIDUEL: Plan[] = [
  {
    name: "Découverte",
    tagline: "Pour tester FinSight",
    price: "0 €",
    priceUnit: "Gratuit pour tous",
    cta: "Essayer maintenant",
    ctaHref: "/app",
    features: [
      "3 analyses société par mois",
      "Pitchbook PowerPoint",
      "Rapport PDF",
      "Modèle Excel",
      "Accès aux données yfinance",
      "Conversation Q&A limitée",
    ],
  },
  {
    name: "Essentiel",
    tagline: "Pour la productivité quotidienne",
    price: "34,99 €",
    priceUnit: "Par mois, facturation mensuelle",
    cta: "Choisir Essentiel",
    ctaHref: "/app",
    highlight: true,
    features: [
      "Tout du plan Découverte, plus :",
      "20 analyses société par mois",
      "Comparatif jusqu'à 6 sociétés",
      "Analyse secteur et indice",
      "Conversation Q&A illimitée",
      "Crédits supplémentaires à l'unité",
      "Historique d'analyses persistant",
    ],
  },
  {
    name: "Pro",
    tagline: "Tirer le meilleur de FinSight",
    price: "44,99 €",
    priceUnit: "Par mois, facturation mensuelle",
    cta: "Choisir Pro",
    ctaHref: "/app",
    features: [
      "Tout du plan Essentiel, plus :",
      "Portrait d'entreprise (sociétés non cotées)",
      "8 portraits Pappers par mois",
      "Accès anticipé aux nouvelles fonctionnalités",
      "Score FinSight propriétaire",
      "Export white-label de vos pitchbooks",
      "Support prioritaire",
    ],
  },
];

const PLANS_ENTREPRISE: Plan[] = [
  {
    name: "Équipe",
    tagline: "Pour les équipes de 5 à 50 personnes",
    price: "Sur devis",
    priceUnit: "À partir de 199 €/siège/mois",
    cta: "Demander un devis",
    ctaHref: "/contact?plan=equipe",
    features: [
      "Tout du plan Pro pour chaque utilisateur",
      "Espace équipe partagé",
      "Bibliothèque d'analyses commune",
      "Single Sign-On (SAML/OIDC)",
      "Permissions granulaires",
      "Support dédié",
    ],
  },
  {
    name: "Enterprise",
    tagline: "Pour les institutions opérant à grande échelle",
    price: "299–499 €",
    priceUnit: "Par siège/mois, négocié selon volume",
    cta: "Contacter les ventes",
    ctaHref: "/contact?plan=enterprise",
    highlight: true,
    features: [
      "Tout du plan Équipe, plus :",
      "Déploiement on-premise possible",
      "White-label complet",
      "Workflows et intégrations sur mesure",
      "Connecteurs Pennylane, Sage, FEC",
      "SLA et conformité (ISO 27001 en cours)",
      "Account manager dédié",
    ],
  },
];

const PLANS_API: Plan[] = [
  {
    name: "Léger",
    tagline: "Endpoints individuels",
    price: "0,05 €",
    priceUnit: "Par appel — données et ratios",
    cta: "Documentation API",
    ctaHref: "/contact?plan=api",
    features: [
      "Endpoints data (snapshot, ratios)",
      "Quotas mensuels élevés",
      "Idéal pour intégrations légères",
    ],
  },
  {
    name: "Standard",
    tagline: "Analyses et synthèses",
    price: "0,50 €",
    priceUnit: "Par appel — analyse complète",
    cta: "Documentation API",
    ctaHref: "/contact?plan=api",
    highlight: true,
    features: [
      "Analyse société complète (JSON)",
      "Synthèse IA + ratios + valorisation",
      "Webhook de complétion",
    ],
  },
  {
    name: "Pro",
    tagline: "Pitchbook et exports",
    price: "2,00 €",
    priceUnit: "Par appel — livrables PDF/PPTX/XLSX",
    cta: "Documentation API",
    ctaHref: "/contact?plan=api",
    features: [
      "Génération des 3 livrables",
      "Stockage cloud sécurisé 30 jours",
      "Personnalisation white-label",
    ],
  },
];

export function Pricing() {
  const [tab, setTab] = useState<Tab>("individuel");
  const plans =
    tab === "individuel"
      ? PLANS_INDIVIDUEL
      : tab === "entreprise"
        ? PLANS_ENTREPRISE
        : PLANS_API;

  return (
    <section id="tarification" className="bg-surface scroll-mt-20">
      <div className="container-vitrine py-24 md:py-32">
        <h2 className="font-serif text-center text-4xl md:text-5xl font-bold text-text-primary tracking-tight">
          Tarification
        </h2>
        <p className="text-center text-text-muted mt-3 text-sm md:text-base">
          Choisissez le plan adapté à votre usage. Sans engagement.
        </p>

        {/* Toggle */}
        <div className="mt-10 flex justify-center">
          <div className="inline-flex bg-surface-muted border border-border-default rounded-full p-1 text-sm">
            <TabButton active={tab === "individuel"} onClick={() => setTab("individuel")}>
              Individuel
            </TabButton>
            <TabButton active={tab === "entreprise"} onClick={() => setTab("entreprise")}>
              Équipe & Entreprise
            </TabButton>
            <TabButton active={tab === "api"} onClick={() => setTab("api")}>
              API
            </TabButton>
          </div>
        </div>

        {/* Cards */}
        <div
          className={`mt-12 grid gap-6 ${
            plans.length === 3
              ? "grid-cols-1 md:grid-cols-3"
              : "grid-cols-1 md:grid-cols-2 max-w-4xl mx-auto"
          }`}
        >
          {plans.map((plan) => (
            <PlanCard key={plan.name} plan={plan} />
          ))}
        </div>
      </div>
    </section>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-full transition-colors ${
        active
          ? "bg-surface-elevated text-text-primary shadow-sm"
          : "text-text-muted hover:text-text-secondary"
      }`}
    >
      {children}
    </button>
  );
}

function PlanCard({ plan }: { plan: Plan }) {
  return (
    <div
      className={`card-vitrine flex flex-col h-full ${
        plan.highlight ? "border-accent-primary ring-1 ring-accent-primary/20" : ""
      }`}
    >
      <div className="mb-5">
        <h3 className="text-xl font-semibold text-text-primary">{plan.name}</h3>
        <p className="text-sm text-text-muted mt-1">{plan.tagline}</p>
      </div>

      <div className="mb-5">
        <div className="text-3xl font-bold text-text-primary">{plan.price}</div>
        <div className="text-xs text-text-muted mt-1">{plan.priceUnit}</div>
      </div>

      <Link
        href={plan.ctaHref}
        className={
          plan.highlight
            ? "btn-cta w-full justify-center mb-6"
            : "btn-outline w-full justify-center mb-6"
        }
      >
        {plan.cta}
      </Link>

      <ul className="space-y-2.5 text-sm text-text-secondary">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2">
            <Check className="w-4 h-4 text-accent-primary shrink-0 mt-0.5" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
