"use client";

import type { YearRatios } from "./types";
import { useI18n } from "@/i18n/provider";

type Tone = "good" | "neutral" | "bad";

interface KpiDef {
  key: keyof YearRatios;
  labelKey: string;
  format: "x" | "%" | "raw";
  tooltipKey: string;
  transform?: (v: number) => number;
  rate: (v: number, t: (k: string) => string) => { tone: Tone; tag: string };
}

const KPIS: KpiDef[] = [
  {
    key: "pe_ratio",
    labelKey: "kpi.pe",
    format: "x",
    tooltipKey: "rating.neutral",
    rate: (v, t) =>
      v < 15
        ? { tone: "good", tag: t("rating.low") }
        : v < 30
        ? { tone: "neutral", tag: t("rating.neutral") }
        : { tone: "bad", tag: t("rating.high") },
  },
  {
    key: "ev_ebitda",
    labelKey: "kpi.ev_ebitda",
    format: "x",
    tooltipKey: "rating.neutral",
    rate: (v, t) =>
      v < 10
        ? { tone: "good", tag: t("rating.low") }
        : v < 20
        ? { tone: "neutral", tag: t("rating.medium") }
        : { tone: "bad", tag: t("rating.high") },
  },
  {
    key: "ebitda_margin",
    labelKey: "kpi.ebitda_margin",
    format: "%",
    tooltipKey: "rating.neutral",
    transform: (v) => v * 100,
    rate: (v, t) =>
      v > 25
        ? { tone: "good", tag: t("rating.strong") }
        : v > 12
        ? { tone: "neutral", tag: t("rating.healthy") }
        : { tone: "bad", tag: t("rating.low") },
  },
  {
    key: "roe",
    labelKey: "kpi.roe",
    format: "%",
    tooltipKey: "rating.neutral",
    transform: (v) => v * 100,
    rate: (v, t) =>
      v > 20
        ? { tone: "good", tag: t("rating.solid") }
        : v > 10
        ? { tone: "neutral", tag: t("rating.correct") }
        : { tone: "bad", tag: t("rating.low") },
  },
  {
    key: "net_margin",
    labelKey: "kpi.net_margin",
    format: "%",
    tooltipKey: "rating.neutral",
    transform: (v) => v * 100,
    rate: (v, t) =>
      v > 15
        ? { tone: "good", tag: t("rating.strong") }
        : v > 7
        ? { tone: "neutral", tag: t("rating.healthy") }
        : { tone: "bad", tag: t("rating.low") },
  },
  {
    key: "roic",
    labelKey: "kpi.roic",
    format: "%",
    tooltipKey: "rating.neutral",
    transform: (v) => v * 100,
    rate: (v, t) =>
      v > 15
        ? { tone: "good", tag: t("rating.solid") }
        : v > 8
        ? { tone: "neutral", tag: t("rating.correct") }
        : { tone: "bad", tag: t("rating.low") },
  },
  {
    key: "net_debt_ebitda",
    labelKey: "kpi.net_debt_ebitda",
    format: "x",
    tooltipKey: "rating.healthy",
    rate: (v, t) =>
      v < 1
        ? { tone: "good", tag: t("rating.healthy") }
        : v < 3
        ? { tone: "neutral", tag: t("rating.moderate") }
        : { tone: "bad", tag: t("rating.high") },
  },
  {
    key: "fcf_yield",
    labelKey: "kpi.fcf_yield",
    format: "%",
    tooltipKey: "rating.neutral",
    transform: (v) => v * 100,
    rate: (v, t) =>
      v > 5
        ? { tone: "good", tag: t("rating.strong") }
        : v > 2
        ? { tone: "neutral", tag: t("rating.neutral") }
        : { tone: "bad", tag: t("rating.low") },
  },
  {
    key: "gross_margin",
    labelKey: "kpi.gross_margin",
    format: "%",
    tooltipKey: "rating.neutral",
    transform: (v) => v * 100,
    rate: (v, t) =>
      v > 50
        ? { tone: "good", tag: t("rating.strong") }
        : v > 30
        ? { tone: "neutral", tag: t("rating.healthy") }
        : { tone: "bad", tag: t("rating.low") },
  },
  {
    key: "current_ratio",
    labelKey: "kpi.current_ratio",
    format: "raw",
    tooltipKey: "rating.healthy",
    rate: (v, t) =>
      v > 2
        ? { tone: "good", tag: t("rating.healthy") }
        : v > 1
        ? { tone: "neutral", tag: t("rating.correct") }
        : { tone: "bad", tag: t("rating.low") },
  },
  {
    key: "altman_z",
    labelKey: "kpi.altman_z",
    format: "raw",
    tooltipKey: "rating.safe",
    rate: (v, t) =>
      v > 2.99
        ? { tone: "good", tag: t("rating.healthy") }
        : v > 1.8
        ? { tone: "neutral", tag: t("rating.grey_zone") }
        : { tone: "bad", tag: t("rating.distress") },
  },
];

const toneClass: Record<Tone, string> = {
  good: "text-signal-buy",
  neutral: "text-ink-700",
  bad: "text-signal-sell",
};

export function KpiGrid({ ratios }: { ratios: YearRatios | null }) {
  const { t, locale } = useI18n();
  const decimalSep = locale === "fr" ? "," : ".";

  function formatVal(v: number | null | undefined, fmt: KpiDef["format"], transform?: KpiDef["transform"]) {
    if (v == null || isNaN(v)) return "—";
    const x = transform ? transform(v) : v;
    if (fmt === "x") return `${x.toFixed(2).replace(".", decimalSep)}x`;
    if (fmt === "%") return `${x.toFixed(1).replace(".", decimalSep)} %`;
    return x.toFixed(2).replace(".", decimalSep);
  }

  if (!ratios) {
    return (
      <div className="text-xs text-ink-400 italic">{t("rating.ratios_unavailable")}</div>
    );
  }

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
      {KPIS.map((k) => {
        const raw = ratios[k.key] as number | null | undefined;
        const transformed = raw != null && !isNaN(raw) ? (k.transform ? k.transform(raw) : raw) : null;
        const rating = transformed != null ? k.rate(transformed, t) : null;
        return (
          <div key={k.key as string} className="bg-white border border-ink-200 rounded-md px-2.5 py-2">
            <div className="text-[8px] font-semibold uppercase tracking-[1px] text-ink-500 mb-0.5 truncate">
              {t(k.labelKey)}
            </div>
            <div className={`text-sm font-bold font-mono ${rating ? toneClass[rating.tone] : "text-ink-400"}`}>
              {formatVal(raw, k.format, k.transform)}
            </div>
            <div className="text-[9px] text-ink-500 mt-0.5 truncate">
              {rating ? rating.tag : t(k.tooltipKey)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
