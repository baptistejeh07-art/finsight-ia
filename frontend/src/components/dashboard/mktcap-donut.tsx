"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { PeerData } from "./types";

interface Props {
  peers: PeerData[];
  targetTicker: string;
  targetName: string;
  targetMarketCapMds: number | null;
  sectorLabel: string;
}

const COLORS = ["#1B2A4A", "#3A5288", "#5A7AB5", "#8AAEDB", "#B8D2EB", "#C4D5E8"];

export function MktCapDonut({ peers, targetTicker, targetName, targetMarketCapMds, sectorLabel }: Props) {
  const cibleMc = targetMarketCapMds ?? 0;
  const items = [
    { name: targetTicker || targetName, value: cibleMc, isTarget: true },
    ...peers
      .filter((p) => (p.market_cap_mds ?? 0) > 0)
      .map((p) => ({ name: p.ticker || p.name, value: p.market_cap_mds || 0, isTarget: false })),
  ];

  const total = items.reduce((s, i) => s + i.value, 0);
  if (total === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-[260px] flex items-center justify-center">
        <span className="text-xs text-ink-400">Pas de données market cap peers</span>
      </div>
    );
  }

  const targetPct = (cibleMc / total) * 100;

  return (
    <div className="bg-white border border-ink-200 rounded-md px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1 text-center">
        Poids relatif Mkt Cap — {sectorLabel}
      </div>
      <div className="h-[150px] relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={items}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={38}
              outerRadius={64}
              paddingAngle={1}
            >
              {items.map((entry, i) => (
                <Cell key={i} fill={entry.isTarget ? "#1B2A4A" : COLORS[(i % (COLORS.length - 1)) + 1]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number) => `${(v).toFixed(0)} Mds`}
              contentStyle={{ fontSize: 11, background: "#fff", border: "1px solid #e5e5e5", borderRadius: 4 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="text-xs text-ink-500">{targetTicker}</div>
          <div className="text-base font-bold text-ink-900 font-mono">
            {targetPct.toFixed(0)} %
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-2 text-[10px]">
        {items.map((item, i) => {
          const pct = (item.value / total) * 100;
          const color = item.isTarget ? "#1B2A4A" : COLORS[(i % (COLORS.length - 1)) + 1];
          return (
            <div key={i} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: color }} />
              <span className={item.isTarget ? "font-semibold text-ink-900" : "text-ink-600"}>
                {item.name} ({pct.toFixed(0)}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
