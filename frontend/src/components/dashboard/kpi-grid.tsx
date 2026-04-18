import type { YearRatios } from "./types";

type Tone = "good" | "neutral" | "bad";

interface KpiDef {
  key: keyof YearRatios;
  label: string;
  format: "x" | "%" | "raw";
  tooltip: string;
  // value transform
  transform?: (v: number) => number;
  rate: (v: number) => { tone: Tone; tag: string };
}

const KPIS: KpiDef[] = [
  {
    key: "pe_ratio",
    label: "P/E Ratio",
    format: "x",
    tooltip: "Valeur actuelle",
    rate: (v) => (v < 15 ? { tone: "good", tag: "Faible" } : v < 30 ? { tone: "neutral", tag: "Neutre" } : { tone: "bad", tag: "Élevé" }),
  },
  {
    key: "ev_ebitda",
    label: "EV / EBITDA",
    format: "x",
    tooltip: "Multiple entreprise",
    rate: (v) => (v < 10 ? { tone: "good", tag: "Faible" } : v < 20 ? { tone: "neutral", tag: "Moyen" } : { tone: "bad", tag: "Élevé" }),
  },
  {
    key: "ebitda_margin",
    label: "Marge EBITDA",
    format: "%",
    tooltip: "Secteur ref",
    transform: (v) => v * 100,
    rate: (v) => (v > 25 ? { tone: "good", tag: "Fort" } : v > 12 ? { tone: "neutral", tag: "Sain" } : { tone: "bad", tag: "Faible" }),
  },
  {
    key: "roe",
    label: "ROE",
    format: "%",
    tooltip: "Return on Equity",
    transform: (v) => v * 100,
    rate: (v) => (v > 20 ? { tone: "good", tag: "Solide" } : v > 10 ? { tone: "neutral", tag: "Correct" } : { tone: "bad", tag: "Faible" }),
  },
  {
    key: "net_margin",
    label: "Marge nette",
    format: "%",
    tooltip: "Net Income / Revenue",
    transform: (v) => v * 100,
    rate: (v) => (v > 15 ? { tone: "good", tag: "Fort" } : v > 7 ? { tone: "neutral", tag: "Sain" } : { tone: "bad", tag: "Faible" }),
  },
  {
    key: "roic",
    label: "ROIC",
    format: "%",
    tooltip: "Return on Invested Capital",
    transform: (v) => v * 100,
    rate: (v) => (v > 15 ? { tone: "good", tag: "Solide" } : v > 8 ? { tone: "neutral", tag: "Correct" } : { tone: "bad", tag: "Faible" }),
  },
  {
    key: "net_debt_ebitda",
    label: "Dette N. / EBITDA",
    format: "x",
    tooltip: "Levier · Sain < 3",
    rate: (v) => (v < 1 ? { tone: "good", tag: "Sain" } : v < 3 ? { tone: "neutral", tag: "Modéré" } : { tone: "bad", tag: "Élevé" }),
  },
  {
    key: "fcf_yield",
    label: "Free Cash Flow",
    format: "%",
    tooltip: "FCF Yield",
    transform: (v) => v * 100,
    rate: (v) => (v > 5 ? { tone: "good", tag: "Fort" } : v > 2 ? { tone: "neutral", tag: "Neutre" } : { tone: "bad", tag: "Faible" }),
  },
  {
    key: "gross_margin",
    label: "Marge brute",
    format: "%",
    tooltip: "Gross Profit / Revenue",
    transform: (v) => v * 100,
    rate: (v) => (v > 50 ? { tone: "good", tag: "Fort" } : v > 30 ? { tone: "neutral", tag: "Sain" } : { tone: "bad", tag: "Faible" }),
  },
  {
    key: "current_ratio",
    label: "Current Ratio",
    format: "raw",
    tooltip: ">1.0 sain · >2.0 fort",
    rate: (v) => (v > 1.5 ? { tone: "good", tag: "Sain" } : v > 1 ? { tone: "neutral", tag: "Correct" } : { tone: "bad", tag: "Tendu" }),
  },
  {
    key: "revenue_growth",
    label: "Croissance CA",
    format: "%",
    tooltip: "YoY vs exercice précédent",
    transform: (v) => v * 100,
    rate: (v) => (v > 10 ? { tone: "good", tag: "Fort" } : v > 0 ? { tone: "neutral", tag: "Positif" } : { tone: "bad", tag: "Recul" }),
  },
  {
    key: "altman_z",
    label: "Altman Z-Score",
    format: "raw",
    tooltip: ">2.99 Sain · <1.8 Détresse",
    rate: (v) => (v > 2.99 ? { tone: "good", tag: "Sain" } : v > 1.8 ? { tone: "neutral", tag: "Zone grise" } : { tone: "bad", tag: "Détresse" }),
  },
];

const toneClass: Record<Tone, string> = {
  good: "text-signal-buy",
  neutral: "text-ink-700",
  bad: "text-signal-sell",
};

function formatVal(v: number | null | undefined, fmt: KpiDef["format"], transform?: KpiDef["transform"]) {
  if (v == null || isNaN(v)) return "—";
  const x = transform ? transform(v) : v;
  if (fmt === "x") return `${x.toFixed(2).replace(".", ",")}x`;
  if (fmt === "%") return `${x.toFixed(1).replace(".", ",")} %`;
  return x.toFixed(2).replace(".", ",");
}

export function KpiGrid({ ratios }: { ratios: YearRatios | null }) {
  if (!ratios) {
    return (
      <div className="text-xs text-ink-400 italic">Ratios indisponibles</div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      {KPIS.map((k) => {
        const raw = ratios[k.key] as number | null | undefined;
        const transformed = raw != null && !isNaN(raw) ? (k.transform ? k.transform(raw) : raw) : null;
        const rating = transformed != null ? k.rate(transformed) : null;
        return (
          <div key={k.key as string} className="bg-white border border-ink-200 rounded-md p-3.5">
            <div className="text-[9px] font-semibold uppercase tracking-[1.2px] text-ink-500 mb-1.5">
              {k.label}
            </div>
            <div className={`text-lg font-bold font-mono ${rating ? toneClass[rating.tone] : "text-ink-400"}`}>
              {formatVal(raw, k.format, k.transform)}
            </div>
            <div className="text-[10px] text-ink-500 mt-1">
              {k.tooltip} {rating ? `· ${rating.tag}` : ""}
            </div>
          </div>
        );
      })}
    </div>
  );
}
