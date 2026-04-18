"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import type { YearData, YearRatios } from "./types";

interface Props {
  years: Record<string, YearData>;
  ratios?: Record<string, YearRatios>;
  currency: string;
}

export function CapexFcfChart({ years, ratios }: Props) {
  // Build data for last 4 years
  const allYears = Object.keys(years).sort();
  const recent = allYears.slice(-4);

  const data = recent.map((y) => {
    const yd: YearData = (years[y] as YearData) || ({} as YearData);
    const yr: YearRatios = (ratios?.[y] as YearRatios) || ({} as YearRatios);
    const capex = Math.abs(Number(yd.capex ?? 0));
    const dividends = Math.abs(
      Number(yr.dividends_paid_abs ?? yd.dividends ?? 0)
    );
    return {
      year: y,
      "CapEx (Mds)": capex / 1000,
      "Div. versés (Mds)": dividends / 1000,
    };
  });

  if (data.every((d) => d["CapEx (Mds)"] === 0 && d["Div. versés (Mds)"] === 0)) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-[260px] flex items-center justify-center">
        <span className="text-xs text-ink-400">Pas de données CapEx / Dividendes</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
        Capital alloué — CapEx vs Dividendes
      </div>
      <div className="h-[180px]">
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
            <Bar dataKey="CapEx (Mds)" fill="#1B2A4A" maxBarSize={32} />
            <Bar dataKey="Div. versés (Mds)" fill="#4A8C5C" maxBarSize={32} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
