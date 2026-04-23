"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, GitCompare, Loader2 } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { submitCmpSecteurJob, waitForJob } from "@/lib/api";
import toast from "react-hot-toast";

const SECTEURS = [
  "Technology",
  "Healthcare",
  "Financial Services",
  "Consumer Cyclical",
  "Consumer Defensive",
  "Communication Services",
  "Energy",
  "Industrials",
  "Basic Materials",
  "Real Estate",
  "Utilities",
];

const SECTEUR_FR: Record<string, string> = {
  "Technology": "Technologie",
  "Healthcare": "Santé",
  "Financial Services": "Services financiers",
  "Consumer Cyclical": "Consommation cyclique",
  "Consumer Defensive": "Consommation défensive",
  "Communication Services": "Services de communication",
  "Energy": "Énergie",
  "Industrials": "Industrie",
  "Basic Materials": "Matériaux de base",
  "Real Estate": "Immobilier",
  "Utilities": "Services aux collectivités",
};

const UNIVERS = [
  "Mondial",
  "S&P 500",
  "CAC 40",
  "DAX",
  "FTSE 100",
  "Nasdaq 100",
  "Euro Stoxx 50",
  "Nikkei 225",
];

const QUICK_PAIRS: Array<{ sa: string; ua: string; sb: string; ub: string; label: string }> = [
  { sa: "Technology", ua: "S&P 500", sb: "Financial Services", ub: "S&P 500", label: "Tech US vs Finance US" },
  { sa: "Technology", ua: "S&P 500", sb: "Technology", ub: "CAC 40", label: "Tech US vs Tech FR" },
  { sa: "Energy", ua: "Mondial", sb: "Utilities", ub: "Mondial", label: "Énergie vs Utilities" },
  { sa: "Healthcare", ua: "S&P 500", sb: "Healthcare", ub: "CAC 40", label: "Santé US vs Santé FR" },
];

export default function ComparatifSecteurPage() {
  const router = useRouter();
  const [secteurA, setSecteurA] = useState("Technology");
  const [universA, setUniversA] = useState("S&P 500");
  const [secteurB, setSecteurB] = useState("Financial Services");
  const [universB, setUniversB] = useState("S&P 500");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string>("");

  async function handleCompare() {
    if (secteurA === secteurB && universA === universB) {
      toast.error("Choisissez deux couples secteur/univers différents");
      return;
    }

    setLoading(true);
    setProgress("Soumission de la comparaison…");
    try {
      const submitted = await submitCmpSecteurJob(secteurA, universA, secteurB, universB);
      setProgress(`Analyse parallèle en cours…`);

      const job = await waitForJob(
        submitted.job_id,
        (j) => {
          if (j.status === "running") setProgress(`Analyse en cours · ${j.progress}%`);
        },
        6000
      );

      if (job.status === "done" && job.result) {
        const elapsedMs = job.finished_at && job.started_at
          ? new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()
          : 0;
        const label = `${SECTEUR_FR[secteurA] || secteurA}/${universA} vs ${SECTEUR_FR[secteurB] || secteurB}/${universB}`;
        try {
          sessionStorage.setItem(
            `analysis_${submitted.job_id}`,
            JSON.stringify({
              success: true,
              request_id: submitted.job_id,
              elapsed_ms: elapsedMs,
              data: job.result.data,
              files: job.result.files,
              kind: "comparatif",
              label,
            })
          );
        } catch {
          // Quota exceeded — la page /resultats rechargera via getJob
        }
        router.push(
          `/resultats/${submitted.job_id}?ticker=${encodeURIComponent(label)}&kind=comparatif`
        );
      } else {
        toast.error(job.error || "Erreur de comparaison");
        setLoading(false);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur API";
      toast.error(msg);
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-4xl mx-auto px-6 py-12 w-full">
        <div className="text-center mb-6 animate-fade-in">
          <div className="section-label mb-3">Comparatif Secteur</div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-900 mb-2 tracking-tight">
            Comparer deux secteurs
          </h1>
          <p className="text-sm text-ink-600 max-w-md mx-auto">
            Analyse intra-univers parallèle · Ratios sectoriels · Allocation Markowitz · Verdict relatif.
          </p>
        </div>

        {/* Tabs switch société/secteur */}
        <div className="flex justify-center gap-2 mb-8">
          <Link
            href="/comparatif"
            className="btn-secondary !py-2 !px-5 !text-sm hover:!border-navy-500 hover:!text-navy-500"
          >
            Sociétés
          </Link>
          <button
            disabled
            className="btn-primary !py-2 !px-5 !text-sm opacity-100 cursor-default"
          >
            Secteurs
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-[1fr,auto,1fr] gap-3 items-start max-w-3xl mx-auto">
          <div className="space-y-2">
            <label className="section-label">Secteur A</label>
            <select
              value={secteurA}
              onChange={(e) => setSecteurA(e.target.value)}
              disabled={loading}
              className="input !text-base !py-3 w-full"
            >
              {SECTEURS.map((s) => (
                <option key={s} value={s}>{SECTEUR_FR[s] || s}</option>
              ))}
            </select>
            <select
              value={universA}
              onChange={(e) => setUniversA(e.target.value)}
              disabled={loading}
              className="input !text-sm !py-2 w-full"
            >
              {UNIVERS.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-center text-ink-400 pt-10">
            <GitCompare className="w-5 h-5" />
          </div>

          <div className="space-y-2">
            <label className="section-label">Secteur B</label>
            <select
              value={secteurB}
              onChange={(e) => setSecteurB(e.target.value)}
              disabled={loading}
              className="input !text-base !py-3 w-full"
            >
              {SECTEURS.map((s) => (
                <option key={s} value={s}>{SECTEUR_FR[s] || s}</option>
              ))}
            </select>
            <select
              value={universB}
              onChange={(e) => setUniversB(e.target.value)}
              disabled={loading}
              className="input !text-sm !py-2 w-full"
            >
              {UNIVERS.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="max-w-3xl mx-auto mt-6">
          <button
            onClick={handleCompare}
            disabled={loading}
            className="btn-primary w-full !py-3 !text-base group disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {progress || "Comparaison…"}
              </>
            ) : (
              <>
                Comparer
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
        </div>

        {!loading && (
          <div className="mt-12 text-center animate-slide-up">
            <div className="section-label mb-4">Comparatifs populaires</div>
            <div className="flex flex-wrap justify-center gap-2">
              {QUICK_PAIRS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setSecteurA(p.sa);
                    setUniversA(p.ua);
                    setSecteurB(p.sb);
                    setUniversB(p.ub);
                  }}
                  className="btn-secondary !py-2 !px-4 !text-sm hover:!border-navy-500 hover:!text-navy-500"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="card mt-12 max-w-2xl mx-auto bg-ink-50">
          <div className="section-label mb-2">Durée estimée</div>
          <p className="text-sm text-ink-700">
            Une comparaison secteur analyse une dizaine de sociétés dans chaque univers en parallèle. Comptez 4 à 6 minutes. Livrables PDF et PPTX comparatifs générés à la fin.
          </p>
        </div>
      </main>

      <Footer />
    </div>
  );
}
