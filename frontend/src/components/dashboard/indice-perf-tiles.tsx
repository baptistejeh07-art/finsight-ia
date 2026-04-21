"use client";

/**
 * Tuiles de performance agrégées pour un indice (YTD / 1A / 3A / 5A / Vol / Sharpe / Max DD).
 *
 * Lit indifféremment :
 *   - result.data.indice_stats.{perf_ytd, perf_1y, perf_3y, perf_5y, vol_1y, sharpe_1y, max_dd}
 *   - result.data.{perf_ytd, perf_1y, ...} (flat)
 * Les valeurs peuvent être en décimal (0.12) ou en pourcent (12) — détection auto.
 */

interface Props {
  stats: Record<string, unknown> | null | undefined;
  label?: string;
}

function toPct(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
  if (!isFinite(n)) return null;
  // Si valeur abs < 2 → décimale, sinon déjà en %
  return Math.abs(n) < 2 ? n * 100 : n;
}

function fmtPct(v: number | null, signed = true): string {
  if (v == null) return "—";
  const sign = signed && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1).replace(".", ",")} %`;
}

function fmtNum(v: unknown, decimals = 2): string {
  if (v == null) return "—";
  const n = typeof v === "number" ? v : parseFloat(String(v));
  if (!isFinite(n)) return "—";
  return n.toFixed(decimals).replace(".", ",");
}

function cls(v: number | null): string {
  if (v == null) return "text-ink-700";
  return v >= 0 ? "text-signal-buy" : "text-signal-sell";
}

export function IndicePerfTiles({ stats, label }: Props) {
  const s = (stats || {}) as Record<string, unknown>;

  const ytd = toPct(s.perf_ytd);
  const p1y = toPct(s.perf_1y);
  const p3y = toPct(s.perf_3y);
  const p5y = toPct(s.perf_5y);
  const vol = toPct(s.vol_1y);
  const mdd = toPct(s.max_dd);
  const sharpe = s.sharpe_1y != null ? Number(s.sharpe_1y) : null;

  const allNull = [ytd, p1y, p3y, p5y, vol, mdd, sharpe].every(
    (x) => x == null || (typeof x === "number" && !isFinite(x))
  );

  if (allNull) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-5 h-full flex items-center justify-center">
        <span className="text-xs text-ink-400">Aucune statistique de performance disponible</span>
      </div>
    );
  }

  const tiles: Array<{ k: string; v: string; color: string }> = [
    { k: "YTD", v: fmtPct(ytd), color: cls(ytd) },
    { k: "1 an", v: fmtPct(p1y), color: cls(p1y) },
    { k: "3 ans", v: fmtPct(p3y), color: cls(p3y) },
    { k: "5 ans", v: fmtPct(p5y), color: cls(p5y) },
    { k: "Volatilité 1A", v: vol != null ? fmtPct(vol, false) : "—", color: "text-ink-800" },
    { k: "Sharpe 1A", v: sharpe != null && isFinite(sharpe) ? fmtNum(sharpe) : "—", color: "text-ink-800" },
    { k: "Max Drawdown", v: fmtPct(mdd), color: cls(mdd) },
  ];

  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Performance agrégée{label ? ` — ${label}` : ""}
        </div>
      </div>
      <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-2 px-3 pb-3 content-start">
        {tiles.map((t) => (
          <div
            key={t.k}
            className="bg-ink-50 border border-ink-100 rounded-md px-2.5 py-2"
          >
            <div className="text-[9px] uppercase tracking-wider text-ink-500 font-semibold">
              {t.k}
            </div>
            <div className={`font-mono text-sm font-semibold mt-0.5 ${t.color}`}>
              {t.v}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
