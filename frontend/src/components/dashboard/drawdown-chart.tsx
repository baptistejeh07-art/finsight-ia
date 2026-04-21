"use client";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import type { StockPoint } from "./types";

/**
 * Drawdown = (prix / plus-haut-précédent) - 1, exprimé en %.
 * Toujours <= 0. L'aire sous la courbe matérialise la chute.
 */
export function DrawdownChart({ history, ticker }: { history: StockPoint[]; ticker: string }) {
  if (!history || history.length < 2) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Historique insuffisant pour drawdown.</span>
      </div>
    );
  }

  const sorted = [...history].sort((a, b) => (a.month < b.month ? -1 : 1));
  let peak = -Infinity;
  const points = sorted.map((p) => {
    if (p.price > peak) peak = p.price;
    const dd = peak > 0 ? (p.price / peak - 1) * 100 : 0;
    return { month: p.month, dd: Number(dd.toFixed(2)) };
  });

  const maxDD = Math.min(...points.map((p) => p.dd));
  const currentDD = points[points.length - 1].dd;

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Drawdown — {ticker}
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">Chute % vs plus-haut glissant</div>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold font-mono text-signal-sell">{maxDD.toFixed(1)} %</div>
          <div className="text-[9px] text-ink-500">Actuel {currentDD.toFixed(1)} %</div>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#A82020" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#A82020" stopOpacity={0.5} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#6B7280" }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} unit="%" width={40} />
            <Tooltip
              formatter={(v: number) => [`${v?.toFixed(2)} %`, "Drawdown"]}
              contentStyle={{ fontSize: 11 }}
            />
            <Area type="monotone" dataKey="dd" stroke="#A82020" strokeWidth={2} fill="url(#ddGradient)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
