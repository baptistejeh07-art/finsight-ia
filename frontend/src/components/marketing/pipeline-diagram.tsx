/**
 * Diagramme LangGraph FinSight — pipeline 10 nœuds.
 * SVG inline pour rester léger (pas de dépendance Mermaid/D3).
 */

interface NodeDef {
  id: string;
  label: string;
  role: string;
  x: number;
  y: number;
  color: "input" | "process" | "llm" | "qa" | "output" | "fallback";
}

const NODES: NodeDef[] = [
  { id: "fetch",      label: "fetch_node",      role: "Agent Data — yfinance, Finnhub, FMP, Pappers, INPI",               x: 50,  y: 40,  color: "input" },
  { id: "fallback",   label: "fallback_node",   role: "Backup multi-API si fetch primaire échoue",                         x: 50,  y: 140, color: "fallback" },
  { id: "quant",      label: "quant_node",      role: "Agent Quant — WACC, DCF, ratios déterministes",                     x: 280, y: 90,  color: "process" },
  { id: "synthesis",  label: "synthesis_node",  role: "Agent Synthèse — LLM Groq/Mistral (recommandation, targets)",       x: 510, y: 90,  color: "llm" },
  { id: "retry",      label: "synthesis_retry", role: "Retry LLM en cas de sortie invalide",                               x: 510, y: 190, color: "llm" },
  { id: "qa",         label: "qa_node",         role: "Agent QA Python + QA Haiku — validation ratios, cohérence",         x: 740, y: 90,  color: "qa" },
  { id: "devil",      label: "devil_node",      role: "Devil's Advocate — thèse inverse, conviction_delta (parallèle QA)", x: 740, y: 190, color: "qa" },
  { id: "entry",      label: "entry_zone_node", role: "Agent Entry Zone — signal d'entrée (DCF vs cours)",                 x: 970, y: 90,  color: "qa" },
  { id: "output",     label: "output_node",     role: "Writers PDF / PPTX / Excel / Briefing — production livrables",      x: 1200, y: 90, color: "output" },
  { id: "blocked",    label: "blocked_node",    role: "Court-circuit si synthesis invalide → livrables partiels",          x: 510, y: 290, color: "fallback" },
];

const EDGES: [string, string, boolean?][] = [
  ["fetch", "quant"],
  ["fetch", "fallback", true],
  ["fallback", "quant"],
  ["quant", "synthesis"],
  ["synthesis", "qa"],
  ["synthesis", "blocked", true],
  ["qa", "retry", true],
  ["retry", "qa"],
  ["qa", "devil"],
  ["qa", "entry"],
  ["entry", "output"],
  ["blocked", "output"],
];

const COLOR_MAP = {
  input:    { fill: "#DBEAFE", stroke: "#1B3A6B", text: "#1B3A6B" },
  process:  { fill: "#E0E7FF", stroke: "#3730A3", text: "#312E81" },
  llm:      { fill: "#FCE7F3", stroke: "#9F1239", text: "#881337" },
  qa:       { fill: "#D1FAE5", stroke: "#065F46", text: "#064E3B" },
  output:   { fill: "#FEF3C7", stroke: "#92400E", text: "#78350F" },
  fallback: { fill: "#F3F4F6", stroke: "#6B7280", text: "#374151" },
};

const NODE_W = 180;
const NODE_H = 60;

export function PipelineDiagram() {
  const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]));

  function edgePath(fromId: string, toId: string): string {
    const f = nodeById[fromId];
    const t = nodeById[toId];
    const x1 = f.x + NODE_W / 2;
    const y1 = f.y + NODE_H;
    const x2 = t.x + NODE_W / 2;
    const y2 = t.y;
    const dx = x2 - x1;
    const dy = y2 - y1;
    if (Math.abs(dx) < 5) {
      return `M ${x1} ${y1} L ${x2} ${y2}`;
    }
    const midY = y1 + dy / 2;
    return `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;
  }

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox="0 0 1400 370"
        className="w-full min-w-[900px]"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Diagramme du pipeline LangGraph FinSight"
      >
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#6B7280" />
          </marker>
          <marker id="arrowDashed" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#9CA3AF" />
          </marker>
        </defs>

        {/* Edges */}
        {EDGES.map(([from, to, dashed]) => (
          <path
            key={`${from}-${to}`}
            d={edgePath(from, to)}
            stroke={dashed ? "#9CA3AF" : "#6B7280"}
            strokeWidth={dashed ? 1.2 : 1.8}
            strokeDasharray={dashed ? "4 4" : undefined}
            fill="none"
            markerEnd={dashed ? "url(#arrowDashed)" : "url(#arrow)"}
          />
        ))}

        {/* Nodes */}
        {NODES.map((n) => {
          const c = COLOR_MAP[n.color];
          return (
            <g key={n.id}>
              <rect
                x={n.x}
                y={n.y}
                width={NODE_W}
                height={NODE_H}
                rx={8}
                fill={c.fill}
                stroke={c.stroke}
                strokeWidth={1.5}
              />
              <text
                x={n.x + NODE_W / 2}
                y={n.y + 22}
                textAnchor="middle"
                fontSize="12"
                fontWeight="700"
                fontFamily="ui-monospace, monospace"
                fill={c.text}
              >
                {n.label}
              </text>
              <text
                x={n.x + NODE_W / 2}
                y={n.y + 42}
                textAnchor="middle"
                fontSize="9"
                fontFamily="system-ui, sans-serif"
                fill={c.text}
              >
                {truncate(n.role, 38)}
              </text>
            </g>
          );
        })}

        {/* Légende */}
        <g transform="translate(50, 330)">
          {[
            { label: "Fetch / Données",          color: "input" as const },
            { label: "Calcul déterministe",      color: "process" as const },
            { label: "Appel LLM",                color: "llm" as const },
            { label: "Contrôle qualité",         color: "qa" as const },
            { label: "Production livrables",     color: "output" as const },
            { label: "Fallback / dégradé",       color: "fallback" as const },
          ].map((l, i) => {
            const c = COLOR_MAP[l.color];
            return (
              <g key={l.color} transform={`translate(${i * 215}, 0)`}>
                <rect width={14} height={14} rx={3} fill={c.fill} stroke={c.stroke} />
                <text x={20} y={11} fontSize="11" fill="#374151" fontFamily="system-ui, sans-serif">
                  {l.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="mt-3 text-xs text-text-secondary italic leading-relaxed">
        Pipeline compilé avec LangGraph&nbsp;0.6. Chaque nœud est wrappé dans un tracer pour
        instrumentation niveau&nbsp;3 (latence, erreurs, provider LLM utilisé). Les flèches pointillées
        représentent des chemins conditionnels (échec fetch, retry LLM, court-circuit).
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
