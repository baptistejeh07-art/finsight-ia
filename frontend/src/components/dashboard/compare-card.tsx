"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { submitCmpSocieteJob } from "@/lib/api";
import { useI18n } from "@/i18n/provider";

export function CompareCard({ targetTicker }: { targetTicker: string }) {
  const { t } = useI18n();
  const router = useRouter();
  const [other, setOther] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleCompare() {
    const tk = other.trim().toUpperCase();
    if (!tk) return;
    if (tk === targetTicker.toUpperCase()) {
      toast.error(t("kpi.different_ticker"));
      return;
    }
    setBusy(true);
    try {
      const res = await submitCmpSocieteJob(targetTicker, tk);
      router.push(`/analyse?id=${res.job_id}&kind=comparatif&label=${targetTicker} vs ${tk}`);
    } catch (e) {
      toast.error(t("kpi.compare_launch_error"));
      console.error(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5 h-full">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
        {t("kpi.compare_analysis")}
      </div>
      <p className="text-xs text-ink-600 mb-3">
        {t("kpi.compare_with").replace("{ticker}", targetTicker)}
      </p>
      <input
        type="text"
        value={other}
        onChange={(e) => setOther(e.target.value)}
        placeholder={t("kpi.compare_placeholder")}
        className="w-full px-3 py-2 border border-ink-200 rounded text-sm font-mono uppercase mb-3 focus:outline-none focus:border-navy-500"
        onKeyDown={(e) => e.key === "Enter" && !busy && handleCompare()}
      />
      <button
        onClick={handleCompare}
        disabled={busy || !other.trim()}
        className="w-full px-3 py-2 rounded bg-navy-500 text-white text-xs font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {busy ? t("kpi.launching") : t("kpi.compare_btn")}
      </button>
    </div>
  );
}
