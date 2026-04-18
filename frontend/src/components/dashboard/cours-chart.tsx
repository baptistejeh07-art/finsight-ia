"use client";

import { useEffect, useState } from "react";
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
import type { StockPoint } from "./types";

// Mapping secteur → ETF de référence (Yahoo symbols)
const SECTOR_ETF: Record<string, string> = {
  Technology: "XLK",
  "Communication Services": "XLC",
  "Financial Services": "XLF",
  Financial: "XLF",
  Healthcare: "XLV",
  "Consumer Cyclical": "XLY",
  "Consumer Defensive": "XLP",
  Energy: "XLE",
  Industrials: "XLI",
  "Basic Materials": "XLB",
  "Real Estate": "XLRE",
  Utilities: "XLU",
};

interface ChartPoint {
  month: string;
  [k: string]: number | string;
}

async function fetchSeries(symbol: string): Promise<{ month: string; price: number }[]> {
  try {
    const r = await fetch(
      `/api/market-series/${encodeURIComponent(symbol)}?range=1y&interval=1mo`
    );
    if (!r.ok) return [];
    const data = await r.json();
    return data.points || [];
  } catch {
    return [];
  }
}

export function CoursChart({
  ticker,
  history,
  sector,
}: {
  ticker: string;
  history: StockPoint[];
  sector?: string;
}) {
  const etf = sector ? SECTOR_ETF[sector] : null;
  const [series, setSeries] = useState<{
    target: { month: string; price: number }[];
    sp500: { month: string; price: number }[];
    etf: { month: string; price: number }[];
  }>({ target: [], sp500: [], etf: [] });

  useEffect(() => {
    (async () => {
      // Fetch les 3 séries depuis la même API → format de mois IDENTIQUE
      const [target, sp500, etfData] = await Promise.all([
        fetchSeries(ticker),
        fetchSeries("^GSPC"),
        etf ? fetchSeries(etf) : Promise.resolve([]),
      ]);
      setSeries({ target, sp500, etf: etfData });
    })();
  }, [ticker, etf]);

  // Fallback : si /api/market-series ne renvoie rien pour le ticker target,
  // utiliser le history Python (mais format de mois peut différer)
  const targetSerie = series.target.length > 0 ? series.target : history;

  if (!targetSerie || targetSerie.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-[260px] flex items-center justify-center">
        <span className="text-xs text-ink-400">Pas d&apos;historique disponible</span>
      </div>
    );
  }

  // Normalisation base 100 pour chaque série
  const normalize = (pts: { month: string; price: number }[]) => {
    if (!pts.length) return new Map<string, number>();
    const base = pts[0].price || 1;
    return new Map(pts.map((p) => [p.month, Math.round((p.price / base) * 1000) / 10]));
  };

  const targetMap = normalize(targetSerie);
  const spMap = normalize(series.sp500);
  const etfMap = normalize(series.etf);

  // Axe = union des mois de toutes les séries (préserve l'ordre)
  const allMonths: string[] = [];
  const seen = new Set<string>();
  const collect = (arr: { month: string }[]) => {
    arr.forEach((p) => {
      if (!seen.has(p.month)) {
        seen.add(p.month);
        allMonths.push(p.month);
      }
    });
  };
  collect(targetSerie);
  collect(series.sp500);
  collect(series.etf);

  const data: ChartPoint[] = allMonths.map((m) => {
    const point: ChartPoint = { month: m };
    const t = targetMap.get(m);
    if (t !== undefined) point[ticker] = t;
    const sp = spMap.get(m);
    if (sp !== undefined) point["S&P 500"] = sp;
    const e = etfMap.get(m);
    if (e !== undefined && etf) point[etf] = e;
    return point;
  });

  const last = targetSerie[targetSerie.length - 1].price;
  const first = targetSerie[0].price || 1;
  const perf = ((last - first) / first) * 100;
  const perfStr = `${perf >= 0 ? "+" : ""}${perf.toFixed(1).replace(".", ",")} %`;
  const perfColor = perf >= 0 ? "text-signal-buy" : "text-signal-sell";

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Performance comparée — 12 mois
        </div>
        <div className={`text-sm font-semibold ${perfColor}`}>{perfStr}</div>
      </div>
      <div className="h-[220px]">
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
              strokeWidth={2.2}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="S&P 500"
              stroke="#888"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              connectNulls
            />
            {etf && (
              <Line
                type="monotone"
                dataKey={etf}
                stroke="#5B8BBF"
                strokeWidth={1.5}
                strokeDasharray="2 2"
                dot={false}
                connectNulls
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
