"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

/**
 * Profil de risque comparé A vs B : volatilité, Sharpe et Max Drawdown.
 * Vol et MDD en %, Sharpe en ratio. Sharpe plus haut = meilleur.
 */
interface RiskData {
  vol_1y?: number | null;
  sharpe_1y?: number | null;
  max_dd?: number | null;
}

function toPct(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return Math.abs(n) < 2 ? n * 100 : n;
}

function toNum(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function CmpRiskProfile({
  statsA,
  statsB,
  nameA,
  nameB,
}: {
  statsA: RiskData | undefined | null;
  statsB: RiskData | undefined | null;
  nameA?: string;
  nameB?: string;
}) {
  const labelA = nameA || "A";
  const labelB = nameB || "B";
  const a = statsA || {};
  const b = statsB || {};

  const rows = [
    {
      metric: "Volatilité 1A (%)",
      [labelA]: toPct(a.vol_1y),
      [labelB]: toPct(b.vol_1y),
    },
    {
      metric: "Sharpe 1A (ratio)",
      [labelA]: toNum(a.sharpe_1y),
      [labelB]: toNum(b.sharpe_1y),
    },
    {
      metric: "Max Drawdown (%)",
      [labelA]: toPct(a.max_dd) != null ? Math.abs(toPct(a.max_dd) as number) : null,
      [labelB]: toPct(b.max_dd) != null ? Math.abs(toPct(b.max_dd) as number) : null,
    },
  ];

  const hasData = rows.some((r) => r[labelA] != null || r[labelB] != null);
  if (!hasData) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Métriques de risque indisponibles.</span>
      </div>
    );
  }

  const data = rows.map((r) => ({
    metric: r.metric,
    [labelA]: r[labelA] != null ? Number((r[labelA] as number).toFixed(2)) : null,
    [labelB]: r[labelB] != null ? Number((r[labelB] as number).toFixed(2)) : null,
  }));

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="mb-2">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Profil de risque — {labelA} vs {labelB}
        </div>
        <div className="text-[10px] text-ink-500 mt-0.5">
          Volatilité et max drawdown en %, Sharpe en ratio (Max DD en valeur absolue)
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 40, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#6B7280" }} />
            <YAxis type="category" dataKey="metric" tick={{ fontSize: 10, fill: "#1F2937" }} width={140} />
            <Tooltip formatter={(v: number) => (v != null ? v.toFixed(2) : "—")} contentStyle={{ fontSize: 11 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey={labelA} fill="#1B3A6B" radius={[0, 3, 3, 0]} />
            <Bar dataKey={labelB} fill="#B06000" radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
