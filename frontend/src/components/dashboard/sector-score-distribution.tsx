"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import type { SectorTicker } from "./types";

/**
 * Distribution des FinSight Score des tickers du secteur ou indice.
 * Buckets : 0-40 (SELL) · 40-55 (HOLD-) · 55-70 (HOLD+) · 70-85 (BUY) · 85-100 (STRONG BUY).
 */
export function SectorScoreDistribution({
  tickers,
  label,
}: {
  tickers: SectorTicker[] | undefined | null;
  label?: string;
}) {
  if (!tickers || tickers.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Aucun ticker disponible.</span>
      </div>
    );
  }

  const scores: number[] = [];
  for (const t of tickers) {
    const s = (t.ratios?.score_global ?? t.ratios?.finsight_score ?? t.ratios?.score) as number | null | undefined;
    if (s != null && Number.isFinite(s)) scores.push(s);
  }

  if (scores.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Scores FinSight non disponibles sur les tickers.</span>
      </div>
    );
  }

  const buckets = [
    { range: "0-40\nSELL", min: 0, max: 40, color: "#A82020" },
    { range: "40-55\nHOLD-", min: 40, max: 55, color: "#D08000" },
    { range: "55-70\nHOLD+", min: 55, max: 70, color: "#B0A020" },
    { range: "70-85\nBUY", min: 70, max: 85, color: "#3A8A3A" },
    { range: "85-100\nSTRONG", min: 85, max: 101, color: "#1A5A1A" },
  ];

  const data = buckets.map((b) => ({
    range: b.range,
    count: scores.filter((s) => s >= b.min && s < b.max).length,
    color: b.color,
  }));

  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  const median = [...scores].sort((a, b) => a - b)[Math.floor(scores.length / 2)];

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Distribution des scores FinSight{label ? ` — ${label}` : ""}
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            {scores.length} sociétés · répartition par bucket de reco
          </div>
        </div>
        <div className="text-right text-[10px] text-ink-500 font-mono">
          Moyenne {avg.toFixed(0)}
          <br />
          Médiane {median.toFixed(0)}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="range" tick={{ fontSize: 10, fill: "#6B7280" }} interval={0} />
            <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} allowDecimals={false} width={30} />
            <Tooltip formatter={(v: number) => [`${v} société(s)`, "Effectif"]} contentStyle={{ fontSize: 11 }} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              {data.map((d, i) => (
                <Cell key={`cell-${i}`} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
