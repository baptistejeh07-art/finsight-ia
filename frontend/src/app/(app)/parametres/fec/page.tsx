"use client";

import { useEffect, useRef, useState } from "react";
import { Upload, FileText, CheckCircle2, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface FecRow {
  id: string;
  filename: string;
  siren: string | null;
  num_lines: number;
  exercice: string | null;
  status: string;
  parsed_summary: { revenue?: number; ebitda?: number; net_income?: number; total_assets?: number; equity?: number } | null;
  created_at: string;
}

export default function FecPage() {
  const [items, setItems] = useState<FecRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [siren, setSiren] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const t = data.session?.access_token;
      if (!t) return;
      const r = await fetch(`${API}/fec/list`, { headers: { Authorization: `Bearer ${t}` } });
      if (r.ok) setItems((await r.json()).fecs || []);
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function upload() {
    const f = fileRef.current?.files?.[0];
    if (!f) { toast.error("Choisissez un fichier"); return; }
    if (f.size > 50 * 1024 * 1024) { toast.error("Max 50 Mo"); return; }
    setUploading(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const t = data.session?.access_token;
      if (!t) { toast.error("Connectez-vous"); return; }
      const fd = new FormData();
      fd.append("file", f);
      if (siren) fd.append("siren", siren);
      const r = await fetch(`${API}/fec/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${t}` },
        body: fd,
      });
      const j = await r.json();
      if (!r.ok) { toast.error(j.detail || "Upload fail"); return; }
      toast.success(`FEC parsé — ${j.entries_count} écritures`);
      setSiren("");
      if (fileRef.current) fileRef.current.value = "";
      load();
    } finally { setUploading(false); }
  }

  function fmt(v: number | null | undefined) {
    if (v == null) return "—";
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(v) + " €";
  }

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-5 h-5 text-ink-700" />
          <h2 className="text-lg font-semibold text-ink-900">Import FEC</h2>
        </div>
        <p className="text-sm text-ink-600 mb-6">
          Importez votre <strong>Fichier des Écritures Comptables</strong> (format officiel FR
          imposé par l&apos;article A. 47 A-1 du LPF). FinSight extrait automatiquement votre
          compte de résultat + bilan + ratios clés — utile pour PME non cotées, expertise
          comptable, détection défaillance. Aucune donnée ne quitte l&apos;infrastructure FinSight.
        </p>

        <div className="bg-white border border-ink-200 rounded-md p-5 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-2xs uppercase tracking-widest text-ink-500 mb-1">SIREN (optionnel)</label>
              <input type="text" value={siren} onChange={(e) => setSiren(e.target.value)}
                placeholder="552032534"
                className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm" />
            </div>
            <div>
              <label className="block text-2xs uppercase tracking-widest text-ink-500 mb-1">Fichier FEC (.txt ou .fec)</label>
              <input ref={fileRef} type="file" accept=".txt,.fec,text/plain"
                className="w-full text-sm file:mr-3 file:py-2 file:px-3 file:rounded-md file:border file:border-ink-300 file:bg-ink-50 file:text-ink-700 file:text-xs" />
            </div>
          </div>
          <button onClick={upload} disabled={uploading}
            className="mt-4 flex items-center gap-2 px-4 py-2 rounded-md bg-navy-500 text-white text-sm font-semibold hover:bg-navy-600 disabled:opacity-50">
            <Upload className="w-4 h-4" /> {uploading ? "Analyse en cours…" : "Importer et analyser"}
          </button>
        </div>

        {loading ? (
          <div className="text-sm text-ink-500">Chargement…</div>
        ) : items.length === 0 ? (
          <div className="rounded-md border border-dashed border-ink-300 p-6 text-center text-sm text-ink-500">
            Aucun FEC importé. Uploadez votre premier fichier ci-dessus.
          </div>
        ) : (
          <div className="border border-ink-200 rounded-md divide-y divide-ink-100 bg-white">
            {items.map((it) => (
              <div key={it.id} className="px-4 py-3">
                <div className="flex items-center gap-2 mb-1.5">
                  {it.status === "parsed" ? (
                    <CheckCircle2 className="w-4 h-4 text-signal-buy" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                  )}
                  <span className="text-sm font-semibold text-ink-900">{it.filename}</span>
                  {it.exercice && <span className="text-xs text-ink-500">· {it.exercice}</span>}
                  {it.siren && <span className="text-xs text-ink-500 font-mono">· {it.siren}</span>}
                </div>
                {it.parsed_summary && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-xs">
                    <div>
                      <div className="text-2xs uppercase text-ink-500">CA</div>
                      <div className="font-mono font-semibold">{fmt(it.parsed_summary.revenue)}</div>
                    </div>
                    <div>
                      <div className="text-2xs uppercase text-ink-500">EBITDA</div>
                      <div className="font-mono font-semibold">{fmt(it.parsed_summary.ebitda)}</div>
                    </div>
                    <div>
                      <div className="text-2xs uppercase text-ink-500">Résultat net</div>
                      <div className="font-mono font-semibold">{fmt(it.parsed_summary.net_income)}</div>
                    </div>
                    <div>
                      <div className="text-2xs uppercase text-ink-500">Total actif</div>
                      <div className="font-mono font-semibold">{fmt(it.parsed_summary.total_assets)}</div>
                    </div>
                  </div>
                )}
                <div className="text-2xs text-ink-400 mt-2 font-mono">
                  {it.num_lines} écritures · {new Date(it.created_at).toLocaleString("fr-FR")}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
