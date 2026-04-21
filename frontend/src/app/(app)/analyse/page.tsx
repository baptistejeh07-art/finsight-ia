"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
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
      router.push("/app");
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
          // Défaut "Mondial" : analyse intra-univers monde plutôt qu'un biais US.
          // Si le résolveur a explicitement détecté un univers (CAC 40, S&P 500…),
          // on le respecte.
          const uni = resolved.universe || "Mondial";
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

          // Cache local en sessionStorage (limite ~5 Mo par origin).
          // Si quota dépassé (Tesla, indices riches…), on skip le cache et on
          // redirige quand même : /resultats refetchera depuis l'API si nécessaire.
          const payload = {
            success: true,
            request_id: submitted.job_id,
            elapsed_ms: elapsedMs,
            data: finalJob.result.data,
            files: finalJob.result.files,
            kind: resolved.kind,
            label,
          };
          try {
            sessionStorage.setItem(
              `analysis_${submitted.job_id}`,
              JSON.stringify(payload),
            );
          } catch (storageErr) {
            // QuotaExceededError ou autre : on essaie une version allégée
            // (sans raw_data, qui est le plus lourd)
            try {
              const lite = {
                ...payload,
                data: payload.data
                  ? {
                      ...payload.data,
                      raw_data: undefined, // omit le plus gros
                    }
                  : payload.data,
              };
              sessionStorage.setItem(
                `analysis_${submitted.job_id}`,
                JSON.stringify(lite),
              );
              console.warn("[analyse] sessionStorage saturé, payload allégé sauvegardé", storageErr);
            } catch {
              // Toujours pas → skip totalement, /resultats refetchera depuis API
              console.warn("[analyse] sessionStorage indisponible, redirect sans cache", storageErr);
            }
          }

          router.push(
            `/resultats/${submitted.job_id}?ticker=${encodeURIComponent(label)}&kind=${resolved.kind}`
          );
        } else {
          setError(finalJob.error || "Erreur inconnue");
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Erreur API";
        // Cas spécial : job perdu côté backend (Railway redémarré ou job évincé)
        if (/\/jobs\/.*failed \(404\)/.test(msg) || msg.includes("404")) {
          setError(
            "Le serveur d'analyse a été redémarré et l'analyse a été perdue avant la fin. Cela peut arriver lors d'un déploiement. Relancez simplement l'analyse — elle reprendra de zéro."
          );
        } else {
          setError(msg);
        }
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
          <p className="text-sm text-ink-600 mb-6 leading-relaxed">{error}</p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => window.location.reload()}
              className="btn-primary"
            >
              Relancer l&apos;analyse
            </button>
            <button onClick={() => router.push("/app")} className="btn-secondary">
              Retour à l&apos;accueil
            </button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  // Style Streamlit : gros titre TICKER + barre progression + texte étape en dessous
  const progress = steps.length > 0 ? Math.min(((stepIdx + 1) / steps.length) * 100, 100) : 0;
  const currentStep = steps[stepIdx] || "Initialisation du graphe d'analyse...";

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-2xl mx-auto px-6 py-20 w-full">
        {/* Gros titre TICKER centré */}
        <div className="text-center mb-12 animate-fade-in">
          <h1 className="text-5xl sm:text-6xl font-bold text-ink-900 tracking-tight mb-4">
            {query}
          </h1>
          <p className="text-sm text-ink-500">
            Analyse en cours — veuillez patienter
          </p>
        </div>

        {/* Barre de progression horizontale */}
        <div className="max-w-md mx-auto mb-3">
          <div className="w-full h-1.5 bg-ink-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-navy-500 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Texte étape en cours sous la barre */}
        <p className="text-center text-xs text-ink-500 mb-12">
          {currentStep}
        </p>

        {/* Search bar grisée (style Streamlit) */}
        <div className="max-w-md mx-auto space-y-3">
          <div className="w-full px-4 py-3 rounded-md border border-ink-200 bg-ink-50 text-sm text-ink-400">
            {query}
          </div>
          <div className="w-full px-4 py-3 rounded-md bg-ink-200 text-center text-sm text-ink-500 cursor-not-allowed">
            Analyser →
          </div>
        </div>

        <p className="text-xs text-ink-400 text-center mt-8 italic">
          {kind === "indice"
            ? "Analyse d'un indice complet. ~5 à 8 minutes."
            : kind === "secteur"
            ? "Analyse sectorielle multi-sociétés. ~2 à 4 minutes."
            : "Analyse institutionnelle. ~1 à 3 minutes."}
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
