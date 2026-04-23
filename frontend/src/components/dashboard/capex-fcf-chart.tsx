"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import type { YearData, YearRatios } from "./types";
import { useI18n } from "@/i18n/provider";

interface Props {
  years: Record<string, YearData>;
  ratios?: Record<string, YearRatios>;
  currency: string;
}

export function CapexFcfChart({ years, ratios }: Props) {
  const { t } = useI18n();
  const capexLabel = t("kpi.capex_short");
  const divLabel = t("kpi.dividends_short");

  const allYears = Object.keys(years).sort();
  const recent = allYears.slice(-4);

  const rawData = recent.map((y) => {
    const yd: YearData = (years[y] as YearData) || ({} as YearData);
    const yr: YearRatios = (ratios?.[y] as YearRatios) || ({} as YearRatios);
    const capex = Math.abs(Number(yd.capex ?? 0));
    const dividends = Math.abs(
      Number(yr.dividends_paid_abs ?? yd.dividends ?? 0)
    );
    return {
      year: y,
      [capexLabel]: capex / 1000,
      [divLabel]: dividends / 1000,
    };
  });

  // Masque les années où CapEx ET Dividendes sont à 0 (colonne vide → graphique déséquilibré)
  const data = rawData.filter(
    (d) => Number(d[capexLabel]) > 0 || Number(d[divLabel]) > 0
  );

  if (data.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">{t("kpi.no_capex_div_data")}</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md px-3 py-3 h-full flex flex-col">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
        {t("kpi.capital_allocated")}
      </div>
      <div className="flex-1 min-h-[140px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="year" tick={{ fontSize: 10, fill: "#888" }} />
            <YAxis tick={{ fontSize: 10, fill: "#888" }} />
            <Tooltip
              contentStyle={{
                fontSize: 11,
                background: "#fff",
                border: "1px solid #e5e5e5",
                borderRadius: 4,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey={capexLabel} fill="#1B2A4A" maxBarSize={32} />
            <Bar dataKey={divLabel} fill="#4A8C5C" maxBarSize={32} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
