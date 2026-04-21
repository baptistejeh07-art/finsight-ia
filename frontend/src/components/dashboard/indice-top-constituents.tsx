"use client";

/**
 * Top 10 constituants d'un indice (tri market cap desc).
 * Source : result.data.tickers (array SectorTicker).
 */

import type { SectorTicker } from "./types";

interface Props {
  tickers: SectorTicker[] | undefined;
  label?: string;
  limit?: number;
}

function fmtMcap(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return "—";
  const b = v / 1_000_000_000;
  if (b >= 1000) return `${(b / 1000).toFixed(1).replace(".", ",")} T`;
  if (b >= 1) return `${b.toFixed(1).replace(".", ",")} Md`;
  return `${(v / 1_000_000).toFixed(0)} M`;
}

export function IndiceTopConstituents({ tickers, label, limit = 10 }: Props) {
  if (!tickers || tickers.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">Aucun constituant disponible</span>
      </div>
    );
  }

  const sorted = [...tickers]
    .filter((t) => (t.market_cap || 0) > 0)
    .sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0))
    .slice(0, limit);

  const totalAll = tickers.reduce((s, t) => s + (t.market_cap || 0), 0) || 1;

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden h-full flex flex-col">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Top {limit} constituants{label ? ` — ${label}` : ""}
        </div>
      </div>
      <div className="overflow-auto flex-1">
        <table className="w-full text-[11px]">
          <thead className="bg-ink-50 text-ink-600 sticky top-0">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold">Rang</th>
              <th className="text-left px-2 py-1.5 font-semibold">Ticker</th>
              <th className="text-left px-2 py-1.5 font-semibold">Société</th>
              <th className="text-right px-2 py-1.5 font-semibold">Mkt Cap</th>
              <th className="text-right px-2 py-1.5 font-semibold">Poids</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => {
              const weight = ((t.market_cap || 0) / totalAll) * 100;
              return (
                <tr key={`${t.ticker}-${i}`} className="border-t border-ink-100">
                  <td className="px-3 py-1.5 font-mono text-ink-500">{i + 1}</td>
                  <td className="px-2 py-1.5 font-mono font-semibold text-ink-900">{t.ticker || "—"}</td>
                  <td className="px-2 py-1.5 text-ink-700 truncate max-w-[220px]">{t.name || "—"}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmtMcap(t.market_cap)}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-ink-700">
                    {weight.toFixed(1).replace(".", ",")} %
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
