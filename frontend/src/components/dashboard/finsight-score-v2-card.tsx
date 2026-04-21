"use client";

import { useState } from "react";
import { Award, ChevronDown, Shield, TrendingUp, DollarSign, Activity } from "lucide-react";
import type { FinSightScoreV2Data, FinSightScoreV2Reco } from "./types";

interface Props {
  data: FinSightScoreV2Data;
}

const SCORE_META = {
  quality:  { icon: <Shield    className="w-3.5 h-3.5" />, label: "Qualité",     color: "bg-purple-500", lightBg: "bg-purple-50", border: "border-purple-200", text: "text-purple-700" },
  value:    { icon: <DollarSign className="w-3.5 h-3.5" />, label: "Valeur",      color: "bg-blue-500",   lightBg: "bg-blue-50",   border: "border-blue-200",   text: "text-blue-700" },
  momentum: { icon: <TrendingUp className="w-3.5 h-3.5" />, label: "Momentum",    color: "bg-emerald-500",lightBg: "bg-emerald-50",border: "border-emerald-200",text: "text-emerald-700" },
  risk:     { icon: <Activity   className="w-3.5 h-3.5" />, label: "Risque (inv)",color: "bg-amber-500",  lightBg: "bg-amber-50",  border: "border-amber-200",  text: "text-amber-700" },
} as const;

const RECO_COLOR = {
  BUY: "bg-emerald-100 text-emerald-700 border-emerald-300",
  HOLD: "bg-amber-100 text-amber-700 border-amber-300",
  SELL: "bg-red-100 text-red-700 border-red-300",
} as const;

/**
 * Bloc FinSight Score v2 : 4 scores + recos par profil.
 *
 * Layout :
 * - Bannière avec 4 scores en cards couleurs
 * - Sous-bannière "Recommandation par profil" : 5 profils avec leur reco
 *   contextuelle (BUY/HOLD/SELL + composite + conviction)
 * - Bouton pour changer le profil "sélectionné" (auto-focus dans le reasoning)
 */
export function FinSightScoreV2Card({ data }: Props) {
  const [activeProfile, setActiveProfile] = useState<string>("balanced");

  const scoreQ = data.scores.quality.score;
  const scoreV = data.scores.value.score;
  const scoreM = data.scores.momentum.score;
  const scoreR = data.scores.risk.score;

  const recoActive = data.recommendations[activeProfile];
  const profileKeys = Object.keys(data.recommendations);

  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-3 pb-2 border-b border-ink-100 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[1.5px] text-ink-500 font-semibold">
            <Award className="w-3 h-3 text-navy-500" />
            FinSight Score v2 — 4 dimensions
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            Reco contextuelle selon profil investisseur
          </div>
        </div>
      </div>

      {/* 4 scores grid */}
      <div className="grid grid-cols-4 gap-2 p-3 border-b border-ink-100">
        <ScoreCell name="quality"  value={scoreQ} />
        <ScoreCell name="value"    value={scoreV} />
        <ScoreCell name="momentum" value={scoreM} />
        <ScoreCell name="risk"     value={scoreR} />
      </div>

      {/* Recos par profil */}
      <div className="flex-1 overflow-auto px-3 py-3">
        <div className="text-[10px] uppercase tracking-wider text-ink-500 font-semibold mb-2">
          Recommandation par profil investisseur
        </div>
        <div className="space-y-1.5">
          {profileKeys.map((key) => {
            const reco = data.recommendations[key];
            const isActive = activeProfile === key;
            const recoClass = RECO_COLOR[reco.recommendation] || RECO_COLOR.HOLD;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setActiveProfile(key)}
                className={
                  "w-full flex items-center gap-2 px-2.5 py-1.5 rounded border text-left transition-all " +
                  (isActive
                    ? "border-navy-500 bg-navy-50 shadow-sm"
                    : "border-ink-100 bg-white hover:bg-ink-50")
                }
              >
                <span className="flex-1 text-xs text-ink-800 font-medium">
                  {reco.profile_label}
                </span>
                <span className="text-[10px] font-mono text-ink-500">
                  {reco.composite.toFixed(0)}
                </span>
                <span className={"px-2 py-0.5 rounded text-[9px] font-bold uppercase border " + recoClass}>
                  {reco.recommendation}
                </span>
                <span className="text-[10px] text-ink-500 w-8 text-right">
                  {Math.round(reco.conviction * 100)}%
                </span>
              </button>
            );
          })}
        </div>

        {/* Reasoning du profil actif */}
        {recoActive && (
          <div className="mt-3 p-2.5 bg-ink-50 border border-ink-100 rounded">
            <div className="flex items-center gap-2 mb-1">
              <span className={"text-[10px] font-bold uppercase px-2 py-0.5 rounded border " +
                (RECO_COLOR[recoActive.recommendation] || RECO_COLOR.HOLD)}>
                {recoActive.recommendation}
              </span>
              <span className="text-[11px] text-ink-700 font-semibold">
                {recoActive.profile_label}
              </span>
              <span className="text-[10px] text-ink-500 ml-auto">
                composite {recoActive.composite.toFixed(1)}/100 · conviction {Math.round(recoActive.conviction * 100)}%
              </span>
            </div>
            <div className="text-[11px] text-ink-700 leading-relaxed">
              {recoActive.reasoning}
            </div>
            <div className="mt-2 flex gap-1 text-[9px] text-ink-500">
              Pondération :
              {(Object.entries(recoActive.weights) as [string, number][]).map(([k, w]) => (
                <span key={k} className="font-mono">
                  {k}:{Math.round(w * 100)}%
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ScoreCell({ name, value }: { name: keyof typeof SCORE_META; value: number }) {
  const meta = SCORE_META[name];
  return (
    <div className={`rounded border ${meta.border} ${meta.lightBg} p-2 flex flex-col items-center`}>
      <div className={`flex items-center gap-1 text-[9px] uppercase tracking-wider font-semibold ${meta.text}`}>
        {meta.icon}
        <span>{meta.label}</span>
      </div>
      <div className={`text-xl font-mono font-bold mt-0.5 ${meta.text}`}>
        {value.toFixed(0)}
      </div>
      <div className="w-full h-1 bg-white/60 rounded-full mt-1 overflow-hidden">
        <div className={`h-full ${meta.color}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}
