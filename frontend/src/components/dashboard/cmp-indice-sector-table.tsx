"use client";

/**
 * Tableau de comparaison sectorielle entre 2 indices.
 * Source : data.sector_comparison = Array<[sector, weight_a, weight_b]>
 */

type Row = [string, number | null, number | null];

interface Props {
  sectorComparison: Row[] | undefined;
  nameA: string;
  nameB: string;
}

function fmtW(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  return `${v.toFixed(1).replace(".", ",")} %`;
}

function deltaColor(a: number | null, b: number | null): string {
  if (a == null || b == null) return "text-ink-500";
  const d = a - b;
  if (Math.abs(d) < 1) return "text-ink-500";
  return d > 0 ? "text-signal-buy" : "text-signal-sell";
}

export function CmpIndiceSectorTable({ sectorComparison, nameA, nameB }: Props) {
  if (!sectorComparison || sectorComparison.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">Comparaison sectorielle indisponible</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden h-full flex flex-col">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Composition sectorielle — {nameA} vs {nameB}
        </div>
      </div>
      <div className="overflow-auto flex-1">
        <table className="w-full text-[11px]">
          <thead className="bg-ink-50 text-ink-600 sticky top-0">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold">Secteur</th>
              <th className="text-right px-2 py-1.5 font-semibold">{nameA}</th>
              <th className="text-right px-2 py-1.5 font-semibold">{nameB}</th>
              <th className="text-right px-2 py-1.5 font-semibold">Écart</th>
            </tr>
          </thead>
          <tbody>
            {sectorComparison.map(([sector, wa, wb], i) => {
              const delta = wa != null && wb != null ? wa - wb : null;
              return (
                <tr key={`${sector}-${i}`} className="border-t border-ink-100">
                  <td className="px-3 py-1.5 font-semibold text-ink-900">{sector}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-ink-800">{fmtW(wa)}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-ink-800">{fmtW(wb)}</td>
                  <td className={`px-2 py-1.5 text-right font-mono ${deltaColor(wa, wb)}`}>
                    {delta == null
                      ? "—"
                      : `${delta > 0 ? "+" : ""}${delta.toFixed(1).replace(".", ",")} pt`}
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
