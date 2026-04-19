"use client";

import type { Synthesis } from "./types";
import { useI18n } from "@/i18n/provider";

export function SyntheseCard({ synthesis }: { synthesis: Synthesis }) {
  const { t } = useI18n();
  const blocs: { title?: string; text: string }[] = [];

  const intro = synthesis.summary || synthesis.thesis;
  if (intro) blocs.push({ text: intro });

  if (synthesis.valuation_comment && synthesis.valuation_comment !== intro) {
    blocs.push({ title: t("kpi.valuation_comment"), text: synthesis.valuation_comment });
  }
  if (synthesis.financial_commentary) {
    blocs.push({ title: t("kpi.financial_reading"), text: synthesis.financial_commentary });
  }
  if (synthesis.peers_commentary) {
    blocs.push({ title: t("kpi.competitive_position"), text: synthesis.peers_commentary });
  }
  if (synthesis.conclusion && synthesis.conclusion !== intro) {
    blocs.push({ title: t("kpi.to_remember"), text: synthesis.conclusion });
  }

  if (blocs.length === 0) return null;

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5 h-full overflow-auto">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
        {t("kpi.synthesis_analysis")}
      </div>
      <div className="space-y-3">
        {blocs.map((b, i) => (
          <div key={i}>
            {b.title && (
              <div className="text-[10px] font-semibold uppercase tracking-[1px] text-ink-600 mb-1">
                {b.title}
              </div>
            )}
            <p className="text-sm text-ink-700 leading-relaxed whitespace-pre-line">
              {b.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
