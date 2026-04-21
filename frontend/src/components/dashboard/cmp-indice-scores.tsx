"use client";

/**
 * Scores A/B avec signal (Surpondérer / Neutre / Sous-pondérer).
 */

interface Props {
  data: Record<string, unknown>;
  nameA: string;
  nameB: string;
}

function scoreColor(s: number | null | undefined): string {
  if (s == null || !isFinite(s as number)) return "bg-ink-200 text-ink-700";
  const n = s as number;
  if (n >= 65) return "bg-green-100 text-green-800 border-green-300";
  if (n >= 45) return "bg-amber-100 text-amber-800 border-amber-300";
  return "bg-red-100 text-red-800 border-red-300";
}

function signalColor(sig: string | undefined): string {
  if (!sig) return "text-ink-600";
  const low = sig.toLowerCase();
  if (low.includes("surp")) return "text-signal-buy";
  if (low.includes("sous")) return "text-signal-sell";
  return "text-ink-600";
}

function Panel({ name, score, signal }: { name: string; score: number | null; signal?: string }) {
  return (
    <div className="flex-1 bg-white border border-ink-100 rounded-md p-4 flex flex-col items-center justify-center">
      <div className="text-[10px] uppercase tracking-[1.5px] text-ink-500 font-semibold">{name}</div>
      <div
        className={`mt-3 px-6 py-4 border rounded-full text-3xl font-bold font-mono ${scoreColor(score)}`}
      >
        {score == null ? "—" : Math.round(score)}
      </div>
      <div className="text-[9px] text-ink-400 mt-1">/ 100</div>
      <div className={`mt-2 text-xs font-semibold ${signalColor(signal)}`}>
        {signal || "—"}
      </div>
    </div>
  );
}

export function CmpIndiceScores({ data, nameA, nameB }: Props) {
  const sA = typeof data.score_a === "number" ? data.score_a : Number(data.score_a) || null;
  const sB = typeof data.score_b === "number" ? data.score_b : Number(data.score_b) || null;
  const sigA = (data.signal_a as string) || undefined;
  const sigB = (data.signal_b as string) || undefined;

  return (
    <div className="bg-white border border-ink-200 rounded-md h-full flex flex-col overflow-hidden">
      <div className="px-3 pt-2.5 pb-1.5 flex-none">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Score composite — verdict
        </div>
      </div>
      <div className="flex-1 flex gap-3 px-3 pb-3">
        <Panel name={nameA} score={sA} signal={sigA} />
        <Panel name={nameB} score={sB} signal={sigB} />
      </div>
    </div>
  );
}
