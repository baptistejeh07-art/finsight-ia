"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import {
  resolveQuery,
  submitSocieteJob,
  submitSecteurJob,
  submitIndiceJob,
  waitForJob,
} from "@/lib/api";

const STEPS_SOCIETE = [
  "Connexion aux sources financières",
  "Récupération des données yfinance",
  "Calcul des ratios sectoriels",
  "Génération des projections DCF",
  "Analyse IA des fondamentaux",
  "Synthèse exécutive",
  "Génération PDF / PPTX / Excel",
];
const STEPS_SECTEUR = [
  "Identification des sociétés du secteur",
  "Récupération des données financières",
  "Calcul des moyennes sectorielles",
  "Comparaison intra-secteur",
  "Allocation optimale (Markowitz)",
  "Génération PDF sectoriel + PPTX",
];
const STEPS_INDICE = [
  "Cartographie des secteurs de l'indice",
  "Récupération données (multi-secteurs)",
  "Calcul des métriques par secteur",
  "Analyse macro de l'indice",
  "Allocation optimale inter-secteurs",
  "Génération PDF + PPTX + Excel indice",
];

function AnalyseContent() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q") || "";
  const devise = params.get("devise") || "USD";
  const scope = (params.get("scope") || "interface") as "interface" | "files";

  const [stepIdx, setStepIdx] = useState(0);
  const [steps, setSteps] = useState<string[]>(STEPS_SOCIETE);
  const [kind, setKind] = useState<"societe" | "secteur" | "indice">("societe");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) {
      router.push("/");
      return;
    }

    let interval: ReturnType<typeof setInterval> | null = null;

    (async () => {
      try {
        // Résolution intelligente du type de requête côté backend
        const resolved = await resolveQuery(query);

        if (resolved.kind === "unknown") {
          setError(
            "Impossible de déterminer si «\u00a0" + query +
            "\u00a0» est un ticker, secteur ou indice. Essayez un ticker (AAPL), un indice (CAC 40) ou un secteur (Technologie)."
          );
          return;
        }

        // Setup des étapes selon le type
        const stepsForKind =
          resolved.kind === "indice" ? STEPS_INDICE :
          resolved.kind === "secteur" ? STEPS_SECTEUR :
          STEPS_SOCIETE;
        setSteps(stepsForKind);
        setKind(resolved.kind);

        // Animation visuelle des étapes — cadence adaptée à la durée totale
        const stepDelay = resolved.kind === "indice" ? 60000 :
                          resolved.kind === "secteur" ? 15000 : 8000;
        interval = setInterval(() => {
          setStepIdx((i) => Math.min(i + 1, stepsForKind.length - 1));
        }, stepDelay);

        // Submit le job + poll le statut
        let label = query;
        let submitted;
        if (resolved.kind === "societe") {
          const t = resolved.ticker || query;
          submitted = await submitSocieteJob(t, devise, scope);
          label = t;
        } else if (resolved.kind === "secteur") {
          const sec = resolved.sector || query;
          const uni = resolved.universe || "S&P 500";
          submitted = await submitSecteurJob(sec, uni);
          label = `${sec} / ${uni}`;
        } else {
          const idx = resolved.universe || query;
          submitted = await submitIndiceJob(idx);
          label = idx;
        }

        // Poll toutes les 5s jusqu'à fin du job
        const pollInterval = resolved.kind === "indice" ? 8000 : 4000;
        const finalJob = await waitForJob(submitted.job_id, undefined, pollInterval);

        if (finalJob.status === "done" && finalJob.result) {
          const elapsedMs = finalJob.finished_at && finalJob.started_at
            ? new Date(finalJob.finished_at).getTime() - new Date(finalJob.started_at).getTime()
            : 0;
          sessionStorage.setItem(
            `analysis_${submitted.job_id}`,
            JSON.stringify({
              success: true,
              request_id: submitted.job_id,
              elapsed_ms: elapsedMs,
              data: finalJob.result.data,
              files: finalJob.result.files,
              kind: resolved.kind,
              label,
            })
          );
          router.push(
            `/resultats/${submitted.job_id}?ticker=${encodeURIComponent(label)}&kind=${resolved.kind}`
          );
        } else {
          setError(finalJob.error || "Erreur inconnue");
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Erreur API";
        setError(msg);
      } finally {
        if (interval) clearInterval(interval);
      }
    })();

    return () => { if (interval) clearInterval(interval); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-2xl mx-auto px-6 py-20 w-full text-center">
          <AlertTriangle className="w-12 h-12 text-signal-sell mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-ink-900 mb-2">
            Échec de l&apos;analyse
          </h1>
          <p className="text-sm text-ink-600 mb-6">{error}</p>
          <button onClick={() => router.push("/")} className="btn-primary">
            Retour à l&apos;accueil
          </button>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-2xl mx-auto px-6 py-16 w-full">
        <div className="text-center mb-10 animate-fade-in">
          <Loader2 className="w-10 h-10 text-navy-500 animate-spin mx-auto mb-4" />
          <div className="section-label mb-2">Analyse en cours</div>
          <h1 className="text-2xl font-bold text-ink-900 mb-2 tracking-tight">
            {query}
          </h1>
          <p className="text-sm text-ink-600">
            {kind === "indice"
              ? "Analyse d'un indice complet. ~5 à 8 minutes."
              : kind === "secteur"
              ? "Analyse sectorielle multi-sociétés. ~2 à 4 minutes."
              : "Analyse institutionnelle. ~1 à 3 minutes."}
          </p>
        </div>

        {/* Steps */}
        <div className="card max-w-md mx-auto">
          <ul className="space-y-3">
            {steps.map((step, i) => (
              <li
                key={step}
                className={`flex items-center gap-3 text-sm transition-opacity ${
                  i > stepIdx ? "opacity-30" : ""
                }`}
              >
                {i < stepIdx ? (
                  <CheckCircle2 className="w-4 h-4 text-signal-buy shrink-0" />
                ) : i === stepIdx ? (
                  <Loader2 className="w-4 h-4 text-navy-500 animate-spin shrink-0" />
                ) : (
                  <div className="w-4 h-4 rounded-full border-2 border-ink-300 shrink-0" />
                )}
                <span
                  className={`${
                    i === stepIdx ? "text-ink-900 font-medium" : "text-ink-600"
                  }`}
                >
                  {step}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-ink-400 text-center mt-6 italic">
          Ne fermez pas cette page. Vous serez redirigé automatiquement.
        </p>
      </main>
      <Footer />
    </div>
  );
}

export default function AnalysePage() {
  return (
    <Suspense fallback={<div className="min-h-screen" />}>
      <AnalyseContent />
    </Suspense>
  );
}
