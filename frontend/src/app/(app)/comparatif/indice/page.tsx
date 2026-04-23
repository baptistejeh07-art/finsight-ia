"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, GitCompare, Loader2 } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { submitCmpIndiceJob, waitForJob } from "@/lib/api";
import toast from "react-hot-toast";

const INDICES: Array<{ code: string; name: string; currency: string }> = [
  { code: "CAC40",     name: "CAC 40",        currency: "EUR" },
  { code: "SP500",     name: "S&P 500",       currency: "USD" },
  { code: "NASDAQ100", name: "NASDAQ 100",    currency: "USD" },
  { code: "DOWJONES",  name: "Dow Jones",     currency: "USD" },
  { code: "DAX40",     name: "DAX 40",        currency: "EUR" },
  { code: "FTSE100",   name: "FTSE 100",      currency: "GBP" },
  { code: "STOXX50",   name: "Euro Stoxx 50", currency: "EUR" },
  { code: "NIKKEI225", name: "Nikkei 225",    currency: "JPY" },
];

const QUICK_PAIRS: Array<{ a: string; b: string; label: string }> = [
  { a: "CAC40",     b: "SP500",     label: "CAC 40 vs S&P 500" },
  { a: "SP500",     b: "NASDAQ100", label: "S&P 500 vs NASDAQ 100" },
  { a: "DAX40",     b: "CAC40",     label: "DAX 40 vs CAC 40" },
  { a: "FTSE100",   b: "STOXX50",   label: "FTSE 100 vs Euro Stoxx 50" },
];

export default function ComparatifIndicePage() {
  const router = useRouter();
  const [indiceA, setIndiceA] = useState("CAC40");
  const [indiceB, setIndiceB] = useState("SP500");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string>("");

  async function handleCompare() {
    if (indiceA === indiceB) {
      toast.error("Choisissez deux indices différents");
      return;
    }

    setLoading(true);
    setProgress("Soumission de la comparaison…");
    try {
      const submitted = await submitCmpIndiceJob(indiceA, indiceB);
      setProgress("Analyse en cours…");

      const job = await waitForJob(
        submitted.job_id,
        (j) => {
          if (j.status === "running") setProgress(`Analyse en cours · ${j.progress}%`);
        },
        8000
      );

      if (job.status === "done" && job.result) {
        const elapsedMs = job.finished_at && job.started_at
          ? new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()
          : 0;
        const nameA = INDICES.find((i) => i.code === indiceA)?.name || indiceA;
        const nameB = INDICES.find((i) => i.code === indiceB)?.name || indiceB;
        const label = `${nameA} vs ${nameB}`;
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
          // Quota exceeded — /resultats rechargera via getJob
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
          <div className="section-label mb-3">Comparatif Indice</div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-900 mb-2 tracking-tight">
            Comparer deux indices boursiers
          </h1>
          <p className="text-sm text-ink-600 max-w-md mx-auto">
            Performance · Volatilité · Sharpe · Valorisation · Composition sectorielle · Top constituants. PDF + PPTX + Excel comparatifs.
          </p>
        </div>

        {/* Tabs switch société/secteur/indice */}
        <div className="flex justify-center gap-2 mb-8">
          <Link
            href="/comparatif"
            className="btn-secondary !py-2 !px-5 !text-sm hover:!border-navy-500 hover:!text-navy-500"
          >
            Sociétés
          </Link>
          <Link
            href="/comparatif/secteur"
            className="btn-secondary !py-2 !px-5 !text-sm hover:!border-navy-500 hover:!text-navy-500"
          >
            Secteurs
          </Link>
          <button
            disabled
            className="btn-primary !py-2 !px-5 !text-sm opacity-100 cursor-default"
          >
            Indices
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-[1fr,auto,1fr] gap-3 items-center max-w-3xl mx-auto">
          <div>
            <label className="section-label mb-2 block">Indice A</label>
            <select
              value={indiceA}
              onChange={(e) => setIndiceA(e.target.value)}
              disabled={loading}
              className="input !text-base !py-3 w-full"
            >
              {INDICES.map((i) => (
                <option key={i.code} value={i.code}>{i.name} ({i.currency})</option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-center text-ink-400 sm:mt-8">
            <GitCompare className="w-5 h-5" />
          </div>

          <div>
            <label className="section-label mb-2 block">Indice B</label>
            <select
              value={indiceB}
              onChange={(e) => setIndiceB(e.target.value)}
              disabled={loading}
              className="input !text-base !py-3 w-full"
            >
              {INDICES.map((i) => (
                <option key={i.code} value={i.code}>{i.name} ({i.currency})</option>
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
                    setIndiceA(p.a);
                    setIndiceB(p.b);
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
            Une comparaison indice récupère les constituants de l&apos;indice A et calcule les métriques agrégées pour les deux. Comptez 5 à 8 minutes. Livrables PDF + PPTX + Excel.
          </p>
        </div>
      </main>

      <Footer />
    </div>
  );
}
