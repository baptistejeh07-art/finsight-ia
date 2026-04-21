"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { IndiceSector } from "./types";
import { useI18n } from "@/i18n/provider";

interface Props {
  secteurs: IndiceSector[];
  universe?: string;
}

const COLORS = [
  "#1B2A4A", "#2E4A78", "#3D5C92", "#5673A8", "#7691C2", "#9DAFD4",
  "#C5D0DF", "#A8B5C8", "#8B96AC", "#6E798F",
];

export function IndiceSectorsDonut({ secteurs, universe }: Props) {
  const { t } = useI18n();

  const valid = (secteurs || []).filter((s) => (s.weight || 0) > 0);
  if (valid.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">{t("kpi.no_mktcap_peers")}</span>
      </div>
    );
  }

  const sorted = [...valid].sort((a, b) => (b.weight || 0) - (a.weight || 0));
  const total = sorted.reduce((s, x) => s + (x.weight || 0), 0);

  return (
    <div className="bg-white border border-ink-200 rounded-md px-3 py-3 h-full flex flex-col">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1 text-center">
        {t("kpi.sector_weights") || "Pondération sectorielle"}
        {universe ? ` — ${universe}` : ""}
      </div>
      <div className="flex-1 min-h-[140px] relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={sorted}
              dataKey="weight"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={42}
              outerRadius={72}
              paddingAngle={1}
            >
              {sorted.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number) => `${v.toFixed(1)}%`}
              contentStyle={{ fontSize: 11, background: "#fff", border: "1px solid #e5e5e5", borderRadius: 4 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="text-xs font-semibold text-ink-900">{universe || "Indice"}</div>
          <div className="text-[10px] text-ink-500">{sorted.length} secteurs</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-2 text-[10px]">
        {sorted.slice(0, 8).map((s, i) => {
          const pct = ((s.weight || 0) / total) * 100;
          return (
            <div key={i} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
              <span className="text-ink-700 truncate">
                {s.name} ({pct.toFixed(1)}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
