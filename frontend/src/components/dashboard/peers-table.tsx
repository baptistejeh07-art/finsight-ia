import type { PeerData, YearRatios } from "./types";

interface Props {
  peers: PeerData[];
  targetTicker: string;
  targetName: string;
  targetRatios?: YearRatios | null;
}

function median(arr: number[]): number | null {
  const xs = arr.filter((x) => x != null && !isNaN(x)).sort((a, b) => a - b);
  if (!xs.length) return null;
  const mid = Math.floor(xs.length / 2);
  return xs.length % 2 ? xs[mid] : (xs[mid - 1] + xs[mid]) / 2;
}

function fmtX(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return "—";
  return `${v.toFixed(1).replace(".", ",")}x`;
}
function fmtP(v: number | null | undefined): string {
  // Valeur déjà en pourcent (peers stockent 68.0, pas 0.68)
  if (v == null || isNaN(v)) return "—";
  return `${v.toFixed(1).replace(".", ",")} %`;
}

export function PeersTable({ peers, targetTicker, targetName, targetRatios }: Props) {
  // target stocke gross_margin en décimal (0.469) → on convertit en pourcent
  // pour aligner avec les peers (qui stockent 68.0)
  const targetRow: PeerData = {
    name: `${targetName} (cible)`,
    ticker: targetTicker,
    ev_ebitda: targetRatios?.ev_ebitda ?? null,
    ev_revenue: targetRatios?.ev_revenue ?? null,
    pe: targetRatios?.pe_ratio ?? null,
    gross_margin: targetRatios?.gross_margin != null ? targetRatios.gross_margin * 100 : null,
    ebitda_margin: targetRatios?.ebitda_margin != null ? targetRatios.ebitda_margin * 100 : null,
    market_cap_mds: targetRatios?.market_cap ? targetRatios.market_cap / 1000 : null,
  };

  const all = [targetRow, ...peers];

  const med: PeerData = {
    name: "Médiane pairs",
    ticker: "",
    ev_ebitda: median(peers.map((p) => Number(p.ev_ebitda || NaN))),
    ev_revenue: median(peers.map((p) => Number(p.ev_revenue || NaN))),
    pe: median(peers.map((p) => Number(p.pe || NaN))),
    gross_margin: median(peers.map((p) => Number(p.gross_margin || NaN))),
    ebitda_margin: median(peers.map((p) => Number(p.ebitda_margin || NaN))),
  };

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden">
      <div className="px-3 pt-2.5 pb-1.5">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Comparatif sectoriel
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead className="bg-ink-50 text-ink-600">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold">Société</th>
              <th className="text-right px-2 py-1.5 font-semibold">EV/EBITDA</th>
              <th className="text-right px-2 py-1.5 font-semibold">EV/Rev</th>
              <th className="text-right px-2 py-1.5 font-semibold">P/E</th>
              <th className="text-right px-2 py-1.5 font-semibold">Marge brute</th>
              <th className="text-right px-2 py-1.5 font-semibold">Marge EBITDA</th>
            </tr>
          </thead>
          <tbody>
            {all.map((p, i) => (
              <tr
                key={`${p.ticker}-${i}`}
                className={`border-t border-ink-100 ${
                  i === 0 ? "font-bold bg-navy-50/30" : ""
                }`}
              >
                <td className="px-3 py-1.5 text-ink-900">{p.name}</td>
                <td className="px-2 py-1.5 text-right font-mono">{fmtX(p.ev_ebitda)}</td>
                <td className="px-2 py-1.5 text-right font-mono">{fmtX(p.ev_revenue)}</td>
                <td className="px-2 py-1.5 text-right font-mono">{fmtX(p.pe)}</td>
                <td className="px-2 py-1.5 text-right font-mono">{fmtP(p.gross_margin)}</td>
                <td className="px-2 py-1.5 text-right font-mono">{fmtP(p.ebitda_margin)}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-ink-200 italic text-ink-600">
              <td className="px-3 py-1.5">{med.name}</td>
              <td className="px-2 py-1.5 text-right font-mono">{fmtX(med.ev_ebitda)}</td>
              <td className="px-2 py-1.5 text-right font-mono">{fmtX(med.ev_revenue)}</td>
              <td className="px-2 py-1.5 text-right font-mono">{fmtX(med.pe)}</td>
              <td className="px-2 py-1.5 text-right font-mono">{fmtP(med.gross_margin)}</td>
              <td className="px-2 py-1.5 text-right font-mono">{fmtP(med.ebitda_margin)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="px-3 py-1.5 text-[10px] text-ink-400 italic border-t border-ink-100">
        Source : FinSight IA — yfinance + FMP, peers générés par le pipeline
      </div>
    </div>
  );
}
