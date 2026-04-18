import type { Synthesis } from "./types";

export function SyntheseCard({ synthesis }: { synthesis: Synthesis }) {
  const summary = synthesis.summary || synthesis.thesis || synthesis.conclusion;
  if (!summary) return null;

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
        Synthèse de l&apos;analyse
      </div>
      <p className="text-sm text-ink-700 leading-relaxed whitespace-pre-line">{summary}</p>
    </div>
  );
}
