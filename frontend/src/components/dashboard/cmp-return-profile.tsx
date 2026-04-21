"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, ReferenceLine } from "recharts";

/**
 * Profil de rendement comparé A vs B : YTD, 1A, 3A, 5A côte à côte.
 * Permet d'identifier rapidement qui domine sur chaque horizon.
 */
interface PerfData {
  perf_ytd?: number | null;
  perf_1y?: number | null;
  perf_3y?: number | null;
  perf_5y?: number | null;
}

function toPct(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return Math.abs(n) < 2 ? n * 100 : n;
}

export function CmpReturnProfile({
  statsA,
  statsB,
  nameA,
  nameB,
}: {
  statsA: PerfData | undefined | null;
  statsB: PerfData | undefined | null;
  nameA?: string;
  nameB?: string;
}) {
  const labelA = nameA || "A";
  const labelB = nameB || "B";
  const a = statsA || {};
  const b = statsB || {};

  const horizons: { key: keyof PerfData; label: string }[] = [
    { key: "perf_ytd", label: "YTD" },
    { key: "perf_1y", label: "1 an" },
    { key: "perf_3y", label: "3 ans" },
    { key: "perf_5y", label: "5 ans" },
  ];

  const data = horizons
    .map((h) => {
      const va = toPct(a[h.key]);
      const vb = toPct(b[h.key]);
      if (va == null && vb == null) return null;
      return { horizon: h.label, [labelA]: va != null ? Number(va.toFixed(1)) : null, [labelB]: vb != null ? Number(vb.toFixed(1)) : null };
    })
    .filter((d): d is NonNullable<typeof d> => d != null);

  if (data.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Performances multi-horizons indisponibles.</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="mb-2">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Profil de rendement — {labelA} vs {labelB}
        </div>
        <div className="text-[10px] text-ink-500 mt-0.5">YTD, 1 an, 3 ans et 5 ans côte à côte</div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="horizon" tick={{ fontSize: 11, fill: "#1F2937" }} />
            <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} unit="%" width={40} />
            <ReferenceLine y={0} stroke="#6B7280" />
            <Tooltip
              formatter={(v: number, name: string) => [v != null ? `${v > 0 ? "+" : ""}${v.toFixed(1)} %` : "—", name]}
              contentStyle={{ fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey={labelA} fill="#1B3A6B" radius={[3, 3, 0, 0]} />
            <Bar dataKey={labelB} fill="#B06000" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
