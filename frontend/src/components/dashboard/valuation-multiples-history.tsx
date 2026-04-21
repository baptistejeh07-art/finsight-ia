"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import type { RatiosData } from "./types";

/**
 * Évolution des multiples de valorisation sur N exercices.
 * P/E + EV/EBITDA + EV/Revenue — utile pour détecter une expansion ou
 * contraction des multiples vs fondamentaux.
 */
export function ValuationMultiplesHistory({ ratios }: { ratios: RatiosData | undefined | null }) {
  const years = Object.keys(ratios?.years || {}).sort();
  if (years.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Historique des ratios indisponible.</span>
      </div>
    );
  }

  const data = years.map((y) => {
    const r = ratios!.years[y];
    const clamp = (v: unknown): number | null => {
      const n = typeof v === "number" ? v : null;
      if (n == null || !Number.isFinite(n) || n <= 0 || n > 200) return null;
      return Number(n.toFixed(1));
    };
    return {
      year: y,
      pe: clamp(r?.pe_ratio),
      ev_ebitda: clamp(r?.ev_ebitda),
      ev_rev: clamp(r?.ev_revenue),
    };
  });

  const hasAny = data.some((d) => d.pe != null || d.ev_ebitda != null || d.ev_rev != null);
  if (!hasAny) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Multiples indisponibles sur la période.</span>
      </div>
    );
  }

  const last = data[data.length - 1];
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Multiples de valorisation — historique
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            Expansion ou contraction des multiples vs fondamentaux
          </div>
        </div>
        <div className="text-right text-[10px] text-ink-500 font-mono">
          P/E {last.pe?.toFixed(1) ?? "—"}x · EV/EBITDA {last.ev_ebitda?.toFixed(1) ?? "—"}x
          <br />
          EV/Rev {last.ev_rev?.toFixed(1) ?? "—"}x
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="year" tick={{ fontSize: 10, fill: "#6B7280" }} />
            <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} unit="x" width={40} />
            <Tooltip
              formatter={(v: number, name: string) => [v != null ? `${v.toFixed(1)}x` : "—", name]}
              contentStyle={{ fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line
              type="monotone"
              dataKey="pe"
              name="P/E"
              stroke="#1B3A6B"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="ev_ebitda"
              name="EV/EBITDA"
              stroke="#4A9EDC"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="ev_rev"
              name="EV/Revenue"
              stroke="#B06000"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
