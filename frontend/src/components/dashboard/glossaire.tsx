"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const TERMS: { term: string; def: string }[] = [
  { term: "P/E Ratio (Price-to-Earnings)", def: "Cours de l'action divisé par le bénéfice net par action. Un P/E élevé peut indiquer une attente de forte croissance ou une survalorisation." },
  { term: "EV / EBITDA", def: "Valeur d'entreprise (Equity + Dette nette) divisée par l'EBITDA. Multiple de référence pour comparer des sociétés à structures de capital différentes." },
  { term: "EV / Revenue", def: "Valeur d'entreprise divisée par le chiffre d'affaires. Utile pour des sociétés non rentables ou en forte croissance." },
  { term: "ROE (Return on Equity)", def: "Bénéfice net divisé par les capitaux propres moyens. Mesure la rentabilité des capitaux propres engagés par les actionnaires." },
  { term: "ROIC (Return on Invested Capital)", def: "NOPAT divisé par le capital investi (dette + equity). Mesure la création de valeur économique par rapport au coût du capital." },
  { term: "Marge EBITDA", def: "EBITDA divisé par le chiffre d'affaires. Mesure la rentabilité opérationnelle avant amortissements et politique de financement." },
  { term: "Marge Nette", def: "Bénéfice net divisé par le chiffre d'affaires. Reflète la rentabilité finale après tous les coûts (opérationnels, financiers, fiscaux)." },
  { term: "Marge Brute", def: "(Chiffre d'affaires – Coûts des biens vendus) / Chiffre d'affaires. Indique le pricing power et l'efficience de production." },
  { term: "Dette Nette / EBITDA", def: "Dette nette (Dette financière – Trésorerie) divisée par l'EBITDA. Mesure la capacité à rembourser la dette via la génération opérationnelle. Sain < 3x." },
  { term: "Free Cash Flow (FCF) Yield", def: "FCF divisé par la capitalisation boursière. Indique le rendement cash réel généré par chaque euro investi." },
  { term: "Current Ratio", def: "Actifs courants / Passifs courants. Mesure la liquidité à court terme. > 1 = capacité à honorer ses engagements." },
  { term: "Croissance du CA (YoY)", def: "Variation en pourcentage du chiffre d'affaires d'une année sur l'autre. Indicateur clé de la dynamique commerciale." },
  { term: "Altman Z-Score", def: "Score composite (5 ratios) prédisant le risque de faillite à 2 ans. > 2,99 = sain · 1,8 – 2,99 = zone grise · < 1,8 = détresse." },
  { term: "WACC (Weighted Average Cost of Capital)", def: "Coût moyen pondéré du capital. Taux d'actualisation utilisé en DCF pour ramener les flux futurs à valeur présente." },
  { term: "DCF (Discounted Cash Flow)", def: "Méthode de valorisation actualisant les flux de trésorerie futurs au coût du capital. Référence académique pour estimer la valeur intrinsèque." },
];

export function Glossaire() {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-white border border-ink-200 rounded-md">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
            Glossaire des termes financiers
          </div>
          <div className="text-sm text-ink-800">Comprendre les indicateurs</div>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-ink-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-ink-100 space-y-3">
          {TERMS.map((t) => (
            <div key={t.term}>
              <div className="text-xs font-semibold text-ink-900">{t.term}</div>
              <div className="text-xs text-ink-600 mt-0.5 leading-relaxed">{t.def}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
