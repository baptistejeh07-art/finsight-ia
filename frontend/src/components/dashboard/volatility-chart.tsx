"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import type { StockPoint } from "./types";

/**
 * Volatilité annualisée glissante 30 jours.
 * stock_history est agrégé mensuel (points {month, price}) — on calcule un std
 * des rendements mensuels sur fenêtre 6m et annualise via √12.
 * Limité car pas de daily prices, mais donne un signal directionnel.
 */
export function VolatilityChart({ history, ticker }: { history: StockPoint[]; ticker: string }) {
  if (!history || history.length < 4) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Historique insuffisant pour volatilité.</span>
      </div>
    );
  }

  const sorted = [...history].sort((a, b) => (a.month < b.month ? -1 : 1));
  const returns: number[] = [];
  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1].price;
    const cur = sorted[i].price;
    if (prev > 0 && Number.isFinite(prev) && Number.isFinite(cur)) {
      returns.push(Math.log(cur / prev));
    } else {
      returns.push(0);
    }
  }

  const window = 6;
  const points: { month: string; vol: number | null }[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i < window) {
      points.push({ month: sorted[i].month, vol: null });
      continue;
    }
    const slice = returns.slice(i - window, i);
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / slice.length;
    const vol = Math.sqrt(variance * 12) * 100;
    points.push({ month: sorted[i].month, vol: Number(vol.toFixed(1)) });
  }

  const valid = points.map((p) => p.vol).filter((v): v is number => v != null);
  const last = valid[valid.length - 1];
  const avg = valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : 0;

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Volatilité annualisée — {ticker}
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">Fenêtre glissante 6 mois (annualisée √12)</div>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold font-mono text-ink-900">{last?.toFixed(1) ?? "—"} %</div>
          <div className="text-[9px] text-ink-500">Moyenne {avg.toFixed(1)} %</div>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#6B7280" }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} unit="%" width={40} />
            <Tooltip
              formatter={(v: number) => [`${v?.toFixed(1)} %`, "Volatilité"]}
              contentStyle={{ fontSize: 11 }}
            />
            <Line
              type="monotone"
              dataKey="vol"
              stroke="#1B3A6B"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
