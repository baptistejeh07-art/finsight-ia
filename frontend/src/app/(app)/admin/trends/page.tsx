"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { ArrowLeft, Database, Download } from "lucide-react";

interface LogRow {
  id: number;
  created_at: string;
  kind: string;
  ticker: string | null;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  universe: string | null;
  country: string | null;
  market_cap_bucket: string | null;
  market_cap_usd_bn: number | null;
  score_finsight: number | null;
  recommendation: string | null;
  conviction: number | null;
  target_upside_pct: number | null;
  language: string | null;
  currency: string | null;
  duration_ms: number | null;
  llm_fallback_used: boolean;
  data_quality: string | null;
}

export default function AdminTrendsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<LogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    (async () => {
      const supabase = createClient();
      const { data } = await supabase.auth.getUser();
      if (!data.user) { router.push("/"); return; }
      const { data: prefs } = await supabase
        .from("user_preferences")
        .select("is_admin")
        .eq("user_id", data.user.id)
        .single();
      const admin = !!prefs?.is_admin;
      setIsAdmin(admin);
      if (!admin) { router.push("/app"); return; }

      // Lire analysis_log (RLS autorise seulement les admins)
      const { data: logs } = await supabase
        .from("analysis_log")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(500);
      setRows(logs || []);
      setLoading(false);
    })();
  }, [router]);

  function downloadCsv() {
    const headers = [
      "created_at", "kind", "ticker", "company_name", "sector", "industry",
      "universe", "country", "market_cap_bucket", "market_cap_usd_bn",
      "score_finsight", "recommendation", "conviction", "target_upside_pct",
      "language", "currency", "duration_ms", "llm_fallback_used", "data_quality",
    ];
    const csvRows = [headers.join(",")];
    for (const r of rows) {
      const vals = headers.map((h) => {
        const v = (r as Record<string, unknown>)[h];
        if (v === null || v === undefined) return "";
        const s = String(v).replace(/"/g, '""');
        return s.includes(",") || s.includes("\n") ? `"${s}"` : s;
      });
      csvRows.push(vals.join(","));
    }
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `finsight_trends_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) return <div className="p-8 text-sm text-ink-500">Chargement…</div>;
  if (!isAdmin) return <div className="p-8 text-sm text-signal-sell">Admin only.</div>;

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/admin" className="text-xs text-navy-500 hover:underline flex items-center gap-1 mb-2">
            <ArrowLeft className="w-3 h-3" /> Retour dashboard
          </Link>
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
            <Database className="w-3 h-3" /> FinSight Trends — Dataset anonymisé
          </div>
          <h1 className="text-2xl font-bold text-ink-900">Toutes les analyses ({rows.length})</h1>
          <p className="text-xs text-ink-500 mt-1">
            Aucune trace utilisateur. Base du futur dataset vendable aux hedge funds (signal alternatif).
          </p>
        </div>
        <button
          onClick={downloadCsv}
          className="flex items-center gap-2 text-xs bg-navy-500 text-white px-3 py-2 rounded hover:bg-navy-600"
        >
          <Download className="w-3 h-3" /> Export CSV
        </button>
      </div>

      <section className="bg-white border border-ink-200 rounded-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-ink-50 sticky top-0">
              <tr className="text-left text-ink-500">
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Kind</th>
                <th className="px-3 py-2">Ticker / SIREN</th>
                <th className="px-3 py-2">Société</th>
                <th className="px-3 py-2">Secteur</th>
                <th className="px-3 py-2">Pays</th>
                <th className="px-3 py-2">Mkt Cap</th>
                <th className="px-3 py-2">Univers</th>
                <th className="px-3 py-2">Reco</th>
                <th className="px-3 py-2">Conv.</th>
                <th className="px-3 py-2">Upside</th>
                <th className="px-3 py-2">Lang</th>
                <th className="px-3 py-2">Dur.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-ink-100 hover:bg-ink-50/50">
                  <td className="px-3 py-2 text-ink-600 whitespace-nowrap">
                    {new Date(r.created_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
                  </td>
                  <td className="px-3 py-2"><span className="text-[10px] bg-ink-100 px-1.5 py-0.5 rounded">{r.kind}</span></td>
                  <td className="px-3 py-2 font-mono text-navy-500">{r.ticker || "—"}</td>
                  <td className="px-3 py-2 text-ink-800 truncate max-w-[200px]">{r.company_name || "—"}</td>
                  <td className="px-3 py-2 text-ink-600">{r.sector || "—"}</td>
                  <td className="px-3 py-2 text-ink-500">{r.country || "—"}</td>
                  <td className="px-3 py-2 text-ink-500">{r.market_cap_bucket || "—"}</td>
                  <td className="px-3 py-2 text-ink-500">{r.universe || "—"}</td>
                  <td className="px-3 py-2">
                    {r.recommendation && (
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        r.recommendation === "BUY" ? "bg-signal-buy/10 text-signal-buy" :
                        r.recommendation === "SELL" ? "bg-signal-sell/10 text-signal-sell" :
                        "bg-amber-500/10 text-amber-700"}`}>
                        {r.recommendation}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-ink-500 font-mono">{r.conviction !== null ? (r.conviction * 100).toFixed(0) + "%" : "—"}</td>
                  <td className="px-3 py-2 text-ink-500 font-mono">{r.target_upside_pct !== null ? r.target_upside_pct.toFixed(1) + "%" : "—"}</td>
                  <td className="px-3 py-2 text-ink-500 uppercase">{r.language || "—"}</td>
                  <td className="px-3 py-2 text-ink-500 font-mono">{r.duration_ms ? (r.duration_ms / 1000).toFixed(1) + "s" : "—"}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={13} className="text-center py-8 text-xs text-ink-400 italic">
                  Aucune analyse enregistrée. Les prochaines analyses apparaîtront ici.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
