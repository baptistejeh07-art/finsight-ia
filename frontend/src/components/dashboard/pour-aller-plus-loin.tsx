"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { Synthesis } from "./types";

export function PourAllerPlusLoin({ synthesis }: { synthesis: Synthesis }) {
  const [open, setOpen] = useState(false);

  const blocks: { label: string; content?: string }[] = [
    { label: "Hypothèse Bull", content: synthesis.bull_hypothesis },
    { label: "Hypothèse Base", content: synthesis.base_hypothesis },
    { label: "Hypothèse Bear", content: synthesis.bear_hypothesis },
    { label: "Commentaire valorisation", content: synthesis.valuation_comment },
    { label: "Commentaire DCF", content: synthesis.dcf_commentary },
    { label: "Commentaire ratios", content: synthesis.ratio_commentary },
    { label: "Commentaire pairs", content: synthesis.peers_commentary },
    { label: "Trigger Achat", content: synthesis.buy_trigger },
    { label: "Trigger Vente", content: synthesis.sell_trigger },
  ].filter((b) => b.content && b.content.trim().length > 0);

  if (blocks.length === 0) return null;

  return (
    <div className="bg-white border border-ink-200 rounded-md">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
            Pour aller plus loin
          </div>
          <div className="text-sm text-ink-800">
            Interprétation, hypothèses et raisonnement IA détaillé
          </div>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-ink-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-ink-100 space-y-4">
          {blocks.map((b) => (
            <div key={b.label}>
              <div className="text-[10px] font-semibold uppercase tracking-[1.2px] text-ink-500 mb-1.5">
                {b.label}
              </div>
              <div className="text-xs text-ink-700 leading-relaxed whitespace-pre-line">
                {b.content}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
