"use client";

/**
 * Tableau de tuiles comparatives : chaque statistique A vs B côte à côte.
 * Catégories : Performance, Risque, Valorisation.
 */

interface Props {
  data: Record<string, unknown>;
  nameA: string;
  nameB: string;
}

type Group = {
  title: string;
  rows: Array<{
    label: string;
    keyA: string;
    keyB: string;
    /** "pct_auto" (décimal→%), "pct_raw" (valeur déjà en %), "x" (multiple), "num" */
    kind: "pct_auto" | "pct_raw" | "x" | "num" | "str";
    colored?: boolean;
  }>;
};

const GROUPS: Group[] = [
  {
    title: "Performance",
    rows: [
      { label: "YTD", keyA: "perf_ytd_a", keyB: "perf_ytd_b", kind: "pct_auto", colored: true },
      { label: "1 an", keyA: "perf_1y_a", keyB: "perf_1y_b", kind: "pct_auto", colored: true },
      { label: "3 ans", keyA: "perf_3y_a", keyB: "perf_3y_b", kind: "pct_auto", colored: true },
      { label: "5 ans", keyA: "perf_5y_a", keyB: "perf_5y_b", kind: "pct_auto", colored: true },
    ],
  },
  {
    title: "Risque",
    rows: [
      { label: "Volatilité 1A", keyA: "vol_1y_a", keyB: "vol_1y_b", kind: "pct_raw" },
      { label: "Sharpe 1A", keyA: "sharpe_1y_a", keyB: "sharpe_1y_b", kind: "num" },
      { label: "Max Drawdown", keyA: "max_dd_a", keyB: "max_dd_b", kind: "pct_auto", colored: true },
    ],
  },
  {
    title: "Valorisation",
    rows: [
      { label: "P/E Forward", keyA: "pe_fwd_a", keyB: "pe_fwd_b", kind: "x" },
      { label: "P/B", keyA: "pb_a", keyB: "pb_b", kind: "x" },
      { label: "Div. Yield", keyA: "div_yield_a", keyB: "div_yield_b", kind: "pct_auto" },
      { label: "ERP", keyA: "erp_a", keyB: "erp_b", kind: "str" },
    ],
  },
];

function fmt(v: unknown, kind: Group["rows"][number]["kind"]): { txt: string; raw: number | null } {
  if (v == null) return { txt: "—", raw: null };
  if (kind === "str") {
    return { txt: typeof v === "string" && v.trim() ? v : "—", raw: null };
  }
  const n = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
  if (!isFinite(n)) return { txt: "—", raw: null };
  switch (kind) {
    case "pct_auto": {
      const pct = Math.abs(n) < 2 ? n * 100 : n;
      const sign = pct > 0 ? "+" : "";
      return { txt: `${sign}${pct.toFixed(1).replace(".", ",")} %`, raw: pct };
    }
    case "pct_raw":
      return { txt: `${n.toFixed(1).replace(".", ",")} %`, raw: n };
    case "x":
      return { txt: `${n.toFixed(1).replace(".", ",")}x`, raw: n };
    case "num":
      return { txt: n.toFixed(2).replace(".", ","), raw: n };
  }
  return { txt: "—", raw: null };
}

function colorFor(raw: number | null, colored?: boolean): string {
  if (!colored || raw == null) return "text-ink-800";
  return raw >= 0 ? "text-signal-buy" : "text-signal-sell";
}

export function CmpIndiceStatTiles({ data, nameA, nameB }: Props) {
  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col overflow-hidden">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Statistiques clés — {nameA} vs {nameB}
        </div>
      </div>
      <div className="flex-1 overflow-auto px-3 pb-3">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-ink-600">
              <th className="text-left py-1 font-semibold">&nbsp;</th>
              <th className="text-right py-1 font-semibold pr-2">{nameA}</th>
              <th className="text-right py-1 font-semibold">{nameB}</th>
            </tr>
          </thead>
          <tbody>
            {GROUPS.map((g) => (
              <>
                <tr key={`group-${g.title}`}>
                  <td
                    colSpan={3}
                    className="text-[9px] uppercase tracking-wider text-ink-500 font-semibold pt-2.5 pb-1 border-b border-ink-100"
                  >
                    {g.title}
                  </td>
                </tr>
                {g.rows.map((r) => {
                  const a = fmt(data[r.keyA], r.kind);
                  const b = fmt(data[r.keyB], r.kind);
                  return (
                    <tr key={`${g.title}-${r.label}`} className="border-b border-ink-50">
                      <td className="py-1 text-ink-700">{r.label}</td>
                      <td className={`py-1 text-right font-mono pr-2 ${colorFor(a.raw, r.colored)}`}>
                        {a.txt}
                      </td>
                      <td className={`py-1 text-right font-mono ${colorFor(b.raw, r.colored)}`}>
                        {b.txt}
                      </td>
                    </tr>
                  );
                })}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
