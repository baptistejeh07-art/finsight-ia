"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown } from "lucide-react";
import { useI18n } from "@/i18n/provider";

interface Warning {
  field: string;
  severity: "info" | "warning" | "error";
  hint: string;
}

const SEVERITY_STYLES: Record<string, { bg: string; border: string; text: string; pill: string }> = {
  error: {
    bg: "bg-signal-sell/5",
    border: "border-signal-sell/30",
    text: "text-signal-sell",
    pill: "bg-signal-sell/15 text-signal-sell",
  },
  warning: {
    bg: "bg-amber-500/5",
    border: "border-amber-400/40",
    text: "text-amber-700",
    pill: "bg-amber-500/15 text-amber-700",
  },
  info: {
    bg: "bg-ink-50",
    border: "border-ink-200",
    text: "text-ink-700",
    pill: "bg-ink-200 text-ink-700",
  },
};

export function WarningsBanner({ warnings }: { warnings: Warning[] }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  if (!warnings || warnings.length === 0) return null;

  const errors = warnings.filter((w) => w.severity === "error").length;
  const wts = warnings.filter((w) => w.severity === "warning").length;
  const top = errors > 0 ? "error" : wts > 0 ? "warning" : "info";
  const s = SEVERITY_STYLES[top];

  const summary =
    errors > 0
      ? `${errors} ${errors > 1 ? t("settings.warn_error_plur") : t("settings.warn_error_sing")}`
      : wts > 0
        ? `${wts} ${wts > 1 ? t("settings.warn_warning_plur") : t("settings.warn_warning_sing")}`
        : `${warnings.length} ${warnings.length > 1 ? t("settings.warn_note_plur") : t("settings.warn_note_sing")}`;

  const detailLabel = warnings.length > 1
    ? t("settings.warn_detail_plur")
    : t("settings.warn_detail_sing");

  return (
    <div className={`mb-4 rounded-md border ${s.border} ${s.bg} overflow-hidden`}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-black/[0.02] transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <AlertTriangle className={`w-4 h-4 ${s.text}`} />
          <span className={`text-sm font-semibold ${s.text}`}>
            {t("settings.warn_analysis_contains")} {summary}
          </span>
          <span className="text-xs text-ink-500">
            ({warnings.length} {detailLabel})
          </span>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-ink-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className={`border-t ${s.border} px-4 py-3 space-y-2 bg-white/50`}>
          {warnings.map((w, i) => {
            const ws = SEVERITY_STYLES[w.severity] || SEVERITY_STYLES.info;
            return (
              <div key={i} className="flex items-start gap-2.5">
                <span
                  className={`text-2xs uppercase font-semibold px-2 py-0.5 rounded shrink-0 ${ws.pill}`}
                >
                  {w.severity}
                </span>
                <div className="flex-1 text-xs text-ink-700 leading-relaxed">
                  <code className="text-2xs bg-ink-100 px-1.5 py-0.5 rounded mr-1.5 text-ink-600">
                    {w.field}
                  </code>
                  {w.hint}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
