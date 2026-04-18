"use client";

import { useState } from "react";
import { TrendingUp, Coins, Shield, BarChart3, BookOpen } from "lucide-react";

type Category = "valorisation" | "rentabilite" | "structure" | "risque";

interface Term {
  term: string;
  short: string; // sigle/acronyme
  def: string;
  category: Category;
}

const TERMS: Term[] = [
  // === VALORISATION ===
  {
    term: "Price-to-Earnings",
    short: "P/E",
    def: "Cours de l'action divisé par le bénéfice net par action. Multiple le plus universel ; un P/E élevé signale soit une forte croissance attendue, soit une survalorisation.",
    category: "valorisation",
  },
  {
    term: "Enterprise Value / EBITDA",
    short: "EV/EBITDA",
    def: "Valeur d'entreprise (Equity + Dette nette) divisée par l'EBITDA. Référence pour comparer des sociétés à structures de capital différentes.",
    category: "valorisation",
  },
  {
    term: "Enterprise Value / Revenue",
    short: "EV/Revenue",
    def: "Valeur d'entreprise divisée par le chiffre d'affaires. Utile pour des sociétés non rentables ou en hyper-croissance.",
    category: "valorisation",
  },
  {
    term: "Discounted Cash Flow",
    short: "DCF",
    def: "Méthode actualisant les flux de trésorerie futurs au coût du capital. Référence académique pour estimer la valeur intrinsèque d'une société.",
    category: "valorisation",
  },
  {
    term: "Weighted Average Cost of Capital",
    short: "WACC",
    def: "Coût moyen pondéré du capital. Taux d'actualisation utilisé en DCF pour ramener les flux futurs à valeur présente.",
    category: "valorisation",
  },

  // === RENTABILITÉ ===
  {
    term: "Return on Equity",
    short: "ROE",
    def: "Bénéfice net divisé par les capitaux propres moyens. Mesure la rentabilité des capitaux propres engagés par les actionnaires.",
    category: "rentabilite",
  },
  {
    term: "Return on Invested Capital",
    short: "ROIC",
    def: "NOPAT divisé par le capital investi (dette + equity). Mesure la création de valeur économique au-delà du coût du capital.",
    category: "rentabilite",
  },
  {
    term: "Marge brute",
    short: "GM",
    def: "(Chiffre d'affaires – Coûts des biens vendus) / Chiffre d'affaires. Indique le pricing power et l'efficience de production.",
    category: "rentabilite",
  },
  {
    term: "Marge EBITDA",
    short: "EBITDA %",
    def: "EBITDA divisé par le chiffre d'affaires. Rentabilité opérationnelle avant amortissements et politique de financement.",
    category: "rentabilite",
  },
  {
    term: "Marge nette",
    short: "Net %",
    def: "Bénéfice net divisé par le chiffre d'affaires. Reflète la rentabilité finale après tous les coûts.",
    category: "rentabilite",
  },

  // === STRUCTURE FINANCIÈRE ===
  {
    term: "Dette nette / EBITDA",
    short: "Leverage",
    def: "Dette nette (Dette financière – Trésorerie) divisée par l'EBITDA. Capacité à rembourser via la génération opérationnelle. Sain < 3×.",
    category: "structure",
  },
  {
    term: "Free Cash Flow Yield",
    short: "FCF Yield",
    def: "FCF divisé par la capitalisation boursière. Rendement cash réel généré par chaque euro investi en bourse.",
    category: "structure",
  },
  {
    term: "Current Ratio",
    short: "Liquidité",
    def: "Actifs courants / Passifs courants. Mesure la liquidité à court terme. > 1 = capacité à honorer ses engagements immédiats.",
    category: "structure",
  },
  {
    term: "Croissance du CA",
    short: "CAGR / YoY",
    def: "Variation en pourcentage du chiffre d'affaires d'une année sur l'autre. Indicateur clé de la dynamique commerciale.",
    category: "structure",
  },

  // === RISQUE ===
  {
    term: "Altman Z-Score",
    short: "Z-Score",
    def: "Score composite (5 ratios) prédisant le risque de faillite à 2 ans. > 2,99 = sain · 1,8–2,99 = zone grise · < 1,8 = détresse.",
    category: "risque",
  },
  {
    term: "Beta",
    short: "β",
    def: "Sensibilité du cours d'une action aux mouvements du marché. β = 1 → suit le marché. β > 1 → plus volatil. β < 1 → plus défensif.",
    category: "risque",
  },
];

const CATEGORIES: {
  key: Category;
  label: string;
  icon: typeof TrendingUp;
}[] = [
  { key: "valorisation", label: "Valorisation", icon: TrendingUp },
  { key: "rentabilite", label: "Rentabilité", icon: Coins },
  { key: "structure", label: "Structure financière", icon: BarChart3 },
  { key: "risque", label: "Risque", icon: Shield },
];

export function Glossaire() {
  const [active, setActive] = useState<Category>("valorisation");
  const filtered = TERMS.filter((t) => t.category === active);

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-ink-100 flex items-center gap-3">
        <div className="w-8 h-8 rounded-md bg-navy-50 text-navy-500 flex items-center justify-center">
          <BookOpen className="w-4 h-4" />
        </div>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Glossaire des termes financiers
          </div>
          <div className="text-sm text-ink-800">Comprendre les indicateurs</div>
        </div>
      </div>

      {/* Tabs catégorie */}
      <div className="px-5 pt-3 flex flex-wrap gap-1.5 border-b border-ink-100">
        {CATEGORIES.map((cat) => {
          const isActive = active === cat.key;
          const Icon = cat.icon;
          return (
            <button
              key={cat.key}
              onClick={() => setActive(cat.key)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-t-md border-b-2 transition-colors ${
                isActive
                  ? "border-navy-500 text-ink-900 font-semibold"
                  : "border-transparent text-ink-500 hover:text-ink-700"
              }`}
            >
              <Icon className="w-3 h-3" />
              {cat.label}
            </button>
          );
        })}
      </div>

      {/* Grille de termes */}
      <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((t) => (
          <div
            key={t.term}
            className="border border-ink-100 rounded-md p-3 hover:border-navy-300 transition-colors"
          >
            <div className="flex items-baseline justify-between gap-2 mb-1.5">
              <div className="text-xs font-bold text-ink-900 leading-tight">
                {t.term}
              </div>
              <span className="text-[10px] font-mono text-navy-500 bg-navy-50 px-1.5 py-0.5 rounded shrink-0">
                {t.short}
              </span>
            </div>
            <div className="text-xs text-ink-600 leading-snug">{t.def}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
