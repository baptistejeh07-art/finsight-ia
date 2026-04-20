"use client";

import { useEffect, useState } from "react";
import { Cookie } from "lucide-react";
import Link from "next/link";

const STORAGE_KEY = "finsight-cookie-consent";

type ConsentValue = "all" | "essential" | null;

export function CookieBanner() {
  const [consent, setConsent] = useState<ConsentValue>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as ConsentValue;
      if (stored === "all" || stored === "essential") setConsent(stored);
    } catch {}
  }, []);

  function choose(value: "all" | "essential") {
    try {
      localStorage.setItem(STORAGE_KEY, value);
      localStorage.setItem(STORAGE_KEY + "-date", new Date().toISOString());
    } catch {}
    setConsent(value);
  }

  if (!mounted || consent) return null;

  return (
    <div className="fixed bottom-0 inset-x-0 z-[100] p-4 md:p-6 pointer-events-none">
      <div className="max-w-4xl mx-auto bg-white dark:bg-ink-900 border border-border-default shadow-xl rounded-lg p-5 md:p-6 pointer-events-auto">
        <div className="flex gap-4 items-start">
          <div className="shrink-0 w-10 h-10 rounded-md bg-accent-primary/10 flex items-center justify-center">
            <Cookie className="w-5 h-5 text-accent-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-semibold text-text-primary mb-1">
              Votre vie privée compte
            </h2>
            <p className="text-xs text-text-muted leading-relaxed">
              FinSight utilise uniquement les cookies strictement nécessaires au
              fonctionnement du service (authentification, préférences). Vous
              pouvez accepter les cookies analytiques anonymisés pour nous aider
              à améliorer la plateforme. Plus d&apos;informations dans notre{" "}
              <Link href="/privacy" className="text-accent-primary underline">
                politique de confidentialité
              </Link>
              .
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => choose("essential")}
                className="px-4 py-2 rounded-md border border-border-default text-xs font-medium text-text-primary hover:bg-surface-muted transition-colors"
              >
                Essentiels uniquement
              </button>
              <button
                type="button"
                onClick={() => choose("all")}
                className="px-4 py-2 rounded-md bg-accent-primary text-accent-primary-fg text-xs font-semibold hover:opacity-90 transition-opacity"
              >
                Tout accepter
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
