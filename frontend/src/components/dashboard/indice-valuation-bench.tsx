"use client";

/**
 * Benchmark valorisation de l'indice courant vs S&P 500 (fallback values).
 * Source : result.data.indice_stats (pe_median, pb_median, div_yield).
 */

interface Props {
  stats: Record<string, unknown> | null | undefined;
  universe?: string;
}

const SP500_BENCH = {
  pe: 21.5,
  pb: 4.5,
  dy: 1.4, // en %
};

function num(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : parseFloat(String(v));
  return isFinite(n) && n > 0 ? n : null;
}

function toPct(v: unknown): number | null {
  const n = num(v);
  if (n == null) return null;
  return n < 1 ? n * 100 : n;
}

function fmtX(n: number | null): string {
  return n == null ? "—" : `${n.toFixed(1).replace(".", ",")}x`;
}
function fmtPct(n: number | null): string {
  return n == null ? "—" : `${n.toFixed(2).replace(".", ",")} %`;
}

function deltaCls(diff: number | null, reverse = false): string {
  if (diff == null) return "text-ink-500";
  if (Math.abs(diff) < 0.01) return "text-ink-500";
  const positive = reverse ? diff < 0 : diff > 0;
  return positive ? "text-signal-buy" : "text-signal-sell";
}

export function IndiceValuationBench({ stats, universe }: Props) {
  const s = (stats || {}) as Record<string, unknown>;
  const pe = num(s.pe_median ?? s.pe_fwd ?? s.pe);
  const pb = num(s.pb_median ?? s.pb);
  const dy = toPct(s.div_yield ?? s.dividend_yield ?? s.dy);

  if (pe == null && pb == null && dy == null) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">Benchmark valorisation indisponible</span>
      </div>
    );
  }

  const rows: Array<{ label: string; cur: string; bench: string; delta: number | null }> = [
    {
      label: "P/E",
      cur: fmtX(pe),
      bench: fmtX(SP500_BENCH.pe),
      delta: pe != null ? pe - SP500_BENCH.pe : null,
    },
    {
      label: "P/B",
      cur: fmtX(pb),
      bench: fmtX(SP500_BENCH.pb),
      delta: pb != null ? pb - SP500_BENCH.pb : null,
    },
    {
      label: "Rendement div.",
      cur: fmtPct(dy),
      bench: fmtPct(SP500_BENCH.dy),
      delta: dy != null ? dy - SP500_BENCH.dy : null,
    },
  ];

  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col overflow-hidden">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Valorisation vs S&P 500{universe ? ` — ${universe}` : ""}
        </div>
      </div>
      <div className="flex-1 overflow-auto px-3 pb-3">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-ink-600">
              <th className="text-left py-1 font-semibold">Multiple</th>
              <th className="text-right py-1 font-semibold">{universe || "Indice"}</th>
              <th className="text-right py-1 font-semibold">S&P 500</th>
              <th className="text-right py-1 font-semibold">Écart</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-t border-ink-100">
                <td className="py-1.5 text-ink-800 font-semibold">{r.label}</td>
                <td className="py-1.5 text-right font-mono">{r.cur}</td>
                <td className="py-1.5 text-right font-mono text-ink-600">{r.bench}</td>
                <td
                  className={`py-1.5 text-right font-mono ${deltaCls(
                    r.delta,
                    r.label === "Rendement div."
                  )}`}
                >
                  {r.delta == null
                    ? "—"
                    : r.label === "Rendement div."
                    ? `${r.delta >= 0 ? "+" : ""}${r.delta.toFixed(2).replace(".", ",")} pt`
                    : `${r.delta >= 0 ? "+" : ""}${r.delta.toFixed(1).replace(".", ",")}x`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-[9px] text-ink-400 italic mt-2">
          Benchmark S&P 500 : P/E 21,5x · P/B 4,5x · DY 1,4 %
        </div>
      </div>
    </div>
  );
}
