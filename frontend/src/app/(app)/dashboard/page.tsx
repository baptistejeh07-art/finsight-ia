"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, FileText, Search } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { createClient } from "@/lib/supabase/client";
import { getHistory } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

interface HistoryJob {
  job_id: string;
  kind: string;
  label?: string;
  created_at: string;
  finished_at?: string;
}

interface AnalysisItem {
  id: string;
  ticker: string;
  company_name: string;
  sector: string;
  recommendation: string;
  created_at: string;
}

function labelForKind(kind: string): string {
  if (kind.startsWith("analyze/societe") || kind === "societe") return "Société";
  if (kind.startsWith("analyze/secteur") || kind === "secteur") return "Secteur";
  if (kind.startsWith("analyze/indice") || kind === "indice") return "Indice";
  if (kind.startsWith("cmp/societe") || kind === "comparatif") return "Comparatif";
  if (kind.startsWith("cmp/secteur")) return "Comparatif secteur";
  return "Analyse";
}

export default function DashboardPage() {
  const router = useRouter();
  const supabase = createClient();
  const [history, setHistory] = useState<AnalysisItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        router.push("/app");
        return;
      }

      // Merge entre jobs backend (user-scoped) + sessionStorage (analyses locales récentes)
      const byId = new Map<string, AnalysisItem>();

      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key?.startsWith("analysis_")) {
          try {
            const r = JSON.parse(sessionStorage.getItem(key) || "{}");
            const data = r.data || {};
            const ci = data.snapshot?.company_info || {};
            const synth = data.synthesis || {};
            const id = r.request_id;
            byId.set(id, {
              id,
              ticker: ci.ticker || r.label || "?",
              company_name: ci.company_name || ci.ticker || r.label || "?",
              sector: ci.sector || (r.kind ? labelForKind(r.kind) : "—"),
              recommendation: synth.recommendation || "—",
              created_at: new Date().toISOString(),
            });
          } catch {
            // skip
          }
        }
      }

      try {
        const { history: jobs } = (await getHistory()) as { history: HistoryJob[] };
        for (const j of jobs) {
          if (byId.has(j.job_id)) continue; // évite doublon avec sessionStorage
          byId.set(j.job_id, {
            id: j.job_id,
            ticker: j.label || j.job_id.slice(0, 8),
            company_name: j.label || "",
            sector: labelForKind(j.kind),
            recommendation: "—",
            created_at: j.finished_at || j.created_at,
          });
        }
      } catch {
        // backend unreachable → fallback sessionStorage only
      }

      const merged = Array.from(byId.values()).sort((a, b) =>
        b.created_at.localeCompare(a.created_at)
      );
      setHistory(merged);
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = history.filter(
    (h) =>
      h.ticker.toLowerCase().includes(search.toLowerCase()) ||
      h.company_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-6xl mx-auto px-6 py-8 w-full">
        {/* Header */}
        <header className="mb-8">
          <div className="section-label mb-1">Mon espace</div>
          <h1 className="text-2xl font-bold text-ink-900 tracking-tight">Dashboard</h1>
          <p className="text-sm text-ink-600 mt-1">
            Historique de vos analyses · Reprenez où vous vous étiez arrêté
          </p>
        </header>

        {/* Search */}
        <div className="relative mb-6 max-w-md">
          <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Rechercher dans mes analyses..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input !pl-10"
          />
        </div>

        {/* History */}
        {loading ? (
          <div className="grid gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-20 rounded-md" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="card text-center py-12">
            <FileText className="w-10 h-10 text-ink-300 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-ink-900 mb-1">
              {history.length === 0 ? "Aucune analyse encore" : "Aucun résultat"}
            </h3>
            <p className="text-xs text-ink-500 mb-4">
              {history.length === 0
                ? "Lancez votre première analyse depuis l'accueil."
                : "Modifiez votre recherche."}
            </p>
            {history.length === 0 && (
              <button onClick={() => router.push("/app")} className="btn-primary">
                Lancer une analyse
              </button>
            )}
          </div>
        ) : (
          <div className="grid gap-3">
            {filtered.map((item) => (
              <button
                key={item.id}
                onClick={() => router.push(`/resultats/${item.id}?ticker=${item.ticker}`)}
                className="card-hover flex items-center gap-4 text-left"
              >
                <div className="w-10 h-10 rounded-md bg-navy-50 flex items-center justify-center text-navy-500 shrink-0">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="font-bold text-ink-900">{item.ticker}</span>
                    <span className="text-sm text-ink-600 truncate">
                      {item.company_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-ink-500">
                    <span>{item.sector}</span>
                    <span>·</span>
                    <span>{fmtDate(item.created_at)}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xs uppercase tracking-wider text-ink-500">
                    Reco
                  </div>
                  <div className="text-sm font-bold text-ink-900">
                    {item.recommendation}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
