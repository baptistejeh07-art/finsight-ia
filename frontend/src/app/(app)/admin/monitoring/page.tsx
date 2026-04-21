"use client";

import { useEffect, useState } from "react";
import { RefreshCw, AlertTriangle, CheckCircle, Clock, Zap } from "lucide-react";
import { BackButton } from "@/components/back-button";

interface MonitoringJob {
  job_id: string;
  kind: string;
  status: string;
  label?: string;
  started_at?: string;
  finished_at?: string;
  elapsed_ms?: number;
  timing?: Record<string, number>;
  synthesis_provider?: string;
  synthesis_provider_ms?: Record<string, number>;
  providers_failed?: string[];
  writers_ms?: { excel_ms?: number; pptx_ms?: number; pdf_ms?: number };
  warnings?: { field: string; severity: string; hint: string }[];
  error?: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "";

function fmtMs(ms?: number | null): string {
  if (!ms || ms < 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function statusColor(s: string): string {
  if (s === "done") return "text-signal-buy";
  if (s === "error") return "text-signal-sell";
  if (s === "running") return "text-signal-hold";
  return "text-ink-500";
}

export default function MonitoringPage() {
  const [jobs, setJobs] = useState<MonitoringJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [auto, setAuto] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/admin/monitoring?limit=30`);
      if (r.ok) {
        const d = await r.json();
        setJobs(d.jobs || []);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!auto) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [auto]);

  return (
    <div className="min-h-screen bg-ink-50/30">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <BackButton className="mb-4" fallback="/admin" />
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-ink-900">Monitoring jobs</h1>
            <p className="text-sm text-ink-500 mt-1">
              {jobs.length} job{jobs.length > 1 ? "s" : ""} récents · timings,
              provider LLM, warnings
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-ink-700 cursor-pointer">
              <input
                type="checkbox"
                checked={auto}
                onChange={(e) => setAuto(e.target.checked)}
              />
              Auto-refresh 5s
            </label>
            <button
              onClick={load}
              disabled={loading}
              className="btn-secondary !py-2 !px-3 inline-flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Stats globales */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <Stat label="Total" value={jobs.length} />
          <Stat label="Done" value={jobs.filter((j) => j.status === "done").length} color="text-signal-buy" />
          <Stat label="Error" value={jobs.filter((j) => j.status === "error").length} color="text-signal-sell" />
          <Stat label="Running" value={jobs.filter((j) => j.status === "running").length} color="text-signal-hold" />
          <Stat
            label="Médiane elapsed"
            value={(() => {
              const ms = jobs.filter((j) => j.elapsed_ms).map((j) => j.elapsed_ms!).sort((a, b) => a - b);
              return ms.length ? fmtMs(ms[Math.floor(ms.length / 2)]) : "—";
            })()}
          />
        </div>

        {/* Liste jobs */}
        <div className="space-y-3">
          {jobs.map((j) => (
            <JobCard key={j.job_id} job={j} />
          ))}
          {jobs.length === 0 && !loading && (
            <div className="text-center py-12 text-sm text-ink-500">
              Aucun job. Lance une analyse pour les voir apparaître ici.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color = "text-ink-900" }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="bg-white border border-ink-200 rounded-md p-3">
      <div className="text-2xs uppercase tracking-widest text-ink-500">{label}</div>
      <div className={`text-xl font-bold font-mono mt-1 ${color}`}>{value}</div>
    </div>
  );
}

function JobCard({ job }: { job: MonitoringJob }) {
  const t = job.timing || {};
  const w = job.writers_ms || {};
  const pms = job.synthesis_provider_ms || {};
  return (
    <div className="bg-white border border-ink-200 rounded-md p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs bg-ink-100 px-2 py-0.5 rounded">
              {job.kind}
            </span>
            <span className={`inline-flex items-center gap-1 text-xs font-semibold ${statusColor(job.status)}`}>
              {job.status === "done" && <CheckCircle className="w-3 h-3" />}
              {job.status === "error" && <AlertTriangle className="w-3 h-3" />}
              {job.status === "running" && <Clock className="w-3 h-3 animate-pulse" />}
              {job.status.toUpperCase()}
            </span>
            <span className="text-sm font-medium text-ink-900">{job.label || "—"}</span>
            {job.elapsed_ms && (
              <span className="text-xs text-ink-600 font-mono ml-auto">
                {fmtMs(job.elapsed_ms)}
              </span>
            )}
          </div>
          <div className="text-2xs text-ink-400 mt-1 font-mono truncate">
            {job.job_id}
          </div>
        </div>
      </div>

      {/* Erreur */}
      {job.error && (
        <div className="mb-3 px-3 py-2 bg-signal-sell/10 border border-signal-sell/20 rounded text-xs text-signal-sell">
          {job.error}
        </div>
      )}

      {/* Timing breakdown */}
      {Object.keys(t).length > 0 && (
        <div className="mb-3">
          <div className="text-2xs uppercase tracking-widest text-ink-500 mb-1.5">Timing par node</div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
            {Object.entries(t).map(([node, ms]) => {
              const pct = job.elapsed_ms ? (ms / job.elapsed_ms) * 100 : 0;
              const isHot = pct > 30;
              return (
                <div key={node} className={`text-xs px-2 py-1.5 rounded border ${isHot ? "border-signal-sell/40 bg-signal-sell/5" : "border-ink-200"}`}>
                  <div className="text-2xs text-ink-500 truncate">{node.replace("_node", "")}</div>
                  <div className={`font-mono ${isHot ? "text-signal-sell font-bold" : "text-ink-900"}`}>
                    {fmtMs(ms)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Synthesis provider */}
      {job.synthesis_provider && (
        <div className="mb-3 flex items-center gap-2 text-xs">
          <Zap className="w-3 h-3 text-ink-400" />
          <span className="text-ink-500">Synthesis →</span>
          <span className="font-mono font-semibold text-ink-900">{job.synthesis_provider}</span>
          {Object.keys(pms).length > 0 && (
            <span className="text-ink-400 font-mono">
              ({Object.entries(pms).map(([p, ms]) => `${p}:${fmtMs(ms)}`).join(" · ")})
            </span>
          )}
          {job.providers_failed && job.providers_failed.length > 0 && (
            <span className="text-signal-sell text-2xs">⚠ failed: {job.providers_failed.join(", ")}</span>
          )}
        </div>
      )}

      {/* Writers breakdown */}
      {(w.excel_ms || w.pptx_ms || w.pdf_ms) && (
        <div className="mb-3 flex items-center gap-3 text-xs">
          <span className="text-ink-500">Writers →</span>
          <span className="font-mono text-ink-700">XLSX: {fmtMs(w.excel_ms)}</span>
          <span className="font-mono text-ink-700">PPTX: {fmtMs(w.pptx_ms)}</span>
          <span className="font-mono text-ink-700">PDF: {fmtMs(w.pdf_ms)}</span>
        </div>
      )}

      {/* Warnings */}
      {job.warnings && job.warnings.length > 0 && (
        <div>
          <div className="text-2xs uppercase tracking-widest text-ink-500 mb-1.5">
            Warnings audit ({job.warnings.length})
          </div>
          <div className="space-y-1">
            {job.warnings.map((wn, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-ink-700">
                <span className={`text-2xs uppercase font-semibold px-1.5 py-0.5 rounded ${
                  wn.severity === "error" ? "bg-signal-sell/15 text-signal-sell"
                  : wn.severity === "warning" ? "bg-signal-hold/15 text-signal-hold"
                  : "bg-ink-200 text-ink-600"
                }`}>
                  {wn.severity}
                </span>
                <span>
                  <code className="text-2xs bg-ink-100 px-1 py-0.5 rounded mr-1">{wn.field}</code>
                  {wn.hint}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
