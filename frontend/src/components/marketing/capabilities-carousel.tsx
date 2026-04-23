"use client";

import Link from "next/link";
import { useRef } from "react";
import { ArrowUpRight, ChevronLeft, ChevronRight } from "lucide-react";

interface Card {
  eyebrow: string;
  title: string;
  description: string;
  href: string;
  tags: string[];
  accent?: "navy" | "green" | "amber";
}

const CARDS: Card[] = [
  {
    eyebrow: "La pile FinSight",
    title: "Sept agents spécialisés,\nun seul rapport auditable.",
    description:
      "Collecte de données, calculs déterministes, synthèse, contradiction, gouvernance — chaque agent a un rôle. Chaque chiffre est sourcé, chaque hypothèse documentée.",
    href: "/methodologie#pipeline",
    tags: ["7 agents", "LangGraph", "Traçabilité totale"],
    accent: "navy",
  },
  {
    eyebrow: "Où en êtes-vous dans votre secteur ?",
    title: "Positionnement sectoriel\nen 60 secondes.",
    description:
      "Scores composites 11 secteurs GICS, cartographie valorisation vs croissance, allocation Markowitz optimisée. Les mêmes données que les grands allocataires.",
    href: "/app",
    tags: ["11 secteurs", "Markowitz", "Top 3 convictions"],
    accent: "green",
  },
  {
    eyebrow: "Sociétés cotées · PME françaises",
    title: "Tapez un ticker ou un SIREN.\nLe reste, c'est nous.",
    description:
      "Société cotée via yfinance, PME française via Pappers + INPI + BODACC. Rapport PDF 20 pages + pitchbook PowerPoint + modèle Excel, chartés.",
    href: "/app",
    tags: ["Coté", "Non coté", "3 livrables"],
    accent: "navy",
  },
  {
    eyebrow: "Score FinSight",
    title: "Signal validé\nstatistiquement.",
    description:
      "Backtest walk-forward sur 10 ans, 100 sociétés S&P 500. Balanced +8,9 % d'alpha annualisé (t=+2,10, significatif 95 %). Growth Tech +19,4 %, Value cyclique +24 %.",
    href: "/methodologie#score",
    tags: ["Backtest 10 ans", "+8,9 % α", "t=2,10"],
    accent: "green",
  },
  {
    eyebrow: "Gouvernance IA",
    title: "Constitution 7 articles,\n4 agents observateurs.",
    description:
      "Price-anchor, conviction bornée, budget mots, traçabilité : chaque sortie LLM est auditée par AgentJustice, AgentEnquête, AgentJournaliste, AgentSociologue.",
    href: "/methodologie#gouvernance",
    tags: ["Constitution", "Cascade LLM", "Audit"],
    accent: "amber",
  },
  {
    eyebrow: "Multi-livrables · Un seul clic",
    title: "Rapport PDF · Pitchbook PPTX · Modèle Excel.",
    description:
      "Même analyse, trois formats. PDF pour la lecture, PPTX pour le comité, Excel pour le stress-test. Tous chartés, tous exportables.",
    href: "/methodologie#livrables",
    tags: ["20 pages PDF", "20 slides PPTX", "7 feuilles XLSX"],
    accent: "navy",
  },
];

function accentCls(a: Card["accent"]) {
  if (a === "green") return "border-signal-buy/30 hover:border-signal-buy";
  if (a === "amber") return "border-signal-hold/30 hover:border-signal-hold";
  return "border-border-default hover:border-accent-primary";
}

export function CapabilitiesCarousel() {
  const scrollerRef = useRef<HTMLDivElement>(null);

  function scrollBy(dir: 1 | -1) {
    const el = scrollerRef.current;
    if (!el) return;
    const card = el.querySelector<HTMLElement>("[data-card]");
    const step = (card?.offsetWidth ?? 380) + 24;
    el.scrollBy({ left: step * dir, behavior: "smooth" });
  }

  return (
    <section className="bg-surface border-y border-border-default">
      <div className="container-vitrine pt-20 md:pt-28 pb-16 md:pb-20">
        <div className="flex items-end justify-between gap-8 mb-10">
          <div>
            <div className="text-xs font-semibold tracking-widest uppercase text-text-muted mb-3">
              ✦ Capacités
            </div>
            <h2 className="font-serif text-3xl md:text-4xl font-bold text-text-primary tracking-tight leading-[1.1] max-w-3xl">
              Explorez la plateforme, section par section.
            </h2>
          </div>
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <button
              onClick={() => scrollBy(-1)}
              aria-label="Défiler à gauche"
              className="w-10 h-10 rounded-full border border-border-default hover:bg-surface-elevated text-text-muted hover:text-text-primary transition-colors flex items-center justify-center"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => scrollBy(1)}
              aria-label="Défiler à droite"
              className="w-10 h-10 rounded-full border border-border-default hover:bg-surface-elevated text-text-muted hover:text-text-primary transition-colors flex items-center justify-center"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div
        ref={scrollerRef}
        className="overflow-x-auto scrollbar-hide scroll-smooth snap-x snap-mandatory pb-20"
        style={{
          scrollPaddingLeft: "5vw",
          scrollPaddingRight: "5vw",
        }}
      >
        <div className="flex gap-6 px-[5vw] min-w-max">
          {CARDS.map((c, i) => (
            <Link
              key={i}
              href={c.href}
              data-card
              className={`group snap-start shrink-0 w-[86vw] sm:w-[520px] md:w-[560px] rounded-xl border-2 ${accentCls(
                c.accent
              )} bg-surface-elevated p-8 md:p-10 transition-colors flex flex-col`}
            >
              <div className="flex items-start justify-between gap-4 mb-6">
                <div className="text-[11px] font-semibold tracking-widest uppercase text-text-muted">
                  {c.eyebrow}
                </div>
                <ArrowUpRight className="w-5 h-5 text-text-muted group-hover:text-text-primary group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-all shrink-0" />
              </div>

              <h3 className="font-serif text-2xl md:text-[28px] font-bold text-text-primary leading-[1.15] mb-5 whitespace-pre-line min-h-[80px]">
                {c.title}
              </h3>

              <p className="text-sm md:text-[15px] text-text-secondary leading-relaxed mb-6 flex-1">
                {c.description}
              </p>

              <div className="flex flex-wrap gap-2 mt-auto">
                {c.tags.map((t) => (
                  <span
                    key={t}
                    className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-surface-muted text-text-muted border border-border-default"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </Link>
          ))}
          <div className="shrink-0 w-[5vw]" aria-hidden />
        </div>
      </div>
    </section>
  );
}
