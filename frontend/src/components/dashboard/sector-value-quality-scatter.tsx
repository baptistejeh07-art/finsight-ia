"use client";

import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";
import type { SectorTicker } from "./types";

/**
 * Scatter EV/EBITDA (axe X, valorisation) vs Marge EBITDA (axe Y, qualité).
 * Bulle = market cap. Quadrant haut-gauche = pépite value + qualité (cher à trouver).
 * Quadrant bas-droite = trap — chère et peu rentable.
 */
export function SectorValueQualityScatter({
  tickers,
  label,
}: {
  tickers: SectorTicker[] | undefined | null;
  label?: string;
}) {
  if (!tickers || tickers.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Aucun ticker disponible.</span>
      </div>
    );
  }

  const points = tickers
    .map((t) => {
      const ev = (t.ratios?.ev_ebitda as number | null | undefined) ?? null;
      let mg = (t.ratios?.ebitda_margin as number | null | undefined) ?? null;
      if (mg != null && Math.abs(mg) < 1.5) mg = mg * 100; // decimal → %
      const mc = (t.market_cap as number | null | undefined) ?? null;
      if (ev == null || mg == null || !Number.isFinite(ev) || !Number.isFinite(mg)) return null;
      if (ev <= 0 || ev > 150) return null; // filtre aberrations
      return {
        ticker: t.ticker || t.name || "?",
        name: t.name || t.ticker || "?",
        ev,
        mg,
        mc: mc != null && Number.isFinite(mc) && mc > 0 ? mc : 1,
      };
    })
    .filter((p): p is NonNullable<typeof p> => p != null);

  if (points.length < 3) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Trop peu de données (EV/EBITDA + marge) pour le scatter.</span>
      </div>
    );
  }

  const medEv = [...points].map((p) => p.ev).sort((a, b) => a - b)[Math.floor(points.length / 2)];
  const medMg = [...points].map((p) => p.mg).sort((a, b) => a - b)[Math.floor(points.length / 2)];

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Valeur × Qualité{label ? ` — ${label}` : ""}
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            EV/EBITDA (X) vs Marge EBITDA (Y) · taille = capitalisation
          </div>
        </div>
        <div className="text-right text-[10px] text-ink-500 font-mono">
          Médiane EV {medEv.toFixed(1)}x · Mg {medMg.toFixed(0)}%
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis
              type="number"
              dataKey="ev"
              name="EV/EBITDA"
              unit="x"
              tick={{ fontSize: 10, fill: "#6B7280" }}
              label={{ value: "EV/EBITDA", position: "insideBottom", offset: -2, fontSize: 10, fill: "#6B7280" }}
            />
            <YAxis
              type="number"
              dataKey="mg"
              name="Marge EBITDA"
              unit="%"
              tick={{ fontSize: 10, fill: "#6B7280" }}
              width={40}
            />
            <ZAxis type="number" dataKey="mc" range={[40, 400]} />
            <ReferenceLine x={medEv} stroke="#9CA3AF" strokeDasharray="3 3" />
            <ReferenceLine y={medMg} stroke="#9CA3AF" strokeDasharray="3 3" />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ fontSize: 11 }}
              formatter={(v: number, name: string) => {
                if (name === "EV/EBITDA") return [`${v.toFixed(1)}x`, name];
                if (name === "Marge EBITDA") return [`${v.toFixed(1)}%`, name];
                return [v, name];
              }}
              labelFormatter={() => ""}
              content={({ payload }) => {
                if (!payload || payload.length === 0) return null;
                const p = payload[0].payload as { ticker: string; name: string; ev: number; mg: number };
                return (
                  <div className="bg-white border border-ink-200 rounded px-2.5 py-1.5 shadow-sm text-[11px]">
                    <div className="font-semibold text-ink-900">{p.ticker}</div>
                    <div className="text-ink-500">{p.name}</div>
                    <div className="font-mono mt-1">EV/EBITDA {p.ev.toFixed(1)}x</div>
                    <div className="font-mono">Mg EBITDA {p.mg.toFixed(1)}%</div>
                  </div>
                );
              }}
            />
            <Scatter data={points} fill="#1B3A6B" fillOpacity={0.7} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
