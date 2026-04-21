"use client";

import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip, Legend } from "recharts";

/**
 * Radar 6 métriques comparées entre deux entités (sociétés, secteurs ou indices).
 * Chaque métrique est normalisée 0-100 pour permettre la superposition.
 * Convention de normalisation :
 *   - Marges, ROE, ROIC : valeur brute en % (clampée 0-100)
 *   - P/E, EV/EBITDA : inversés (plus bas = mieux), mappés sur 0-100
 */
interface Stats {
  pe_ratio?: number | null;
  ev_ebitda?: number | null;
  ebitda_margin?: number | null;
  net_margin?: number | null;
  roe?: number | null;
  revenue_growth?: number | null;
}

function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, v));
}

function pctFromDecimal(v: number | null | undefined): number | null {
  if (v == null || !Number.isFinite(v)) return null;
  return Math.abs(v) < 2 ? v * 100 : v;
}

function inverseMultiple(v: number | null | undefined, benchmark: number): number {
  if (v == null || !Number.isFinite(v) || v <= 0) return 0;
  const score = (benchmark / v) * 50;
  return clamp01(score);
}

export function CmpMultiplesRadar({
  statsA,
  statsB,
  nameA,
  nameB,
}: {
  statsA: Stats | undefined | null;
  statsB: Stats | undefined | null;
  nameA?: string;
  nameB?: string;
}) {
  const a = statsA || {};
  const b = statsB || {};

  const build = (s: Stats) => [
    { metric: "Marge EBITDA", v: clamp01(pctFromDecimal(s.ebitda_margin) ?? 0) },
    { metric: "Marge nette", v: clamp01((pctFromDecimal(s.net_margin) ?? 0) * 2) },
    { metric: "ROE", v: clamp01((pctFromDecimal(s.roe) ?? 0) * 2) },
    { metric: "Croissance", v: clamp01((pctFromDecimal(s.revenue_growth) ?? 0) * 4) },
    { metric: "Valo P/E", v: inverseMultiple(s.pe_ratio, 20) },
    { metric: "Valo EV/EBITDA", v: inverseMultiple(s.ev_ebitda, 15) },
  ];

  const pointsA = build(a);
  const pointsB = build(b);

  const data = pointsA.map((p, i) => ({
    metric: p.metric,
    [nameA || "A"]: Number(p.v.toFixed(1)),
    [nameB || "B"]: Number(pointsB[i].v.toFixed(1)),
  }));

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="mb-2">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Radar comparatif — 6 dimensions
        </div>
        <div className="text-[10px] text-ink-500 mt-0.5">
          Normalisé 0-100 · plus large = meilleur profil sur cette dimension
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="70%">
            <PolarGrid stroke="#E5E7EB" />
            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fill: "#374151" }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 8, fill: "#9CA3AF" }} />
            <Tooltip contentStyle={{ fontSize: 11 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Radar name={nameA || "A"} dataKey={nameA || "A"} stroke="#1B3A6B" fill="#1B3A6B" fillOpacity={0.25} />
            <Radar name={nameB || "B"} dataKey={nameB || "B"} stroke="#B06000" fill="#B06000" fillOpacity={0.25} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
