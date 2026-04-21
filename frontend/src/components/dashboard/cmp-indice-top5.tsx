"use client";

/**
 * Top 5 constituants A et B côte à côte.
 * Source : data.top5_a, data.top5_b = Array<[name, ticker, weight_pct, sector]>
 */

type Row = [string, string, number | null, string];

interface Props {
  top5A: Row[] | undefined;
  top5B: Row[] | undefined;
  nameA: string;
  nameB: string;
}

function fmtW(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  return `${v.toFixed(1).replace(".", ",")} %`;
}

function Panel({ title, rows }: { title: string; rows: Row[] | undefined }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="flex-1 bg-ink-50 rounded-md p-3 border border-ink-100">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
          {title}
        </div>
        <div className="text-xs text-ink-400 italic">Non disponible</div>
      </div>
    );
  }
  return (
    <div className="flex-1 bg-white rounded-md p-3 border border-ink-100">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-600 mb-2">
        {title}
      </div>
      <table className="w-full text-[11px]">
        <tbody>
          {rows.slice(0, 5).map(([name, ticker, weight, sector], i) => (
            <tr key={`${ticker}-${i}`} className="border-b border-ink-50 last:border-0">
              <td className="py-1 font-mono text-ink-500 w-6">{i + 1}</td>
              <td className="py-1">
                <div className="font-semibold text-ink-900 truncate max-w-[180px]">{name}</div>
                <div className="text-[9px] text-ink-500 font-mono">
                  {ticker} · {sector || "—"}
                </div>
              </td>
              <td className="py-1 text-right font-mono text-ink-700 whitespace-nowrap">
                {fmtW(weight)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CmpIndiceTop5({ top5A, top5B, nameA, nameB }: Props) {
  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col overflow-hidden">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Top 5 constituants
        </div>
      </div>
      <div className="flex-1 flex gap-2 px-3 pb-3 overflow-auto">
        <Panel title={nameA} rows={top5A} />
        <Panel title={nameB} rows={top5B} />
      </div>
    </div>
  );
}
