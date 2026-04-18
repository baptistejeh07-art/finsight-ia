import type { Metadata } from "next";
import Link from "next/link";
import {
  Building2,
  Calculator,
  Briefcase,
  TrendingUp,
  GraduationCap,
  Newspaper,
  Code2,
  ArrowRight,
} from "lucide-react";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Collaboration — Construisons FinSight ensemble",
  description:
    "FinSight est ouvert à la collaboration avec banques d'investissement, cabinets comptables, conseillers en gestion, hedge funds et écoles. Discutons.",
};

const PARTENAIRES = [
  {
    icon: Building2,
    title: "Banques & gestion d'actifs",
    pitch:
      "Intégrer FinSight dans le workflow buy-side : pré-screening de positions, génération automatisée de pitchbooks pour comités, signaux alternatifs.",
    forms: [
      "Licence Enterprise multi-utilisateurs",
      "Connecteurs natifs Bloomberg / FactSet",
      "Modèles personnalisés selon mandat",
    ],
  },
  {
    icon: Calculator,
    title: "Cabinets comptables & expertise",
    pitch:
      "L'import FEC + le portrait Pappers ouvrent un produit unique : analyse financière, détection précoce de défaillance, dossier de financement clé en main.",
    forms: [
      "Intégration Pennylane, Sage, ACD",
      "Tableaux de bord client multi-entités",
      "Score de risque propriétaire",
    ],
  },
  {
    icon: Briefcase,
    title: "Conseillers en gestion (CGP)",
    pitch:
      "Production de reporting client white-label sur leur portefeuille de positions. Vous gardez la marque, FinSight produit le contenu.",
    forms: [
      "White-label complet (logo, charte)",
      "Rapports trimestriels automatisés",
      "Module patrimonial dédié",
    ],
  },
  {
    icon: TrendingUp,
    title: "Hedge funds & recherche",
    pitch:
      "Accès API aux données enrichies, à la conviction agrégée des analyses et au futur Score FinSight comme signal alternatif systématique.",
    forms: [
      "API à haute fréquence",
      "Historique d'analyses pour backtest",
      "Co-développement de signaux propriétaires",
    ],
  },
  {
    icon: GraduationCap,
    title: "Écoles & universités",
    pitch:
      "Donner aux étudiants en finance un outil professionnel pour leurs travaux dirigés, mémoires et compétitions de stock-picking.",
    forms: [
      "Licences académiques à tarif réduit",
      "Cas pédagogiques basés sur FinSight",
      "Concours d'investissement annuels",
    ],
  },
  {
    icon: Newspaper,
    title: "Médias & édition financière",
    pitch:
      "Enrichir vos contenus éditoriaux avec des analyses FinSight intégrées : graphiques, KPI, mini-pitches embarqués.",
    forms: [
      "Widgets embeddables",
      "Co-branding sur les analyses",
      "Flux RSS d'analyses fraîches",
    ],
  },
  {
    icon: Code2,
    title: "Intégrateurs & développeurs",
    pitch:
      "Vous bâtissez un outil financier ? Branchez l'API FinSight pour produire instantanément analyses, pitchbooks et modèles à vos utilisateurs.",
    forms: [
      "API REST documentée",
      "SDK Python / JavaScript",
      "Programme partenaire avec revenue share",
    ],
  },
];

export default function CollaborationPage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        {/* Hero */}
        <section className="container-vitrine pt-20 md:pt-28 pb-16 max-w-4xl">
          <div className="label-vitrine mb-5">Partenariats</div>
          <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-4xl md:text-6xl font-bold">
            Construisons FinSight
            <br />
            <span className="text-text-muted">ensemble.</span>
          </h1>
          <p className="mt-8 text-lg text-text-secondary leading-relaxed">
            FinSight n&apos;a pas vocation à rester un produit isolé. Banques
            d&apos;investissement, cabinets comptables, conseillers en gestion,
            hedge funds, écoles, médias : nous ouvrons la plateforme à tous les
            acteurs qui veulent bâtir avec nous l&apos;analyse financière de
            demain.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/contact?type=partenariat" className="btn-cta">
              Discutons de votre projet
              <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Link>
            <a href="#partenaires" className="btn-outline">
              Voir les types de partenariats
            </a>
          </div>
        </section>

        {/* Pourquoi collaborer */}
        <section className="bg-surface-muted border-y border-border-default">
          <div className="container-vitrine py-20 md:py-24 max-w-5xl">
            <div className="grid md:grid-cols-3 gap-10">
              {[
                [
                  "Mutualiser l'effort",
                  "Plutôt que chaque acteur réinvente l'analyse, nous mettons à disposition un moteur de qualité institutionnelle, et chacun construit la couche métier qui lui est propre.",
                ],
                [
                  "Valoriser vos données",
                  "Vous avez des données métier propriétaires (FEC, transactions, sentiment client) ? Nous les transformons en valeur ajoutée pour votre offre.",
                ],
                [
                  "Co-développer la roadmap",
                  "Nos partenaires influencent directement la roadmap produit. Une fonctionnalité critique pour votre métier ? Nous la priorisons.",
                ],
              ].map(([title, desc]) => (
                <div key={title}>
                  <h3 className="font-serif text-xl font-semibold text-text-primary mb-3">
                    {title}
                  </h3>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Types de partenariats */}
        <section id="partenaires" className="scroll-mt-20">
          <div className="container-vitrine py-20 md:py-24 max-w-6xl">
            <div className="mb-12 max-w-2xl">
              <div className="label-vitrine mb-3">Types de partenariats</div>
              <h2 className="font-serif text-3xl md:text-4xl font-semibold text-text-primary tracking-tight">
                Sept terrains de jeu, une même méthode.
              </h2>
            </div>
            <div className="grid md:grid-cols-2 gap-6">
              {PARTENAIRES.map((p) => (
                <PartnerCard key={p.title} {...p} />
              ))}
            </div>
          </div>
        </section>

        {/* CTA bas */}
        <section className="bg-surface-inverse text-text-inverse">
          <div className="container-vitrine py-20 md:py-24 max-w-3xl text-center">
            <h2 className="font-serif text-3xl md:text-4xl font-semibold tracking-tight mb-5">
              Vous ne vous reconnaissez dans aucun de ces formats ?
            </h2>
            <p className="text-text-inverse/70 mb-8 leading-relaxed">
              Nous restons ouverts à toute conversation. Si votre métier touche
              à l&apos;analyse, à l&apos;investissement ou à la donnée
              financière, écrivez-nous.
            </p>
            <Link
              href="/contact?type=partenariat"
              className="inline-flex items-center gap-2 px-5 py-3 bg-accent-primary text-accent-primary-fg text-sm font-medium rounded-md hover:bg-accent-primary-hover transition-colors"
            >
              Nous contacter
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}

function PartnerCard({
  icon: Icon,
  title,
  pitch,
  forms,
}: {
  icon: typeof Building2;
  title: string;
  pitch: string;
  forms: string[];
}) {
  return (
    <article className="card-vitrine">
      <div className="flex items-center gap-3 mb-4">
        <span className="w-10 h-10 rounded-md bg-accent-primary/10 text-accent-primary flex items-center justify-center">
          <Icon className="w-5 h-5" />
        </span>
        <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
      </div>
      <p className="text-sm text-text-secondary leading-relaxed mb-4">{pitch}</p>
      <ul className="space-y-1.5">
        {forms.map((f) => (
          <li
            key={f}
            className="text-xs text-text-muted flex items-start gap-2"
          >
            <span className="text-accent-primary mt-0.5">·</span>
            {f}
          </li>
        ))}
      </ul>
    </article>
  );
}
