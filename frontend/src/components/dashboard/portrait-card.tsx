"use client";

import { useState } from "react";
import { Sparkles, Lock } from "lucide-react";
import toast from "react-hot-toast";

export function PortraitCard({ ticker, companyName }: { ticker: string; companyName: string }) {
  const [busy] = useState(false);

  function handleClick() {
    toast(
      "Le Portrait d'entreprise sera disponible avec le plan 44,99 €/mois (8 portraits/mois inclus). Bientôt en ligne.",
      { icon: "🔒", duration: 5000 }
    );
  }

  return (
    <div className="bg-gradient-to-br from-navy-50 to-white border border-navy-200 rounded-md p-5">
      <div className="flex items-start gap-3 mb-3">
        <div className="shrink-0 w-9 h-9 rounded-md bg-navy-500 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div>
          <div className="text-sm font-bold text-ink-900">Portrait d&apos;entreprise</div>
          <div className="text-xs text-ink-600 mt-0.5">
            Rapport qualitatif complémentaire — dirigeants, ADN, signaux stratégiques.
          </div>
        </div>
      </div>
      <ul className="text-[11px] text-ink-600 mb-4 space-y-1 pl-9">
        <li>• Profil CEO + management + signaux de départ</li>
        <li>• Histoire, ADN, crises traversées</li>
        <li>• Concurrence approfondie + signaux R&amp;D / brevets</li>
        <li>• Réputation, culture, Glassdoor</li>
      </ul>
      <button
        onClick={handleClick}
        disabled={busy}
        className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded bg-navy-500 text-white text-xs font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50"
      >
        <Lock className="w-3.5 h-3.5" />
        Générer le portrait de {ticker || companyName}
      </button>
      <div className="text-[10px] text-ink-500 italic text-center mt-2">
        Disponible avec le plan 44,99 €/mois — 8 portraits inclus
      </div>
    </div>
  );
}
