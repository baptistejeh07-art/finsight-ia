import type { SectorTicker } from "./types";

interface Props {
  tickers: SectorTicker[];
  sectorLabel?: string;
}

function fmtX(v: number | null | undefined): string {
  if (v == null || isNaN(v as number)) return "—";
  return `${(v as number).toFixed(1).replace(".", ",")}x`;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || isNaN(v as number)) return "—";
  const pct = (v as number) > 0 && (v as number) < 1 ? (v as number) * 100 : (v as number);
  return `${pct.toFixed(1).replace(".", ",")} %`;
}

function fmtMcap(v: number | null | undefined): string {
  if (v == null || isNaN(v as number)) return "—";
  const b = (v as number) / 1_000_000_000;
  return `${b.toFixed(1)} Md`;
}

export function SectorTickersTable({ tickers, sectorLabel }: Props) {
  if (!tickers || tickers.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">Aucune société disponible</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden h-full flex flex-col">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Sociétés du secteur{sectorLabel ? ` — ${sectorLabel}` : ""}
        </div>
      </div>
      <div className="overflow-auto flex-1">
        <table className="w-full text-[11px]">
          <thead className="bg-ink-50 text-ink-600 sticky top-0">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold">Ticker</th>
              <th className="text-left px-2 py-1.5 font-semibold">Société</th>
              <th className="text-right px-2 py-1.5 font-semibold">Mkt Cap</th>
              <th className="text-right px-2 py-1.5 font-semibold">P/E</th>
              <th className="text-right px-2 py-1.5 font-semibold">EV/EBITDA</th>
              <th className="text-right px-2 py-1.5 font-semibold">Marge EBITDA</th>
              <th className="text-right px-2 py-1.5 font-semibold">ROE</th>
            </tr>
          </thead>
          <tbody>
            {tickers.map((t, i) => {
              const r = t.ratios || {};
              return (
                <tr key={`${t.ticker}-${i}`} className="border-t border-ink-100">
                  <td className="px-3 py-1.5 font-mono font-semibold text-ink-900">{t.ticker || "?"}</td>
                  <td className="px-2 py-1.5 text-ink-700 truncate max-w-[180px]">{t.name || "—"}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmtMcap(t.market_cap)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmtX(r.pe_ratio)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmtX(r.ev_ebitda)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmtPct(r.ebitda_margin)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmtPct(r.roe)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-1.5 text-[10px] text-ink-400 italic border-t border-ink-100 flex-none">
        Source : FinSight IA — yfinance + FMP
      </div>
    </div>
  );
}
