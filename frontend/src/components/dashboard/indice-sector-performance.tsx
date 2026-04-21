"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, ReferenceLine } from "recharts";
import type { IndiceSector } from "./types";

/**
 * Performance des secteurs de l'indice, triée décroissante.
 * Couleur : vert si positif, rouge si négatif. Ligne de référence à 0.
 */
export function IndiceSectorPerformance({
  secteurs,
  universe,
}: {
  secteurs: IndiceSector[] | undefined | null;
  universe?: string;
}) {
  if (!secteurs || secteurs.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Répartition sectorielle indisponible.</span>
      </div>
    );
  }

  const rows = secteurs
    .filter((s) => s.name && s.performance != null && Number.isFinite(s.performance as number))
    .map((s) => {
      let p = s.performance as number;
      if (Math.abs(p) < 2) p = p * 100;
      return { name: s.name as string, perf: Number(p.toFixed(1)), weight: s.weight ?? null };
    })
    .sort((a, b) => b.perf - a.perf);

  if (rows.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Performances sectorielles non disponibles.</span>
      </div>
    );
  }

  const best = rows[0];
  const worst = rows[rows.length - 1];
  const spread = best.perf - worst.perf;

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Performance sectorielle{universe ? ` — ${universe}` : ""}
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">Tri décroissant · dispersion visible en coup d&apos;œil</div>
        </div>
        <div className="text-right text-[10px] text-ink-500 font-mono">
          {best.name} {best.perf >= 0 ? "+" : ""}{best.perf.toFixed(1)} %
          <br />
          Spread {spread.toFixed(1)} pts
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 5, right: 40, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#6B7280" }} unit="%" />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#1F2937" }} width={130} />
            <ReferenceLine x={0} stroke="#6B7280" />
            <Tooltip
              formatter={(v: number) => [`${v > 0 ? "+" : ""}${v.toFixed(1)} %`, "Performance"]}
              contentStyle={{ fontSize: 11 }}
            />
            <Bar dataKey="perf" radius={[0, 3, 3, 0]}>
              {rows.map((r, i) => (
                <Cell key={`cell-${i}`} fill={r.perf >= 0 ? "#3A8A3A" : "#A82020"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
