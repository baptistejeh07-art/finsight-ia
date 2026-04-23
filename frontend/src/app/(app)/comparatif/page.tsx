"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, GitCompare, Loader2 } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { submitCmpSocieteJob, waitForJob } from "@/lib/api";
import toast from "react-hot-toast";

const QUICK_PAIRS: Array<[string, string]> = [
  ["AAPL", "MSFT"],
  ["MC.PA", "OR.PA"],
  ["TSLA", "F"],
  ["NVDA", "AMD"],
];

export default function ComparatifPage() {
  const router = useRouter();
  const [tickerA, setTickerA] = useState("");
  const [tickerB, setTickerB] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string>("");

  async function handleCompare() {
    const a = tickerA.trim().toUpperCase();
    const b = tickerB.trim().toUpperCase();
    if (!a || !b) {
      toast.error("Saisissez deux tickers");
      return;
    }
    if (a === b) {
      toast.error("Les deux tickers doivent être différents");
      return;
    }

    setLoading(true);
    setProgress("Soumission de la comparaison…");
    try {
      const submitted = await submitCmpSocieteJob(a, b);
      setProgress(`Analyse de ${a} et ${b} en parallèle…`);

      const job = await waitForJob(
        submitted.job_id,
        (j) => {
          if (j.status === "running") setProgress(`Analyse en cours · ${j.progress}%`);
        },
        5000
      );

      if (job.status === "done" && job.result) {
        const elapsedMs = job.finished_at && job.started_at
          ? new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()
          : 0;
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
              label: `${a} vs ${b}`,
            })
          );
        } catch {
          // Quota exceeded — la page /resultats rechargera via getJob
        }
        router.push(
          `/resultats/${submitted.job_id}?ticker=${encodeURIComponent(`${a} vs ${b}`)}&kind=comparatif`
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
        {/* Hero */}
        <div className="text-center mb-6 animate-fade-in">
          <div className="section-label mb-3">Comparatif Société</div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-900 mb-2 tracking-tight">
            Comparer deux sociétés
          </h1>
          <p className="text-sm text-ink-600 max-w-md mx-auto">
            Analyse parallèle DCF · Ratios · Multiples · Verdict relatif. PDF + PPTX + Excel comparatifs.
          </p>
        </div>

        {/* Tabs switch société/secteur */}
        <div className="flex justify-center gap-2 mb-8">
          <button
            disabled
            className="btn-primary !py-2 !px-5 !text-sm opacity-100 cursor-default"
          >
            Sociétés
          </button>
          <Link
            href="/comparatif/secteur"
            className="btn-secondary !py-2 !px-5 !text-sm hover:!border-navy-500 hover:!text-navy-500"
          >
            Secteurs
          </Link>
        </div>

        {/* Inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-[1fr,auto,1fr] gap-3 items-center max-w-2xl mx-auto">
          <input
            type="text"
            placeholder="Ticker A (ex: AAPL)"
            value={tickerA}
            onChange={(e) => setTickerA(e.target.value)}
            disabled={loading}
            className="input !text-base !py-3 text-center"
            autoFocus
          />
          <div className="flex items-center justify-center text-ink-400">
            <GitCompare className="w-5 h-5" />
          </div>
          <input
            type="text"
            placeholder="Ticker B (ex: MSFT)"
            value={tickerB}
            onChange={(e) => setTickerB(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCompare()}
            disabled={loading}
            className="input !text-base !py-3 text-center"
          />
        </div>

        <div className="max-w-2xl mx-auto mt-4">
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

        {/* Quick pairs */}
        {!loading && (
          <div className="mt-12 text-center animate-slide-up">
            <div className="section-label mb-4">Comparatifs populaires</div>
            <div className="flex flex-wrap justify-center gap-2">
              {QUICK_PAIRS.map(([a, b]) => (
                <button
                  key={`${a}-${b}`}
                  onClick={() => {
                    setTickerA(a);
                    setTickerB(b);
                  }}
                  className="btn-secondary !py-2 !px-4 !text-sm hover:!border-navy-500 hover:!text-navy-500"
                >
                  {a} <span className="text-ink-400 mx-1">vs</span> {b}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Info bloc */}
        <div className="card mt-12 max-w-2xl mx-auto bg-ink-50">
          <div className="section-label mb-2">Durée estimée</div>
          <p className="text-sm text-ink-700">
            Une comparaison nécessite deux analyses complètes en parallèle. Comptez environ 3 à 5 minutes.
            Les livrables PDF, PPTX et Excel comparatifs sont générés à la fin.
          </p>
        </div>
      </main>

      <Footer />
    </div>
  );
}
