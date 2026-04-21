"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

/**
 * Performance comparée de l'indice vs S&P 500, Obligations US 10Y, Or — base 100 sur ~12 mois.
 * Lit la clé perf_history injectée par cli_analyze (dates + 4 séries rebasées).
 */
interface PerfHistory {
  dates?: string[];
  indice?: number[];
  sp500?: number[];
  bonds?: number[];
  gold?: number[];
  indice_name?: string;
}

export function IndicePerfBenchmark({
  perfHistory,
  universe,
}: {
  perfHistory: PerfHistory | null | undefined;
  universe?: string;
}) {
  if (!perfHistory?.dates || perfHistory.dates.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Historique de performance indisponible.</span>
      </div>
    );
  }

  const dates = perfHistory.dates;
  const n = dates.length;
  const short = (s: string) => {
    const parts = s.split("-");
    if (parts.length >= 2) return `${parts[0].slice(2)}/${parts[1]}`;
    return s.slice(0, 5);
  };

  const data = dates.map((d, i) => ({
    date: short(d),
    indice: perfHistory.indice?.[i] ?? null,
    sp500: perfHistory.sp500?.[i] ?? null,
    bonds: perfHistory.bonds?.[i] ?? null,
    gold: perfHistory.gold?.[i] ?? null,
  }));

  const last = data[n - 1];
  const name = perfHistory.indice_name || universe || "Indice";

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Performance comparée — base 100
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            {name} vs S&P 500 vs Obligations US 10Y vs Or sur ~12 mois
          </div>
        </div>
        <div className="text-right text-[10px] text-ink-500 font-mono">
          {name} {last.indice?.toFixed(1) ?? "—"}
          <br />
          SPX {last.sp500?.toFixed(1) ?? "—"} · Gold {last.gold?.toFixed(1) ?? "—"}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#6B7280" }}
              interval={Math.max(1, Math.floor(n / 8))}
            />
            <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} width={40} />
            <Tooltip
              formatter={(v: number, name: string) => [v != null ? v.toFixed(1) : "—", name]}
              contentStyle={{ fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="indice" name={name} stroke="#1B3A6B" strokeWidth={2.5} dot={false} connectNulls />
            <Line type="monotone" dataKey="sp500" name="S&P 500" stroke="#4A9EDC" strokeWidth={1.5} strokeDasharray="4 4" dot={false} connectNulls />
            <Line type="monotone" dataKey="bonds" name="US 10Y" stroke="#6B7280" strokeWidth={1.2} strokeDasharray="2 3" dot={false} connectNulls />
            <Line type="monotone" dataKey="gold" name="Or" stroke="#B06000" strokeWidth={1.5} strokeDasharray="6 3" dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
