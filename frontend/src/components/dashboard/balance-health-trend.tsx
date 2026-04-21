"use client";

import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, ReferenceLine } from "recharts";
import type { RatiosData } from "./types";

/**
 * Santé bilan simplifiée — trajectoire Net Debt / EBITDA + Altman Z + Current Ratio.
 * Proxy synthétique à défaut d'un vrai bilan ligne à ligne.
 *   - ND/EBITDA : endettement relatif à la génération de cash opérationnel
 *   - Altman Z : score composite du risque de défaillance (Z > 2.99 = sain)
 *   - Current Ratio : liquidité court terme (> 1.5 = confortable)
 */
export function BalanceHealthTrend({ ratios }: { ratios: RatiosData | undefined | null }) {
  const years = Object.keys(ratios?.years || {}).sort();
  if (years.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Historique bilan indisponible.</span>
      </div>
    );
  }

  const data = years.map((y) => {
    const r = ratios!.years[y];
    const val = (v: unknown): number | null => {
      const n = typeof v === "number" ? v : null;
      return n != null && Number.isFinite(n) ? Number(n.toFixed(2)) : null;
    };
    return {
      year: y,
      nd_ebitda: val(r?.net_debt_ebitda),
      altman_z: val(r?.altman_z),
      current: val(r?.current_ratio),
    };
  });

  const hasAny = data.some((d) => d.nd_ebitda != null || d.altman_z != null || d.current != null);
  if (!hasAny) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Ratios de solidité indisponibles.</span>
      </div>
    );
  }

  const last = data[data.length - 1];
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Santé bilan — trajectoire
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            Endettement · risque défaillance · liquidité court terme
          </div>
        </div>
        <div className="text-right text-[10px] text-ink-500 font-mono">
          ND/EBITDA {last.nd_ebitda?.toFixed(1) ?? "—"}x · Z {last.altman_z?.toFixed(1) ?? "—"}
          <br />
          Current {last.current?.toFixed(1) ?? "—"}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 5, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="year" tick={{ fontSize: 10, fill: "#6B7280" }} />
            <YAxis yAxisId="left" tick={{ fontSize: 10, fill: "#6B7280" }} width={35} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: "#6B7280" }} width={35} />
            <ReferenceLine yAxisId="left" y={3} stroke="#A82020" strokeDasharray="3 3" />
            <Tooltip
              formatter={(v: number, name: string) => {
                if (name === "ND/EBITDA") return [v != null ? `${v.toFixed(2)}x` : "—", name];
                return [v != null ? v.toFixed(2) : "—", name];
              }}
              contentStyle={{ fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar yAxisId="left" dataKey="nd_ebitda" name="ND/EBITDA" fill="#1B3A6B" radius={[3, 3, 0, 0]} />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="altman_z"
              name="Altman Z"
              stroke="#4A9EDC"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="current"
              name="Current Ratio"
              stroke="#B06000"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
