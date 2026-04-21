"use client";

import { useEffect, useState, use } from "react";
import { createClient } from "@/lib/supabase/client";
import { BackButton } from "@/components/back-button";
import { Activity, DollarSign, Zap, AlertTriangle, Clock, Database, FileOutput } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface Step {
  id: number;
  level: string;
  step_name: string;
  parent_id: number | null;
  provider: string | null;
  model: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  input_preview: string | null;
  output_preview: string | null;
  input_size: number;
  output_size: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  cache_hit: boolean;
  fallback_level: number;
  error_type: string | null;
  error_message: string | null;
  status: string;
  metadata: Record<string, unknown>;
}

interface Summary {
  total_ms: number;
  n_steps: number;
  n_errors: number;
  n_llm_calls: number;
  n_cache_hits: number;
  llm_ms: number;
  fetch_ms: number;
  writer_ms: number;
  total_cost_usd: number;
}

async function getToken(): Promise<string | null> {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token || null;
}

const LEVEL_COLORS: Record<string, string> = {
  root: "bg-ink-100 text-ink-900",
  node: "bg-navy-100 text-navy-700",
  llm: "bg-purple-100 text-purple-700",
  fetch: "bg-blue-100 text-blue-700",
  writer: "bg-amber-100 text-amber-700",
  cache: "bg-emerald-100 text-emerald-700",
  other: "bg-ink-50 text-ink-600",
};

const LEVEL_ICONS: Record<string, React.ReactNode> = {
  llm: <Zap className="w-3 h-3" />,
  fetch: <Activity className="w-3 h-3" />,
  writer: <FileOutput className="w-3 h-3" />,
  cache: <Database className="w-3 h-3" />,
};

