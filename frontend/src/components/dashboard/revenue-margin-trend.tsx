"use client";

import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import type { RawData, RatiosData } from "./types";

/**
 * Évolution CA (barres) + Marges EBITDA & Nette (lignes) sur 5 ans.
 * Double axe Y : gauche = CA en devise, droite = marges en %.
 */
export function RevenueMarginTrend({
  rawData,
  ratios,
  currency,
}: {
  rawData: RawData | undefined | null;
  ratios: RatiosData | undefined | null;
  currency?: string;
}) {
  const years = Object.keys(rawData?.years || {}).sort();
  if (years.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Historique indisponible.</span>
      </div>
    );
  }

  const ccy = currency || "USD";
  const fmtRev = (v: number | null | undefined) => {
    if (v == null || !Number.isFinite(v)) return "—";
    if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)} Mds`;
    if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(0)} M`;
    return String(v);
  };

  const data = years.map((y) => {
    const rY = ratios?.years?.[y];
    return {
      year: y,
      revenue: (rawData!.years[y].revenue as number | null) ?? null,
      ebitda_margin: rY?.ebitda_margin != null ? Number((rY.ebitda_margin as number * 100).toFixed(1)) : null,
      net_margin: rY?.net_margin != null ? Number((rY.net_margin as number * 100).toFixed(1)) : null,
    };
  });

  const hasAny = data.some((d) => d.revenue != null || d.ebitda_margin != null);
  if (!hasAny) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Marges et revenus manquants sur toutes les années.</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Évolution CA et marges
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            Barres = CA en {ccy}, lignes = marges EBITDA et nette
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 5, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="year" tick={{ fontSize: 10, fill: "#6B7280" }} />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 10, fill: "#6B7280" }}
              tickFormatter={fmtRev}
              width={55}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 10, fill: "#6B7280" }}
              unit="%"
              width={40}
            />
            <Tooltip
              formatter={(v: number, name: string) => {
                if (name === "Chiffre d'affaires") return [`${fmtRev(v)} ${ccy}`, name];
                return [`${v?.toFixed(1)} %`, name];
              }}
              contentStyle={{ fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar
              yAxisId="left"
              dataKey="revenue"
              name="Chiffre d'affaires"
              fill="#1B3A6B"
              radius={[3, 3, 0, 0]}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="ebitda_margin"
              name="Marge EBITDA"
              stroke="#4A9EDC"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="net_margin"
              name="Marge nette"
              stroke="#B06000"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
