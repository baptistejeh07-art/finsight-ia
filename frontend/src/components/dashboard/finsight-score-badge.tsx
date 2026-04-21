"use client";

import { useState } from "react";
import { Award, ChevronDown } from "lucide-react";

export interface FinSightScore {
  global: number;
  grade: string;        // A, B, C, D, E
  verdict: string;
  quality: number;
  value: number;
  momentum: number;
  governance: number;
  details?: Record<string, unknown>;
}

interface Props {
  score: FinSightScore;
  /** "compact" pour header (badge inline), "full" pour bloc dashboard */
  variant?: "compact" | "full";
}

const GRADE_COLOR: Record<string, string> = {
  A: "bg-emerald-100 text-emerald-700 border-emerald-300",
  B: "bg-lime-100 text-lime-700 border-lime-300",
  C: "bg-amber-100 text-amber-700 border-amber-300",
  D: "bg-orange-100 text-orange-700 border-orange-300",
  E: "bg-red-100 text-red-700 border-red-300",
};

const BAR_COLOR: Record<string, string> = {
  quality: "bg-purple-500",
  value: "bg-blue-500",
  momentum: "bg-emerald-500",
  governance: "bg-amber-500",
};

export function FinSightScoreBadge({ score, variant = "compact" }: Props) {
  const [open, setOpen] = useState(false);
  const colorClass = GRADE_COLOR[score.grade] || GRADE_COLOR.C;

  if (variant === "compact") {
    return (
      <div className="relative inline-flex">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className={
            "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-bold transition-all hover:shadow-sm " +
            colorClass
          }
          title={score.verdict}
        >
          <Award className="w-3.5 h-3.5" />
          <span className="font-mono">{score.global}/100</span>
          <span className="text-[10px] uppercase tracking-wider opacity-75">·{score.grade}</span>
          <ChevronDown className={"w-3 h-3 transition-transform " + (open ? "rotate-180" : "")} />
        </button>
        {open && (
          <div className="absolute top-full mt-1 right-0 z-50 w-72 bg-white border border-ink-200 rounded-md shadow-xl p-3 animate-fade-in">
            <ScoreBreakdown score={score} />
          </div>
        )}
      </div>
    );
  }

  // Full variant — pour bloc dashboard
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-navy-500" />
          <span className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Score FinSight
          </span>
        </div>
        <span className={"text-xs font-bold px-2 py-0.5 rounded border " + colorClass}>
          {score.grade}
        </span>
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <span className="text-4xl font-bold text-ink-900 font-mono">{score.global}</span>
        <span className="text-sm text-ink-500">/100</span>
      </div>
      <p className="text-xs text-ink-700 font-medium mb-4">{score.verdict}</p>

      <ScoreBreakdown score={score} compact />

      <a
        href="/methodologie#score-finsight"
        className="text-[10px] text-navy-500 hover:underline mt-auto pt-2"
      >
        Comment est calculé ce score ? →
      </a>
    </div>
  );
}

function ScoreBreakdown({ score, compact = false }: { score: FinSightScore; compact?: boolean }) {
  const lines: Array<{ key: keyof typeof BAR_COLOR; label: string; value: number }> = [
    { key: "quality", label: "Qualité", value: score.quality },
    { key: "value", label: "Valorisation", value: score.value },
    { key: "momentum", label: "Momentum", value: score.momentum },
    { key: "governance", label: "Gouvernance", value: score.governance },
  ];
  const max = 25;
  return (
    <div className={compact ? "space-y-2" : "space-y-2.5"}>
      {!compact && (
        <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-500 mb-1.5">
          Détail des 4 dimensions
        </div>
      )}
      {lines.map((l) => (
        <div key={l.key}>
          <div className="flex items-center justify-between text-xs mb-0.5">
            <span className="text-ink-700">{l.label}</span>
            <span className="font-mono text-ink-900">
              <strong>{l.value.toFixed(1)}</strong>
              <span className="text-ink-400">/{max}</span>
            </span>
          </div>
          <div className="h-1.5 bg-ink-100 rounded-full overflow-hidden">
            <div
              className={"h-full rounded-full " + BAR_COLOR[l.key]}
              style={{ width: `${(l.value / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
