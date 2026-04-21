"use client";

import { ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import type { RatiosData } from "./types";

/**
 * Historique ROE vs ROIC par exercice.
 * Le gap ROE-ROIC éclaire l'effet de levier financier :
 *   - ROE > ROIC → levier positif (endettement crée de la valeur actionnaire)
 *   - ROE < ROIC → levier destructeur
 */
export function RoeRoicHistoryChart({ ratios }: { ratios: RatiosData | undefined | null }) {
  if (!ratios?.years) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Historique ROE/ROIC indisponible.</span>
      </div>
    );
  }

  const years = Object.keys(ratios.years).sort();
  const points = years.map((y) => {
    const r = ratios.years[y];
    const roe = r?.roe != null ? Number((r.roe as number * 100).toFixed(1)) : null;
    const roic = r?.roic != null ? Number((r.roic as number * 100).toFixed(1)) : null;
    return { year: y, roe, roic, spread: roe != null && roic != null ? Number((roe - roic).toFixed(1)) : null };
  });

  const valid = points.filter((p) => p.roe != null || p.roic != null);
  if (valid.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Aucune année avec ROE ou ROIC exploitables.</span>
      </div>
    );
  }

  const last = valid[valid.length - 1];
  const avgRoe =
    valid.filter((p) => p.roe != null).reduce((a, p) => a + (p.roe as number), 0) /
    Math.max(1, valid.filter((p) => p.roe != null).length);
  const avgRoic =
    valid.filter((p) => p.roic != null).reduce((a, p) => a + (p.roic as number), 0) /
    Math.max(1, valid.filter((p) => p.roic != null).length);

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Rentabilité — ROE vs ROIC
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            ROE = capitaux propres · ROIC = capital investi · gap = effet de levier
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-ink-500">
            Moy. ROE <span className="font-mono text-ink-900">{avgRoe.toFixed(1)}%</span>
          </div>
          <div className="text-[10px] text-ink-500">
            Moy. ROIC <span className="font-mono text-ink-900">{avgRoic.toFixed(1)}%</span>
          </div>
          <div className="text-[10px] text-ink-500">
            Dernier spread{" "}
            <span className="font-mono text-ink-900">
              {last.spread != null ? `${last.spread > 0 ? "+" : ""}${last.spread.toFixed(1)} pts` : "—"}
            </span>
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={valid} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="year" tick={{ fontSize: 10, fill: "#6B7280" }} />
            <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} unit="%" width={40} />
            <Tooltip
              formatter={(v: number, name: string) => [v != null ? `${v.toFixed(1)} %` : "—", name]}
              contentStyle={{ fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="roe" name="ROE" fill="#1B3A6B" radius={[3, 3, 0, 0]} />
            <Line type="monotone" dataKey="roic" name="ROIC" stroke="#B06000" strokeWidth={2} dot={{ r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
