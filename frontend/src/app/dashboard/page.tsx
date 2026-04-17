"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, FileText, Search } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { createClient } from "@/lib/supabase/client";
import { fmtDate } from "@/lib/utils";

interface AnalysisItem {
  id: string;
  ticker: string;
  company_name: string;
  sector: string;
  recommendation: string;
  created_at: string;
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
        router.push("/");
        return;
      }
      // V1 stub : pas de DB encore. On simule depuis sessionStorage.
      const localItems: AnalysisItem[] = [];
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key?.startsWith("analysis_")) {
          try {
            const r = JSON.parse(sessionStorage.getItem(key) || "{}");
            const data = r.data || {};
            const ci = data.snapshot?.company_info || {};
            const synth = data.synthesis || {};
            localItems.push({
              id: r.request_id,
              ticker: ci.ticker || "?",
              company_name: ci.company_name || ci.ticker || "?",
              sector: ci.sector || "—",
              recommendation: synth.recommendation || "HOLD",
              created_at: new Date().toISOString(),
            });
          } catch {
            // skip
          }
        }
      }
      setHistory(localItems);
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
              <button onClick={() => router.push("/")} className="btn-primary">
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
