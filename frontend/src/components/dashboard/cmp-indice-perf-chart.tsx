"use client";

/**
 * Graphique interactif de comparaison de 2 indices (base 100).
 * Source : data.perf_history = { dates: string[], indice_a: number[], indice_b: number[] }
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";

interface PerfHistory {
  dates: string[];
  indice_a: number[];
  indice_b: number[];
}

interface Props {
  perfHistory: PerfHistory | null | undefined;
  nameA: string;
  nameB: string;
}

export function CmpIndicePerfChart({ perfHistory, nameA, nameB }: Props) {
  if (
    !perfHistory ||
    !perfHistory.dates ||
    !perfHistory.indice_a ||
    !perfHistory.indice_b ||
    perfHistory.dates.length === 0
  ) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">Historique de performance indisponible</span>
      </div>
    );
  }

  const data = perfHistory.dates.map((d, i) => ({
    date: d,
    [nameA]: perfHistory.indice_a[i],
    [nameB]: perfHistory.indice_b[i],
  }));

  // Perf finale pour titre
  const lastA = perfHistory.indice_a[perfHistory.indice_a.length - 1] ?? 100;
  const lastB = perfHistory.indice_b[perfHistory.indice_b.length - 1] ?? 100;
  const perfA = lastA - 100;
  const perfB = lastB - 100;

  const fmtPerf = (v: number) =>
    `${v >= 0 ? "+" : ""}${v.toFixed(1).replace(".", ",")} %`;

  return (
    <div className="bg-white border border-ink-200 rounded-md px-3 py-3 h-full flex flex-col">
      <div className="flex items-baseline justify-between mb-2 px-1">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Performance comparée (base 100) — 1 an
        </div>
        <div className="text-[10px] font-mono text-ink-600">
          <span className={perfA >= 0 ? "text-signal-buy" : "text-signal-sell"}>
            {nameA} {fmtPerf(perfA)}
          </span>
          <span className="mx-2 text-ink-400">·</span>
          <span className={perfB >= 0 ? "text-signal-buy" : "text-signal-sell"}>
            {nameB} {fmtPerf(perfB)}
          </span>
        </div>
      </div>
      <div className="flex-1 min-h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#888" }}
              minTickGap={40}
              tickFormatter={(d: string) => {
                const parts = (d || "").split("-");
                return parts.length >= 3 ? `${parts[2]}/${parts[1]}` : d;
              }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#888" }}
              domain={["dataMin - 2", "dataMax + 2"]}
            />
            <Tooltip
              contentStyle={{
                fontSize: 11,
                background: "#fff",
                border: "1px solid #e5e5e5",
                borderRadius: 4,
              }}
              labelStyle={{ color: "#111" }}
              formatter={(v: number) => v.toFixed(1)}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line
              type="monotone"
              dataKey={nameA}
              stroke="#1B2A4A"
              strokeWidth={2.2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey={nameB}
              stroke="#5B8BBF"
              strokeWidth={2}
              strokeDasharray="4 3"
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
