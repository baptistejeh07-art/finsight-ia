"use client";

import { useEffect, useState } from "react";
import { Building2, History, Download, Sparkles, X, ChevronRight } from "lucide-react";
import { useUserPreferences } from "@/hooks/use-user-preferences";

interface Step {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    icon: Sparkles,
    title: "Bienvenue dans FinSight IA",
    body: "Votre analyste financier propulsé par IA. En 2-3 minutes vous obtenez un rapport institutionnel complet (DCF, ratios, scénarios) sur n'importe quelle société, secteur ou indice.",
  },
  {
    icon: Building2,
    title: "1. Lancez une analyse",
    body: "Tapez un ticker (AAPL, MC.PA…), choisissez un secteur ou un indice depuis la page d'accueil. Vous pouvez aussi analyser les PME françaises non cotées via leur SIREN.",
  },
  {
    icon: History,
    title: "2. Retrouvez votre historique",
    body: "La sidebar gauche garde une trace de toutes vos analyses. Renommez-les, mettez-les en favori (étoile) et revenez dessus quand vous voulez sans relancer le calcul.",
  },
  {
    icon: Download,
    title: "3. Téléchargez vos livrables",
    body: "Chaque analyse génère un PDF (rapport), un PowerPoint (pitchbook) et un Excel (modèle). Tout est exportable depuis la sidebar « Livrables » ou la page de résultats.",
  },
];

export function OnboardingTour() {
  const { prefs, update, loading } = useUserPreferences();
  const [step, setStep] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (prefs.onboarded) return;
    setOpen(true);
  }, [loading, prefs.onboarded]);

  function finish() {
    update({ onboarded: true });
    setOpen(false);
  }
  function next() {
    if (step + 1 >= STEPS.length) finish();
    else setStep(step + 1);
  }

  if (!open) return null;
  const s = STEPS[step];
  const Icon = s.icon;
  const isLast = step + 1 >= STEPS.length;

  return (
    <div className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-ink-900 rounded-lg shadow-2xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border-default">
          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={
                  "h-1.5 rounded-full transition-all " +
                  (i === step ? "w-6 bg-accent-primary" : "w-1.5 bg-ink-200")
                }
              />
            ))}
          </div>
          <button
            onClick={finish}
            className="text-text-muted hover:text-text-primary transition-colors"
            title="Passer le tour"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-7">
          <div className="w-12 h-12 rounded-md bg-accent-primary/10 flex items-center justify-center mb-4">
            <Icon className="w-6 h-6 text-accent-primary" />
          </div>
          <h2 className="text-lg font-semibold text-text-primary mb-2">{s.title}</h2>
          <p className="text-sm text-text-secondary leading-relaxed">{s.body}</p>
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-t border-border-default bg-surface-muted/30">
          <button
            type="button"
            onClick={finish}
            className="text-xs text-text-muted hover:text-text-primary transition-colors"
          >
            Passer
          </button>
          <button
            type="button"
            onClick={next}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-accent-primary text-accent-primary-fg text-xs font-semibold hover:opacity-90 transition-opacity"
          >
            {isLast ? "Commencer" : "Suivant"}
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
