"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, AlertCircle, Info, AlertOctagon } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { BackButton } from "@/components/back-button";

const API = process.env.NEXT_PUBLIC_API_URL || "";

type Severity = "info" | "warn" | "error" | "critical";

interface ErrorRow {
  id: string;
  severity: Severity;
  error_type: string;
  node: string | null;
  ticker: string | null;
  kind: string | null;
  field_path: string | null;
  message: string;
  context: Record<string, unknown>;
  wakeup_fired: boolean;
  created_at: string;
}

const SEV_META: Record<Severity, { color: string; icon: React.ComponentType<{ className?: string }> }> = {
  critical: { color: "bg-red-100 text-red-800 border-red-300", icon: AlertOctagon },
  error: { color: "bg-orange-100 text-orange-800 border-orange-300", icon: AlertCircle },
  warn: { color: "bg-amber-50 text-amber-800 border-amber-200", icon: AlertTriangle },
  info: { color: "bg-ink-50 text-ink-700 border-ink-200", icon: Info },
};

export default function AdminErrorsPage() {
  const [data, setData] = useState<{ errors: ErrorRow[]; stats: Record<string, number>; by_type: Record<string, number> } | null>(null);
  const [filter, setFilter] = useState<Severity | "all">("all");
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancel = false;
    async function load() {
      setLoading(true);
      const supabase = createClient();
      const { data: sess } = await supabase.auth.getSession();
      const token = sess.session?.access_token;
      if (!token) { setLoading(false); return; }
      const sevParam = filter === "all" ? "" : `&severity=${filter}`;
      const r = await fetch(`${API}/admin/errors?hours=${hours}${sevParam}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) { setLoading(false); return; }
      const j = await r.json();
      if (!cancel) { setData(j); setLoading(false); }
    }
    load();
    return () => { cancel = true; };
  }, [filter, hours]);

  if (loading && !data) return <div className="p-6 text-sm text-ink-500">Chargement…</div>;

  const errs = data?.errors || [];
  const stats = data?.stats || {};

  return (
    <div className="min-h-screen bg-surface p-6 md:p-10 space-y-6">
      <BackButton fallback="/admin" />
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Sentinelle — erreurs pipeline</h1>
        <p className="text-sm text-ink-600 mt-1">
          Erreurs, warnings et data missing détectés dans le pipeline prod FinSight.
          {data && ` ${errs.length} événements sur les ${hours} dernières heures.`}
        </p>
      </header>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(["critical", "error", "warn", "info"] as Severity[]).map((s) => {
          const Icon = SEV_META[s].icon;
          return (
            <button
              key={s}
              onClick={() => setFilter(filter === s ? "all" : s)}
              className={`${SEV_META[s].color} border rounded-md p-3 text-left transition-all ${filter === s ? "ring-2 ring-offset-1" : ""}`}
            >
              <div className="flex items-center gap-2 text-xs uppercase font-semibold">
                <Icon className="w-3.5 h-3.5" /> {s}
              </div>
              <div className="text-2xl font-bold mt-1 font-mono">{stats[s] || 0}</div>
            </button>
          );
        })}
      </div>

      {/* Filtres */}
      <div className="flex items-center gap-3 text-sm">
        <button onClick={() => setFilter("all")} className={`px-3 py-1 rounded ${filter === "all" ? "bg-ink-900 text-white" : "bg-ink-100"}`}>
          Tous
        </button>
        <select value={hours} onChange={(e) => setHours(Number(e.target.value))}
                className="px-3 py-1 rounded border border-ink-300 bg-white">
          <option value={1}>1 heure</option>
          <option value={6}>6 heures</option>
          <option value={24}>24 heures</option>
          <option value={168}>7 jours</option>
          <option value={720}>30 jours</option>
        </select>
      </div>

      {/* Top error types */}
      {data?.by_type && Object.keys(data.by_type).length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-ink-700 mb-2">Types d&apos;erreur les plus fréquents</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.by_type)
              .sort((a, b) => b[1] - a[1]).slice(0, 10)
              .map(([type, count]) => (
                <span key={type} className="text-xs px-2 py-1 rounded bg-ink-100 text-ink-800 font-mono">
                  {type} <span className="font-bold">×{count}</span>
                </span>
              ))}
          </div>
        </section>
      )}

      {/* Table des erreurs */}
      <section className="bg-white border border-ink-200 rounded-md overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-ink-50 border-b border-ink-200">
            <tr>
              <th className="text-left px-3 py-2">Sévérité</th>
              <th className="text-left px-3 py-2">Type</th>
              <th className="text-left px-3 py-2">Ticker</th>
              <th className="text-left px-3 py-2">Node</th>
              <th className="text-left px-3 py-2">Message</th>
              <th className="text-left px-3 py-2">Wake</th>
              <th className="text-left px-3 py-2">Quand</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {errs.length === 0 ? (
              <tr><td colSpan={7} className="px-3 py-4 text-center text-ink-400">Aucune erreur.</td></tr>
            ) : errs.map((e) => (
              <tr key={e.id} className="hover:bg-ink-50/50">
                <td className="px-3 py-2">
                  <span className={`${SEV_META[e.severity].color} px-2 py-0.5 rounded text-[10px] font-semibold uppercase border`}>{e.severity}</span>
                </td>
                <td className="px-3 py-2 font-mono text-ink-800">{e.error_type}</td>
                <td className="px-3 py-2 font-mono text-ink-700">{e.ticker || "—"}</td>
                <td className="px-3 py-2 text-ink-600">{e.node || "—"}</td>
                <td className="px-3 py-2 text-ink-700 max-w-md truncate" title={e.message}>{e.message}</td>
                <td className="px-3 py-2">{e.wakeup_fired ? <span className="text-signal-buy">✓</span> : <span className="text-ink-300">—</span>}</td>
                <td className="px-3 py-2 text-ink-500 whitespace-nowrap">{new Date(e.created_at).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
