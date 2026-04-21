"use client";

import { Factory, TrendingUp, Gauge, Users } from "lucide-react";

interface Props {
  sector?: string;
  universe?: string;
  summary?: string | null;
  analytics?: Record<string, unknown>;
  etf?: { ticker: string; name: string; zone?: string } | null;
  tickersCount?: number;
}

function _num(v: unknown): number | null {
  return typeof v === "number" && !isNaN(v) ? v : null;
}

function _str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

/**
 * Portrait secteur — équivalent de PortraitCard pour l'analyse société.
 * Affiche le résumé narratif + 4 KPI cards (HHI, P/E cycle, ROIC,
 * couverture) + l'ETF de référence.
 */
export function SectorPortraitCard({
  sector,
  universe,
  summary,
  analytics,
  etf,
  tickersCount,
}: Props) {
  const a = analytics || {};
  const hhi = _num(a.hhi);
  const hhiLabel = _str(a.hhi_label);
  const peMed = _num(a.pe_median_ltm);
  const peCycle = _str(a.pe_cycle_label);
  const roicMean = _num(a.roic_mean);
  const roicStd = _num(a.roic_std);
  const roicLabel = _str(a.roic_label);

  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col overflow-hidden">
      <div className="px-4 pt-3 pb-2 border-b border-ink-100">
        <div className="text-[10px] uppercase tracking-[1.5px] text-ink-500 font-semibold">
          Portrait secteur
        </div>
        <div className="flex items-baseline gap-2 mt-0.5">
          <span className="text-sm font-semibold text-ink-900">{sector || "Secteur"}</span>
          {universe && (
            <span className="text-xs text-ink-500">· {universe}</span>
          )}
        </div>
        {etf?.ticker && (
          <div className="text-[10px] text-ink-500 mt-0.5 font-mono">
            ETF réf. : {etf.ticker}{etf.name ? ` — ${etf.name}` : ""}
          </div>
        )}
      </div>

      {summary && (
        <div className="px-4 py-3 border-b border-ink-100 text-sm text-ink-700 leading-relaxed">
          {summary}
        </div>
      )}

      <div className="flex-1 px-3 py-3 grid grid-cols-2 gap-2 overflow-auto">
        <StatCard
          icon={<Users className="w-3.5 h-3.5" />}
          label="Couverture"
          value={tickersCount ? `${tickersCount} sociétés` : "—"}
          hint={universe || "Univers"}
        />
        <StatCard
          icon={<Factory className="w-3.5 h-3.5" />}
          label="HHI concentration"
          value={hhi != null ? `${hhi.toLocaleString("fr-FR")}` : "—"}
          hint={hhiLabel || "Structure de marché"}
        />
        <StatCard
          icon={<TrendingUp className="w-3.5 h-3.5" />}
          label="P/E médian"
          value={peMed != null ? `${peMed}x` : "—"}
          hint={peCycle || "Valorisation vs historique"}
        />
        <StatCard
          icon={<Gauge className="w-3.5 h-3.5" />}
          label="ROIC moyen"
          value={roicMean != null ? `${roicMean}%` : "—"}
          hint={
            roicStd != null
              ? `σ = ${roicStd}% · ${roicLabel || "Dispersion"}`
              : roicLabel || "Dispersion"
          }
        />
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="bg-ink-50/60 border border-ink-100 rounded-md p-2.5 flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-ink-500 font-semibold">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-base font-mono font-semibold text-ink-900">{value}</div>
      <div className="text-[10px] text-ink-600 leading-snug line-clamp-2">{hint}</div>
    </div>
  );
}
