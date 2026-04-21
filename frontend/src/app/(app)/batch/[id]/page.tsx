"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { CheckCircle2, AlertCircle, Loader2, Clock } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { BackButton } from "@/components/back-button";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface SubJob {
  job_id: string;
  status: string;
  label: string;
  progress?: number;
  started_at?: string;
  finished_at?: string;
}

interface BatchStatus {
  batch_id: string;
  label: string;
  status: string;
  total: number;
  done: number;
  failed: number;
  sub_jobs: SubJob[];
}

async function getToken() {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token || null;
}

export default function BatchProgressPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [batch, setBatch] = useState<BatchStatus | null>(null);

  useEffect(() => {
    let stop = false;
    async function poll() {
      while (!stop) {
        const token = await getToken();
        try {
          const r = await fetch(`${API}/batch/${id}`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          if (r.ok) {
            const j = (await r.json()) as BatchStatus;
            setBatch(j);
            if (j.status !== "running") return; // stop polling
          }
        } catch {}
        await new Promise((res) => setTimeout(res, 4000));
      }
    }
    poll();
    return () => { stop = true; };
  }, [id]);

  if (!batch) {
    return (
      <div className="min-h-screen bg-ink-50/30">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <BackButton fallback="/watchlists" />
          <div className="mt-6 text-sm text-ink-500 italic">Chargement…</div>
        </div>
      </div>
    );
  }

  const pct = batch.total > 0 ? Math.round(((batch.done + batch.failed) / batch.total) * 100) : 0;
  const isFinal = batch.status !== "running";

  return (
    <div className="min-h-screen bg-ink-50/30">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <BackButton fallback="/watchlists" />

        <header>
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
            Batch en cours
          </div>
          <h1 className="text-2xl font-bold text-ink-900">{batch.label || "Batch"}</h1>
          <p className="text-sm text-ink-600 mt-1">
            {batch.done} / {batch.total} terminé{batch.done > 1 ? "s" : ""}
            {batch.failed > 0 && (
              <span className="text-signal-sell"> · {batch.failed} en erreur</span>
            )}
            {isFinal && (
              <span className={"ml-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase " +
                (batch.status === "done" ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700")}>
                {batch.status === "done" ? "Terminé" : "Terminé (partiel)"}
              </span>
            )}
          </p>
        </header>

        {/* Barre de progression globale */}
        <div className="bg-white border border-ink-200 rounded-md p-4">
          <div className="flex items-center justify-between text-xs text-ink-700 mb-2">
            <span>{pct}%</span>
            <span className="font-mono">{batch.done + batch.failed} / {batch.total}</span>
          </div>
          <div className="h-2 bg-ink-100 rounded-full overflow-hidden">
            <div className="h-full bg-navy-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>

        {/* Liste des sous-jobs */}
        <div className="bg-white border border-ink-200 rounded-md overflow-hidden">
          <div className="px-4 py-2 border-b border-ink-100 text-[11px] font-semibold uppercase tracking-wider text-ink-500">
            Détail par ticker ({batch.sub_jobs.length})
          </div>
          <div className="divide-y divide-ink-100">
            {batch.sub_jobs.map((sj) => (
              <SubJobRow key={sj.job_id} sj={sj} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SubJobRow({ sj }: { sj: SubJob }) {
  const icon =
    sj.status === "done" ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> :
    sj.status === "error" ? <AlertCircle className="w-4 h-4 text-signal-sell" /> :
    sj.status === "running" ? <Loader2 className="w-4 h-4 text-navy-500 animate-spin" /> :
    <Clock className="w-4 h-4 text-ink-400" />;
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 hover:bg-ink-50">
      {icon}
      <span className="font-mono font-semibold text-sm text-ink-900 w-28">{sj.label}</span>
      <span className="flex-1 text-xs text-ink-500 capitalize">{sj.status}</span>
      {sj.status === "done" && (
        <Link
          href={`/resultats/${sj.job_id}?ticker=${sj.label}&kind=societe`}
          className="text-xs font-semibold text-navy-500 hover:underline"
        >
          Voir l&apos;analyse →
        </Link>
      )}
    </div>
  );
}
