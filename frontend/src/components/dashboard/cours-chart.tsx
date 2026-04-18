"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import type { StockPoint } from "./types";

export function CoursChart({
  ticker,
  history,
}: {
  ticker: string;
  history: StockPoint[];
}) {
  if (!history || history.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-[260px] flex items-center justify-center">
        <span className="text-xs text-ink-400">Pas d&apos;historique disponible</span>
      </div>
    );
  }

  // Base 100 sur le 1er point
  const base = history[0].price || 1;
  const data = history.map((p) => ({
    month: p.month,
    [ticker]: Math.round((p.price / base) * 1000) / 10,
  }));

  const last = history[history.length - 1].price;
  const perf = ((last - base) / base) * 100;
  const perfStr = `${perf >= 0 ? "+" : ""}${perf.toFixed(1).replace(".", ",")} %`;
  const perfColor = perf >= 0 ? "text-signal-buy" : "text-signal-sell";

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Cours sur 12 mois (base 100)
        </div>
        <div className={`text-sm font-semibold ${perfColor}`}>{perfStr}</div>
      </div>
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#888" }} />
            <YAxis tick={{ fontSize: 10, fill: "#888" }} />
            <Tooltip
              contentStyle={{
                fontSize: 11,
                background: "#fff",
                border: "1px solid #e5e5e5",
                borderRadius: 4,
              }}
              labelStyle={{ color: "#111" }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line
              type="monotone"
              dataKey={ticker}
              stroke="#1B2A4A"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
