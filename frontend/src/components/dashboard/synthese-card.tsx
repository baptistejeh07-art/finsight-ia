import type { Synthesis } from "./types";

export function SyntheseCard({ synthesis }: { synthesis: Synthesis }) {
  // Construit une synthèse étoffée à partir de plusieurs champs du state
  const blocs: { title?: string; text: string }[] = [];

  const intro = synthesis.summary || synthesis.thesis;
  if (intro) blocs.push({ text: intro });

  if (synthesis.valuation_comment && synthesis.valuation_comment !== intro) {
    blocs.push({ title: "Valorisation", text: synthesis.valuation_comment });
  }
  if (synthesis.financial_commentary) {
    blocs.push({ title: "Lecture financière", text: synthesis.financial_commentary });
  }
  if (synthesis.peers_commentary) {
    blocs.push({ title: "Position concurrentielle", text: synthesis.peers_commentary });
  }
  if (synthesis.conclusion && synthesis.conclusion !== intro) {
    blocs.push({ title: "À retenir", text: synthesis.conclusion });
  }

  if (blocs.length === 0) return null;

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5 h-full overflow-auto">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
        Synthèse de l&apos;analyse
      </div>
      <div className="space-y-3">
        {blocs.map((b, i) => (
          <div key={i}>
            {b.title && (
              <div className="text-[10px] font-semibold uppercase tracking-[1px] text-ink-600 mb-1">
                {b.title}
              </div>
            )}
            <p className="text-sm text-ink-700 leading-relaxed whitespace-pre-line">
              {b.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
