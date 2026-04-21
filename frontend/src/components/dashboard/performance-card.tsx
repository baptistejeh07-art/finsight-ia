"use client";

import { useEffect, useMemo, useState } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "";

type Period = "1d" | "5d" | "1mo" | "3mo" | "6mo" | "ytd" | "1y" | "3y" | "5y";

const PERIODS: { value: Period; label: string }[] = [
  { value: "1d",  label: "1J" },
  { value: "5d",  label: "5J" },
  { value: "1mo", label: "1M" },
  { value: "3mo", label: "3M" },
  { value: "6mo", label: "6M" },
  { value: "ytd", label: "YTD" },
  { value: "1y",  label: "1A" },
  { value: "3y",  label: "3A" },
  { value: "5y",  label: "5A" },
];

interface PeriodStats {
  change_pct: number | null;
  high: number | null;
  low: number | null;
  volatility_ann: number | null;
  volume_avg: number | null;
  points: number;
}

interface PerformanceData {
  ticker: string;
  current_price: number | null;
  periods: Record<Period, PeriodStats>;
}

interface SeriesPoint {
  date: string;
  close: number;
}

interface PerformanceCardProps {
  ticker: string;
  currency?: string;
  sector?: string;
}

interface MultiSeriesResponse {
  series: {
    main?: { name: string; ticker: string; points: Array<{ date: string; close: number; base100?: number }> };
    index?: { name: string; ticker: string; points: Array<{ date: string; close: number; base100?: number }> };
    sector?: { name: string; ticker: string; points: Array<{ date: string; close: number; base100?: number }> };
  };
}

export function PerformanceCard({ ticker, currency = "EUR", sector = "" }: PerformanceCardProps) {
  const [period, setPeriod] = useState<Period>("1mo");
  const [perf, setPerf] = useState<PerformanceData | null>(null);
  const [multi, setMulti] = useState<MultiSeriesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    fetch(`${API}/market/performance/${encodeURIComponent(ticker)}`)
      .then((r) => r.ok ? r.json() : null)
      .then((j) => { if (!cancel && j && !j.error) setPerf(j as PerformanceData); })
      .finally(() => { if (!cancel) setLoading(false); });
    return () => { cancel = true; };
  }, [ticker]);

  useEffect(() => {
    let cancel = false;
    const url = `${API}/market/series-multi/${encodeURIComponent(ticker)}?period=${period}&sector=${encodeURIComponent(sector)}`;
    fetch(url)
      .then((r) => r.ok ? r.json() : null)
      .then((j) => { if (!cancel && j?.series) setMulti(j as MultiSeriesResponse); })
      .catch(() => {});
    return () => { cancel = true; };
  }, [ticker, period, sector]);

  const stats = perf?.periods?.[period];
  const positive = (stats?.change_pct ?? 0) >= 0;

  // Assemble les 3 séries (main + index + sector) avec base100 par date
  const chartData = useMemo(() => {
    if (!multi?.series) return [];
    const { main, index, sector: secSeries } = multi.series;
    if (!main?.points?.length) return [];
    const byDate: Record<string, { date: string; main?: number; index?: number; sector?: number }> = {};
    for (const p of main.points) byDate[p.date] = { date: p.date, main: p.base100 ?? p.close };
    if (index?.points) for (const p of index.points) (byDate[p.date] ||= { date: p.date }).index = p.base100 ?? p.close;
    if (secSeries?.points) for (const p of secSeries.points) (byDate[p.date] ||= { date: p.date }).sector = p.base100 ?? p.close;
    return Object.values(byDate).sort((a, b) => (a.date > b.date ? 1 : -1));
  }, [multi]);
  const lineColor = positive ? "#16a34a" : "#dc2626";
  const indexName = multi?.series?.index?.name;
  const sectorName = multi?.series?.sector?.name;

  if (loading && !perf) {
    return (
      <div className="h-full bg-white border border-ink-200 rounded-md p-4 text-xs text-ink-500">
        Chargement performance…
      </div>
    );
  }

  return (
    <div className="h-full bg-white border border-ink-200 rounded-md flex flex-col">
      <div className="px-4 pt-3 pb-2 border-b border-ink-100 flex items-start justify-between gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-[1.5px] text-ink-500 font-semibold">
            Performance comparée
          </div>
          <div className="text-sm font-semibold text-ink-900 mt-0.5">{ticker}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-ink-500">Cours</div>
          <div className="text-sm font-mono text-ink-900 font-semibold">
            {perf?.current_price ? `${perf.current_price.toFixed(2)} ${currency}` : "—"}
          </div>
        </div>
      </div>

      {/* Sélecteur période */}
      <div className="px-3 py-2 border-b border-ink-100 flex flex-wrap gap-1">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => setPeriod(p.value)}
            className={
              "px-2 py-1 rounded text-[11px] font-semibold transition-colors " +
              (period === p.value
                ? "bg-navy-500 text-white"
                : "bg-ink-50 text-ink-700 hover:bg-ink-100")
            }
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Graph */}
      <div className="flex-1 min-h-[120px] px-3 pt-3">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis domain={["dataMin - 2", "dataMax + 2"]} hide />
              <Line
                type="monotone" dataKey="main" name={ticker}
                stroke={lineColor} strokeWidth={2.2} dot={false} isAnimationActive={false}
              />
              {indexName && (
                <Line
                  type="monotone" dataKey="index" name={indexName}
                  stroke="#6b7280" strokeWidth={1.2} strokeDasharray="4 4" dot={false} isAnimationActive={false}
                />
              )}
              {sectorName && (
                <Line
                  type="monotone" dataKey="sector" name={sectorName}
                  stroke="#a855f7" strokeWidth={1.2} strokeDasharray="2 2" dot={false} isAnimationActive={false}
                />
              )}
              <Tooltip
                contentStyle={{ fontSize: 11, borderRadius: 4, border: "1px solid #ddd" }}
                formatter={(v: number) => [v.toFixed(1), ""]}
                labelFormatter={(l) => String(l)}
              />
              <Legend iconType="plainline" wrapperStyle={{ fontSize: 10, paddingTop: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[140px] flex items-center justify-center text-xs text-ink-400">
            Chargement du graphique…
          </div>
        )}
      </div>

      {/* Stats ligne */}
      <div className="px-4 py-3 border-t border-ink-100 grid grid-cols-4 gap-2 text-xs">
        <Stat
          label="Perf"
          value={stats?.change_pct != null ? `${stats.change_pct >= 0 ? "+" : ""}${stats.change_pct.toFixed(2)}%` : "—"}
          icon={positive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          color={positive ? "text-signal-buy" : "text-signal-sell"}
        />
        <Stat
          label="Plus haut"
          value={stats?.high ? `${stats.high.toFixed(2)}` : "—"}
        />
        <Stat
          label="Plus bas"
          value={stats?.low ? `${stats.low.toFixed(2)}` : "—"}
        />
        <Stat
          label="Volatilité"
          value={stats?.volatility_ann ? `${stats.volatility_ann.toFixed(1)}%` : "—"}
        />
      </div>
    </div>
  );
}

function Stat({ label, value, icon, color }: {
  label: string; value: string; icon?: React.ReactNode; color?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[9px] uppercase tracking-wider text-ink-500">{label}</div>
      <div className={`flex items-center gap-1 font-mono font-semibold truncate ${color || "text-ink-900"}`}>
        {icon}{value}
      </div>
    </div>
  );
}
