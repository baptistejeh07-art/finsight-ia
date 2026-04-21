"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import type { SectorTicker } from "./types";

/**
 * Top 5 / Bottom 5 performers sur momentum 52 semaines.
 * Permet d'isoler les leaders (rotation active) et les retardataires (value ?) du secteur.
 */
export function SectorMomentumLeaders({
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

  const rows = tickers
    .map((t) => {
      let m = (t.ratios?.momentum_52w ?? t.ratios?.mom_52w ?? t.ratios?.ret_52w) as number | null | undefined;
      if (m == null || !Number.isFinite(m)) return null;
      if (Math.abs(m) < 2) m = m * 100; // décimal
      return { ticker: t.ticker || t.name || "?", name: t.name || "", momentum: Number(m.toFixed(1)) };
    })
    .filter((r): r is NonNullable<typeof r> => r != null);

  if (rows.length < 3) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Momentum 52 semaines indisponible.</span>
      </div>
    );
  }

  const sorted = [...rows].sort((a, b) => b.momentum - a.momentum);
  const n = Math.min(5, Math.floor(sorted.length / 2));
  const top = sorted.slice(0, n);
  const bot = sorted.slice(-n).reverse();

  const data = [
    ...top.map((r) => ({ ...r, kind: "top" as const })),
    ...bot.map((r) => ({ ...r, kind: "bot" as const })),
  ];

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Leaders et retardataires{label ? ` — ${label}` : ""}
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            Top {n} et bottom {n} sur momentum 52 semaines
          </div>
        </div>
        <div className="text-right text-[10px] text-ink-500 font-mono">
          {rows.length} tickers classés
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#6B7280" }} unit="%" />
            <YAxis type="category" dataKey="ticker" tick={{ fontSize: 10, fill: "#1F2937" }} width={60} />
            <Tooltip
              formatter={(v: number) => [`${v.toFixed(1)} %`, "Momentum 52S"]}
              contentStyle={{ fontSize: 11 }}
            />
            <Bar dataKey="momentum" radius={[0, 3, 3, 0]}>
              {data.map((d, i) => (
                <Cell key={`cell-${i}`} fill={d.momentum >= 0 ? "#3A8A3A" : "#A82020"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
