"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { SectorTicker } from "./types";
import { useI18n } from "@/i18n/provider";

interface Props {
  tickers: SectorTicker[];
  sectorLabel?: string;
  /** Centre du donut : ex. "Santé" / "Market Cap" */
  centerLabel?: string;
}

const COLORS = ["#1B2A4A", "#2E4A78", "#3D5C92", "#5673A8", "#7691C2", "#9DAFD4"];

export function SectorMktCapDonut({ tickers, sectorLabel, centerLabel }: Props) {
  const { t, locale } = useI18n();
  const unit = locale === "fr" ? "Md" : "B";

  const valid = (tickers || []).filter((x) => (x.market_cap || 0) > 0);
  if (valid.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">{t("kpi.no_mktcap_peers")}</span>
      </div>
    );
  }

  const sorted = [...valid].sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
  const top = sorted.slice(0, 5);
  const rest = sorted.slice(5);
  const restMc = rest.reduce((s, x) => s + (x.market_cap || 0), 0);
  const items = top.map((x) => ({
    name: x.name || x.ticker || "?",
    ticker: x.ticker || "?",
    value: (x.market_cap || 0) / 1_000_000_000,
  }));
  if (restMc > 0) {
    items.push({
      name: t("kpi.others") || "Autres",
      ticker: "—",
      value: restMc / 1_000_000_000,
    });
  }

  const total = items.reduce((s, i) => s + i.value, 0);

  return (
    <div className="bg-white border border-ink-200 rounded-md px-3 py-3 h-full flex flex-col">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1 text-center">
        {t("kpi.mktcap_distribution") || "Répartition Market Cap"}
        {sectorLabel ? ` — ${sectorLabel}` : ""}
      </div>
      <div className="flex-1 min-h-[140px] relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={items}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={42}
              outerRadius={72}
              paddingAngle={1}
            >
              {items.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v: number) => `${v.toFixed(1)} ${unit}`}
              contentStyle={{ fontSize: 11, background: "#fff", border: "1px solid #e5e5e5", borderRadius: 4 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          {centerLabel ? (
            <>
              <div className="text-xs font-semibold text-ink-900">{centerLabel}</div>
              <div className="text-[10px] text-ink-500">Market Cap</div>
            </>
          ) : (
            <div className="text-base font-bold text-ink-900 font-mono">
              {total.toFixed(0)} {unit}
            </div>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-2 text-[10px]">
        {items.map((item, i) => {
          const pct = (item.value / total) * 100;
          return (
            <div key={i} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
              <span className="text-ink-700 truncate">
                {item.ticker !== "—" ? item.ticker : item.name} ({pct.toFixed(1)}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
