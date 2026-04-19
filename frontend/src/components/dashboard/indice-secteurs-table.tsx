"use client";

import type { IndiceSector } from "./types";
import { useI18n } from "@/i18n/provider";

interface Props {
  secteurs: IndiceSector[];
  universe?: string;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || isNaN(v as number)) return "—";
  const pct = (v as number) > 0 && (v as number) < 1 ? (v as number) * 100 : (v as number);
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1).replace(".", ",")} %`;
}

function fmtWeight(v: number | null | undefined): string {
  if (v == null || isNaN(v as number)) return "—";
  const pct = (v as number) > 0 && (v as number) < 1 ? (v as number) * 100 : (v as number);
  return `${pct.toFixed(1).replace(".", ",")} %`;
}

export function IndiceSecteursTable({ secteurs, universe }: Props) {
  const { t } = useI18n();
  if (!secteurs || secteurs.length === 0) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">{t("kpi.no_sector_data")}</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden h-full flex flex-col">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          {t("kpi.sector_mapping")}{universe ? ` — ${universe}` : ""}
        </div>
      </div>
      <div className="overflow-auto flex-1">
        <table className="w-full text-[11px]">
          <thead className="bg-ink-50 text-ink-600 sticky top-0">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold">{t("kpi.sector")}</th>
              <th className="text-right px-2 py-1.5 font-semibold">{t("kpi.weight")}</th>
              <th className="text-right px-2 py-1.5 font-semibold">{t("kpi.performance_short")}</th>
              <th className="text-left px-2 py-1.5 font-semibold">{t("kpi.top_companies")}</th>
            </tr>
          </thead>
          <tbody>
            {secteurs.map((s, i) => {
              const perfNum = typeof s.performance === "number" ? s.performance : null;
              const perfClass =
                perfNum == null
                  ? "text-ink-500"
                  : perfNum >= 0
                  ? "text-signal-buy"
                  : "text-signal-sell";
              return (
                <tr key={`${s.name}-${i}`} className="border-t border-ink-100">
                  <td className="px-3 py-1.5 font-semibold text-ink-900">{s.name || "?"}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmtWeight(s.weight)}</td>
                  <td className={`px-2 py-1.5 text-right font-mono ${perfClass}`}>
                    {fmtPct(s.performance)}
                  </td>
                  <td className="px-2 py-1.5 text-ink-600 font-mono text-[10px]">
                    {(s.top_tickers || []).slice(0, 4).join(" · ") || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-1.5 text-[10px] text-ink-400 italic border-t border-ink-100 flex-none">
        {t("kpi.peers_source")}
      </div>
    </div>
  );
}