export default function AdminTraceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [steps, setSteps] = useState<Step[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);

  async function loadOnce() {
    const token = await getToken();
    const r = await fetch(`${API}/admin/trace/${id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (r.ok) {
      const j = await r.json();
      setSteps(j.steps || []);
      setSummary(j.summary || null);
    }
    setLoading(false);
  }

  // SSE live : push nouveaux steps pendant que le job tourne
  useEffect(() => {
    loadOnce();
    let closed = false;
    try {
      const ev = new EventSource(`${API}/admin/trace/${id}/stream`);
      ev.onopen = () => setLive(true);
      ev.onmessage = (m) => {
        try {
          const row = JSON.parse(m.data);
          setSteps((prev) => {
            if (prev.some((x) => x.id === row.id)) {
              return prev.map((x) => (x.id === row.id ? row : x));
            }
            return [...prev, row];
          });
        } catch {
          /* heartbeat */
        }
      };
      ev.onerror = () => {
        ev.close();
        if (!closed) setLive(false);
      };
      return () => { closed = true; ev.close(); };
    } catch {
      /* SSE not supported */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Total par type (calculé côté client si summary manquant)
  const totals = summary || {
    total_ms: Math.max(...steps.map((s) => s.duration_ms || 0), 0),
    n_steps: steps.length,
    n_errors: steps.filter((s) => s.status === "error").length,
    n_llm_calls: steps.filter((s) => s.level === "llm").length,
    n_cache_hits: steps.filter((s) => s.cache_hit).length,
    llm_ms: steps.filter((s) => s.level === "llm").reduce((a, b) => a + (b.duration_ms || 0), 0),
    fetch_ms: steps.filter((s) => s.level === "fetch").reduce((a, b) => a + (b.duration_ms || 0), 0),
    writer_ms: steps.filter((s) => s.level === "writer").reduce((a, b) => a + (b.duration_ms || 0), 0),
    total_cost_usd: steps.reduce((a, b) => a + (Number(b.cost_usd) || 0), 0),
  };

  const maxDuration = Math.max(...steps.map((s) => s.duration_ms || 0), 1);

  return (
    <div className="min-h-screen bg-ink-50/30">
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-5">
        <BackButton fallback="/admin/traces" />

        <header className="flex items-start justify-between gap-6">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
              Trace — {id}
            </div>
            <h1 className="text-2xl font-bold text-ink-900">Timeline des steps</h1>
            <p className="text-sm text-ink-600 mt-1">
              {steps.length} steps · {totals.n_llm_calls} appels LLM · {totals.n_cache_hits} cache hits
              {totals.n_errors > 0 && (
                <span className="text-signal-sell font-semibold"> · {totals.n_errors} erreur(s)</span>
              )}
            </p>
          </div>
          {live && (
            <span className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-2 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              LIVE
            </span>
          )}
        </header>

        {/* KPI grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Kpi label="Total" value={`${(totals.total_ms / 1000).toFixed(1)}s`} />
          <Kpi label="Temps LLM" value={`${(totals.llm_ms / 1000).toFixed(1)}s`}
               hint={`${totals.n_llm_calls} appels`} color="purple" />
          <Kpi label="Temps Fetch" value={`${(totals.fetch_ms / 1000).toFixed(1)}s`} color="blue" />
          <Kpi label="Coût estimé" value={`$${Number(totals.total_cost_usd).toFixed(4)}`} color="amber" />
        </div>

        {loading && <div className="text-sm text-ink-500 italic">Chargement…</div>}

        {/* Timeline */}
        <div className="bg-white border border-ink-200 rounded-md overflow-hidden">
          <div className="px-4 py-2 border-b border-ink-100 text-[11px] font-semibold text-ink-500 uppercase tracking-wider">
            Timeline ({steps.length} steps)
          </div>
          <div className="divide-y divide-ink-100">
            {steps.map((s) => (
              <StepRow key={s.id} step={s} maxDuration={maxDuration} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, hint, color = "ink" }: {
  label: string; value: string; hint?: string; color?: string;
}) {
  const border = {
    ink: "border-ink-200 bg-white",
    purple: "border-purple-200 bg-purple-50",
    blue: "border-blue-200 bg-blue-50",
    amber: "border-amber-200 bg-amber-50",
  }[color] || "border-ink-200 bg-white";
  return (
    <div className={`rounded-md border ${border} p-3`}>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-500">{label}</div>
      <div className="text-xl font-mono font-bold text-ink-900 mt-0.5">{value}</div>
      {hint && <div className="text-[10px] text-ink-500 mt-0.5">{hint}</div>}
    </div>
  );
}

function StepRow({ step, maxDuration }: { step: Step; maxDuration: number }) {
  const [expanded, setExpanded] = useState(false);
  const pct = step.duration_ms ? (step.duration_ms / maxDuration) * 100 : 0;
  const colorClass = LEVEL_COLORS[step.level] || LEVEL_COLORS.other;
  const icon = LEVEL_ICONS[step.level];
  const isError = step.status === "error";
  return (
    <div className={isError ? "bg-red-50/40" : ""}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-2 hover:bg-ink-50 text-left"
      >
        <span className={`inline-flex items-center gap-1 text-[9px] font-bold uppercase rounded px-1.5 py-0.5 ${colorClass}`}>
          {icon}
          {step.level}
        </span>
        <span className="text-xs font-mono text-ink-800 flex-1 truncate">
          {step.step_name}
          {step.model && <span className="text-ink-500 ml-2">({step.model})</span>}
        </span>
        <div className="flex items-center gap-3 text-[10px] shrink-0">
          {step.tokens_in > 0 && (
            <span className="text-purple-600 font-mono">
              {step.tokens_in.toLocaleString()}↓/{step.tokens_out.toLocaleString()}↑
            </span>
          )}
          {step.cost_usd != null && Number(step.cost_usd) > 0 && (
            <span className="text-amber-700 font-mono">${Number(step.cost_usd).toFixed(4)}</span>
          )}
          {step.cache_hit && (
            <span className="text-emerald-700 text-[9px] font-semibold uppercase">cache</span>
          )}
          {isError && (
            <AlertTriangle className="w-3 h-3 text-signal-sell" />
          )}
          <span className="font-mono text-ink-600 min-w-[50px] text-right">
            {step.duration_ms != null ? `${step.duration_ms}ms` : "…"}
          </span>
        </div>
      </button>
      {/* Barre de proportion */}
      <div className="mx-4 mb-1 h-1 bg-ink-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${isError ? "bg-signal-sell" :
            step.level === "llm" ? "bg-purple-500" :
            step.level === "fetch" ? "bg-blue-500" :
            step.level === "writer" ? "bg-amber-500" : "bg-navy-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {expanded && (step.input_preview || step.output_preview || step.error_message) && (
        <div className="px-4 pb-3 space-y-2">
          {step.error_message && (
            <div className="bg-red-50 border border-red-200 rounded p-2 text-[11px] text-red-800">
              <div className="font-semibold mb-1">{step.error_type}</div>
              <div className="font-mono whitespace-pre-wrap">{step.error_message}</div>
            </div>
          )}
          {step.input_preview && (
            <div className="bg-ink-50 rounded p-2 text-[11px]">
              <div className="font-semibold text-ink-600 mb-1">Input ({step.input_size} chars)</div>
              <div className="font-mono whitespace-pre-wrap text-ink-700 max-h-40 overflow-auto">{step.input_preview}</div>
            </div>
          )}
          {step.output_preview && (
            <div className="bg-ink-50 rounded p-2 text-[11px]">
              <div className="font-semibold text-ink-600 mb-1">Output ({step.output_size} chars)</div>
              <div className="font-mono whitespace-pre-wrap text-ink-700 max-h-40 overflow-auto">{step.output_preview}</div>
            </div>
          )}
          {Object.keys(step.metadata || {}).length > 0 && (
            <div className="text-[10px] text-ink-500 font-mono">
              {JSON.stringify(step.metadata)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
