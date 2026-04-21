"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { BackButton } from "@/components/back-button";
import { Activity, DollarSign, Zap, AlertTriangle, Clock } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface TraceSummary {
  job_id: string;
  kind: string | null;
  label: string | null;
  started_at: string;
  finished_at: string | null;
  total_ms: number | null;
  n_steps: number;
  n_errors: number;
  n_llm_calls: number;
  n_cache_hits: number;
  llm_ms: number | null;
  fetch_ms: number | null;
  writer_ms: number | null;
  total_tokens_in: number | null;
  total_tokens_out: number | null;
  total_cost_usd: number | null;
}

async function getToken(): Promise<string | null> {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token || null;
}

export default function AdminTracesPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      const r = await fetch(`${API}/admin/traces?limit=50`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (r.ok) {
        const j = await r.json();
        setTraces(j.traces || []);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="min-h-screen bg-ink-50/30">
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        <BackButton fallback="/admin" />

        <header>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
            Observability
          </div>
          <h1 className="text-2xl font-bold text-ink-900">
            Traces d&apos;analyses (profiling)
          </h1>
          <p className="text-sm text-ink-600 mt-1">
            Chaque ligne = un job analysé. Durées par type (LLM / fetch / writer), tokens
            consommés, coût USD estimé, erreurs. Clic pour timeline détaillée.
          </p>
        </header>

        {loading ? (
          <div className="text-sm text-ink-500 italic">Chargement…</div>
        ) : traces.length === 0 ? (
          <div className="text-sm text-ink-500 italic">
            Aucune trace encore — lancez une analyse pour voir les steps apparaître ici.
          </div>
        ) : (
          <div className="bg-white border border-ink-200 rounded-md overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-ink-50 text-ink-600 border-b border-ink-200">
                <tr>
                  <th className="text-left px-3 py-2 font-semibold">Job</th>
                  <th className="text-left px-2 py-2 font-semibold">Kind</th>
                  <th className="text-right px-2 py-2 font-semibold">Total</th>
                  <th className="text-right px-2 py-2 font-semibold">LLM</th>
                  <th className="text-right px-2 py-2 font-semibold">Fetch</th>
                  <th className="text-right px-2 py-2 font-semibold">Writer</th>
                  <th className="text-right px-2 py-2 font-semibold"># LLM</th>
                  <th className="text-right px-2 py-2 font-semibold">Tokens</th>
                  <th className="text-right px-2 py-2 font-semibold">Coût</th>
                  <th className="text-right px-2 py-2 font-semibold">Err</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((t) => (
                  <tr key={t.job_id} className="border-b border-ink-100 hover:bg-ink-50">
                    <td className="px-3 py-2">
                      <Link
                        href={`/admin/traces/${t.job_id}`}
                        className="text-navy-600 hover:underline font-mono text-[11px]"
                      >
                        {t.job_id.slice(0, 10)}…
                      </Link>
                      {t.label && (
                        <div className="text-[10px] text-ink-500 truncate max-w-[160px]">
                          {t.label}
                        </div>
                      )}
                    </td>
                    <td className="px-2 py-2 text-ink-700 capitalize">{t.kind || "—"}</td>
                    <td className="px-2 py-2 text-right font-mono font-semibold">
                      {t.total_ms ? `${(t.total_ms / 1000).toFixed(1)}s` : "—"}
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-purple-600">
                      {t.llm_ms ? `${(t.llm_ms / 1000).toFixed(1)}s` : "—"}
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-blue-600">
                      {t.fetch_ms ? `${(t.fetch_ms / 1000).toFixed(1)}s` : "—"}
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-amber-700">
                      {t.writer_ms ? `${(t.writer_ms / 1000).toFixed(1)}s` : "—"}
                    </td>
                    <td className="px-2 py-2 text-right font-mono">{t.n_llm_calls}</td>
                    <td className="px-2 py-2 text-right font-mono text-[10px]">
                      <div>{(t.total_tokens_in || 0).toLocaleString("fr-FR")}↓</div>
                      <div className="text-ink-500">
                        {(t.total_tokens_out || 0).toLocaleString("fr-FR")}↑
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right font-mono font-semibold">
                      {t.total_cost_usd != null ? `$${Number(t.total_cost_usd).toFixed(4)}` : "—"}
                    </td>
                    <td className="px-2 py-2 text-right">
                      {t.n_errors > 0 ? (
                        <span className="text-signal-sell font-semibold">{t.n_errors}</span>
                      ) : (
                        <span className="text-ink-400">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Légende */}
        <div className="flex gap-6 text-[10px] text-ink-500">
          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Total = durée du job</span>
          <span className="flex items-center gap-1"><Zap className="w-3 h-3 text-purple-600" /> LLM = temps sur appels LLM</span>
          <span className="flex items-center gap-1"><Activity className="w-3 h-3 text-blue-600" /> Fetch = yfinance/FMP/news</span>
          <span className="flex items-center gap-1"><DollarSign className="w-3 h-3" /> Coût USD estimé (prix publics)</span>
          <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-signal-sell" /> Err = steps en erreur</span>
        </div>
      </div>
    </div>
  );
}
