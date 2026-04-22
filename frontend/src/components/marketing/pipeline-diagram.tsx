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
  { id: "fetch",      label: "fetch_node",      role: "Agent Data — yfinance, Finnhub, FMP, Pappers, INPI",               x: 40,   y: 50,  color: "input" },
  { id: "fallback",   label: "fallback_node",   role: "Backup multi-API si fetch primaire échoue",                         x: 40,   y: 200, color: "fallback" },
  { id: "quant",      label: "quant_node",      role: "Agent Quant — WACC, DCF, ratios déterministes",                     x: 310,  y: 125, color: "process" },
  { id: "synthesis",  label: "synthesis_node",  role: "Agent Synthèse — LLM Groq/Mistral (reco, conviction, targets)",     x: 580,  y: 125, color: "llm" },
  { id: "retry",      label: "synthesis_retry", role: "Retry LLM si sortie JSON invalide",                                 x: 580,  y: 275, color: "llm" },
  { id: "qa",         label: "qa_node",         role: "Agent QA Python + QA Haiku — validation ratios et cohérence",       x: 850,  y: 125, color: "qa" },
  { id: "devil",      label: "devil_node",      role: "Devil's Advocate — thèse inverse (parallèle QA)",                   x: 850,  y: 275, color: "qa" },
  { id: "entry",      label: "entry_zone_node", role: "Agent Entry Zone — signal d'entrée (DCF vs cours)",                 x: 1120, y: 125, color: "qa" },
  { id: "output",     label: "output_node",     role: "Writers PDF / PPTX / Excel / Briefing",                             x: 1390, y: 125, color: "output" },
  { id: "blocked",    label: "blocked_node",    role: "Court-circuit si synthesis invalide → livrables partiels",          x: 580,  y: 400, color: "fallback" },
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

const NODE_W = 240;
const NODE_H = 88;

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
        viewBox="0 0 1680 540"
        className="w-full min-w-[1100px]"
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
                y={n.y + 30}
                textAnchor="middle"
                fontSize="15"
                fontWeight="700"
                fontFamily="ui-monospace, monospace"
                fill={c.text}
              >
                {n.label}
              </text>
              <text
                x={n.x + NODE_W / 2}
                y={n.y + 56}
                textAnchor="middle"
                fontSize="11"
                fontFamily="system-ui, sans-serif"
                fill={c.text}
              >
                {truncate(n.role, 48)}
              </text>
              <text
                x={n.x + NODE_W / 2}
                y={n.y + 74}
                textAnchor="middle"
                fontSize="11"
                fontFamily="system-ui, sans-serif"
                fill={c.text}
              >
                {tailText(n.role, 48)}
              </text>
            </g>
          );
        })}

        {/* Légende */}
        <g transform="translate(40, 500)">
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
              <g key={l.color} transform={`translate(${i * 260}, 0)`}>
                <rect width={18} height={18} rx={4} fill={c.fill} stroke={c.stroke} strokeWidth={1.5} />
                <text x={26} y={14} fontSize="13" fill="#374151" fontFamily="system-ui, sans-serif">
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
  if (s.length <= n) return s;
  // Coupe sur un mot entier pour la première ligne
  const cut = s.slice(0, n).lastIndexOf(" ");
  return s.slice(0, cut > 0 ? cut : n);
}

function tailText(s: string, headLen: number): string {
  if (s.length <= headLen) return "";
  const cut = s.slice(0, headLen).lastIndexOf(" ");
  const tail = s.slice(cut > 0 ? cut + 1 : headLen);
  return tail.length > 48 ? tail.slice(0, 47) + "…" : tail;
}
