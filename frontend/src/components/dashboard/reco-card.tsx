"use client";

import { signalColor, signalLabel } from "@/lib/utils";
import { useI18n } from "@/i18n/provider";

export function RecoCard({
  recommendation,
  conviction,
}: {
  recommendation: string;
  conviction: number;
}) {
  const { t, fp } = useI18n();
  // Clamp [20%, 90%] aussi en frontend : les anciennes analyses historiques
  // peuvent avoir conviction=0.01 (bug LLM corrigé côté backend le 2026-04-20).
  // Double garde pour UX cohérente sans forcer re-run des analyses passées.
  const rawPct = Math.round((conviction || 0) * 100);
  const pct = Math.max(20, Math.min(90, rawPct || 50));

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5 h-full">
      <div className="grid grid-cols-2 gap-6">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
            {t("results.recommendation")}
          </div>
          <div className={`text-2xl font-bold ${signalColor(recommendation)}`}>
            {signalLabel(recommendation)}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2">
            {t("results.ai_conviction")}
          </div>
          <div className="text-2xl font-bold text-ink-900 font-mono">{fp(pct, 0)}</div>
          <div className="w-full h-1 bg-ink-100 rounded-full mt-2 overflow-hidden">
            <div
              className="h-full bg-ink-900 rounded-full"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
