"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { analyzeSociete } from "@/lib/api";
import toast from "react-hot-toast";

const STEPS = [
  "Connexion aux sources financières",
  "Récupération des données yfinance",
  "Calcul des ratios sectoriels",
  "Génération des projections",
  "Analyse IA des fondamentaux",
  "Synthèse exécutive",
  "Génération PDF / PPTX / Excel",
];

function AnalyseContent() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q") || "";
  const devise = params.get("devise") || "USD";
  const scope = (params.get("scope") || "interface") as "interface" | "files";

  const [stepIdx, setStepIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) {
      router.push("/");
      return;
    }

    // Animation des étapes (purement visuel, pas réel)
    const interval = setInterval(() => {
      setStepIdx((i) => Math.min(i + 1, STEPS.length - 1));
    }, 8000);

    // Lance l'analyse réelle
    (async () => {
      try {
        // Détecte si c'est une société (ticker) ou autre
        const isTicker = /^[A-Z0-9.\-]{1,12}$/i.test(query);
        if (isTicker) {
          const result = await analyzeSociete(query, devise, scope);
          if (result.success) {
            // Stock le résultat dans sessionStorage pour la page résultats
            sessionStorage.setItem(
              `analysis_${result.request_id}`,
              JSON.stringify(result)
            );
            router.push(`/resultats/${result.request_id}?ticker=${query}`);
          } else {
            setError(result.error || "Erreur inconnue");
          }
        } else {
          // TODO : router secteur / indice
          toast.error("Analyse secteur/indice : bientôt disponible");
          setTimeout(() => router.push("/"), 2000);
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Erreur API";
        setError(msg);
      } finally {
        clearInterval(interval);
      }
    })();

    return () => clearInterval(interval);
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
            Génération de l&apos;analyse institutionnelle. ~1 à 3 minutes.
          </p>
        </div>

        {/* Steps */}
        <div className="card max-w-md mx-auto">
          <ul className="space-y-3">
            {STEPS.map((step, i) => (
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
