"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import type { RawData, RatiosData } from "./types";

/**
 * Compte de résultat simplifié — dernière année.
 *   Revenue → Gross Profit → EBITDA → Net Income
 * Visualise la conversion marge brute → marge nette. Chaque barre est
 * colorée pour suggérer la dégradation progressive.
 */
export function IncomeStatementWaterfall({
  rawData,
  ratios,
  currency,
}: {
  rawData: RawData | undefined | null;
  ratios: RatiosData | undefined | null;
  currency?: string;
}) {
  const latest = ratios?.latest_year || (rawData?.years ? Object.keys(rawData.years).sort().pop() : undefined);
  if (!latest || !rawData?.years?.[latest]) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Compte de résultat indisponible.</span>
      </div>
    );
  }

  const y = rawData.years[latest];
  const r = ratios?.years?.[latest];
  const rev = (y.revenue as number | null) ?? null;
  const ebitda = (y.ebitda as number | null) ?? null;
  const ni = (y.net_income as number | null) ?? null;
  const grossMargin = r?.gross_margin as number | null | undefined;
  const grossProfit = rev != null && grossMargin != null ? rev * grossMargin : null;

  const ccy = currency || "USD";
  const fmtAbs = (v: number | null | undefined) => {
    if (v == null || !Number.isFinite(v)) return "—";
    const abs = Math.abs(v);
    if (abs >= 1e9) return `${(v / 1e9).toFixed(1)} Mds ${ccy}`;
    if (abs >= 1e6) return `${(v / 1e6).toFixed(0)} M ${ccy}`;
    if (abs >= 1e3) return `${(v / 1e3).toFixed(0)} k ${ccy}`;
    return `${v.toFixed(0)} ${ccy}`;
  };

  const steps = [
    { step: "Chiffre d'affaires", value: rev, color: "#1B3A6B" },
    { step: "Marge brute", value: grossProfit, color: "#2E6CA8" },
    { step: "EBITDA", value: ebitda, color: "#4A9EDC" },
    { step: "Résultat net", value: ni, color: "#6FBFE8" },
  ].filter((d) => d.value != null && Number.isFinite(d.value)) as { step: string; value: number; color: string }[];

  if (steps.length < 2) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400 italic">Données comptables insuffisantes.</span>
      </div>
    );
  }

  const base = steps[0].value;
  const lastRow = steps[steps.length - 1];
  const convRate = (v: number) => `${((v / base) * 100).toFixed(1)}%`;

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
            Compte de résultat simplifié
          </div>
          <div className="text-[10px] text-ink-500 mt-0.5">
            Exercice {latest} · Conversion chiffre d&apos;affaires → résultat net
          </div>
        </div>
        <div className="text-right text-[10px] text-ink-500">
          CA {fmtAbs(base)}
          <br />
          RN {fmtAbs(lastRow.value)}
          <span className="text-ink-400"> ({convRate(lastRow.value)})</span>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={steps} margin={{ top: 10, right: 60, left: 0, bottom: 5 }} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#6B7280" }} tickFormatter={(v) => fmtAbs(v)} />
            <YAxis type="category" dataKey="step" tick={{ fontSize: 11, fill: "#1F2937" }} width={110} />
            <Tooltip
              formatter={(v: number) => [`${fmtAbs(v)} (${convRate(v)})`, "Valeur"]}
              contentStyle={{ fontSize: 11 }}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]}>
              {steps.map((s, i) => (
                <Cell key={`cell-${i}`} fill={s.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
