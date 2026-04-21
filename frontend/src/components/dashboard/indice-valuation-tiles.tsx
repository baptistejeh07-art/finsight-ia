"use client";

/**
 * Tuiles de valorisation agrégée d'un indice : P/E, P/B, Dividend Yield, ERP.
 * Source prioritaire : result.data.indice_stats ; fallback flat data.
 */

interface Props {
  stats: Record<string, unknown> | null | undefined;
  label?: string;
}

function fmtX(v: unknown): string {
  if (v == null) return "—";
  const n = typeof v === "number" ? v : parseFloat(String(v));
  if (!isFinite(n) || n <= 0) return "—";
  return `${n.toFixed(1).replace(".", ",")}x`;
}

function fmtPct(v: unknown): string {
  if (v == null) return "—";
  const n = typeof v === "number" ? v : parseFloat(String(v));
  if (!isFinite(n)) return "—";
  const pct = Math.abs(n) < 1 ? n * 100 : n;
  return `${pct.toFixed(2).replace(".", ",")} %`;
}

export function IndiceValuationTiles({ stats, label }: Props) {
  const s = (stats || {}) as Record<string, unknown>;
  const pe = s.pe_median ?? s.pe_fwd ?? s.pe ?? s.pe_ratio;
  const pb = s.pb_median ?? s.pb;
  const dy = s.div_yield ?? s.dividend_yield ?? s.dy;
  const erpRaw = s.erp;

  const hasAny =
    pe != null || pb != null || dy != null || erpRaw != null;

  if (!hasAny) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">Valorisation indisponible</span>
      </div>
    );
  }

  // ERP peut être une string du backend ("+2,4 %") ou un nombre décimal
  let erpStr = "—";
  if (typeof erpRaw === "string" && erpRaw.trim() && erpRaw !== "—") {
    erpStr = erpRaw;
  } else if (typeof erpRaw === "number" && isFinite(erpRaw)) {
    erpStr = fmtPct(erpRaw);
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Valorisation agrégée{label ? ` — ${label}` : ""}
        </div>
      </div>
      <div className="flex-1 grid grid-cols-2 gap-2 px-3 pb-3 content-start">
        <Tile label="P/E médian" value={fmtX(pe)} />
        <Tile label="P/B médian" value={fmtX(pb)} />
        <Tile label="Rendement div." value={fmtPct(dy)} />
        <Tile label="Prime de risque" value={erpStr} />
      </div>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-ink-50 border border-ink-100 rounded-md px-2.5 py-2">
      <div className="text-[9px] uppercase tracking-wider text-ink-500 font-semibold">
        {label}
      </div>
      <div className="font-mono text-sm font-semibold mt-0.5 text-ink-900">
        {value}
      </div>
    </div>
  );
}
