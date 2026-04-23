"use client";

import { useEffect, useState } from "react";
import { Download, X, Monitor, CheckCircle2 } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/**
 * Déclencheur d'installation PWA + détection état "installed".
 *
 * Affiche une bannière discrète bottom-right au 2e visit quand le navigateur
 * supporte l'install. Stocké en localStorage pour ne pas harceler.
 *
 * Détecte aussi si l'utilisateur est déjà dans l'app installée (display-mode
 * standalone) — dans ce cas : zéro UI (l'utilisateur est déjà conquis).
 *
 * Safari iOS n'émet pas beforeinstallprompt → fallback instructions manuelles
 * via UA detection.
 */
export function PWAInstaller() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [showIOS, setShowIOS] = useState(false);

  useEffect(() => {
    // Service worker — register avec updateViaCache="none" pour que Chrome
    // ne mette JAMAIS /sw.js en cache HTTP 24h (sinon les PWA installées
    // continuent de servir du vieux code tant que la clé HTTP n'a pas expiré).
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js", { updateViaCache: "none" })
        .then((reg) => {
          // Check for update immediately + toutes les 60 secondes tant que l'onglet
          // est ouvert. Permet à la PWA de récupérer les déploiements frais
          // sans attendre 24h.
          reg.update().catch(() => {});
          const intervalId = setInterval(() => {
            reg.update().catch(() => {});
          }, 60_000);
          // Quand un nouveau SW prend le contrôle (après install + activate),
          // reload la page pour charger la nouvelle version du HTML/JS.
          let reloaded = false;
          navigator.serviceWorker.addEventListener("controllerchange", () => {
            if (reloaded) return;
            reloaded = true;
            window.location.reload();
          });
          return () => clearInterval(intervalId);
        })
        .catch(() => {});
    }

    // Détection standalone mode (app déjà installée ET lancée via raccourci)
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.matchMedia("(display-mode: window-controls-overlay)").matches ||
      // iOS Safari
      (window.navigator as unknown as { standalone?: boolean }).standalone === true;
    setIsStandalone(standalone);

    // iOS detection
    const ua = navigator.userAgent;
    const iOS = /iPad|iPhone|iPod/.test(ua) && !(window as Window & { MSStream?: unknown }).MSStream;
    setIsIOS(iOS);

    // Dismissed memo
    try {
      if (localStorage.getItem("pwa-install-dismissed") === "1") setDismissed(true);
    } catch {}

    // Compteur de visites — affiche prompt au 2e visit seulement (moins intrusif)
    let visits = 0;
    try {
      visits = parseInt(localStorage.getItem("pwa-visits") || "0", 10) + 1;
      localStorage.setItem("pwa-visits", String(visits));
    } catch {}

    function onBIP(e: Event) {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    }
    window.addEventListener("beforeinstallprompt", onBIP);

    // Si iOS + >=2 visites + non installée + non dismissed → prompt iOS
    if (iOS && !standalone && visits >= 2) {
      try {
        if (localStorage.getItem("pwa-install-dismissed") !== "1") {
          // Légère latence pour ne pas flash au load
          setTimeout(() => setShowIOS(true), 3000);
        }
      } catch {}
    }

    return () => window.removeEventListener("beforeinstallprompt", onBIP);
  }, []);

  async function install() {
    if (!deferred) return;
    await deferred.prompt();
    const res = await deferred.userChoice;
    setDeferred(null);
    if (res.outcome === "accepted") {
      // Track install accepted (stats)
      try { localStorage.setItem("pwa-installed", "1"); } catch {}
    } else {
      try { localStorage.setItem("pwa-install-dismissed", "1"); } catch {}
      setDismissed(true);
    }
  }

  function dismiss() {
    try { localStorage.setItem("pwa-install-dismissed", "1"); } catch {}
    setDismissed(true);
    setShowIOS(false);
  }

  // Si user est DANS l'app installée → rien à afficher (on est déjà conquis)
  if (isStandalone) return null;

  // iOS custom prompt
  if (showIOS && !dismissed) {
    return (
      <div className="fixed bottom-4 right-4 left-4 md:left-auto md:max-w-sm z-50 bg-white dark:bg-ink-900 border border-border-default rounded-lg shadow-xl p-4 animate-slide-up">
        <div className="flex items-start gap-3">
          <div className="shrink-0 w-10 h-10 rounded-md bg-accent-primary/10 flex items-center justify-center">
            <Monitor className="w-5 h-5 text-accent-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-text-primary">Installer FinSight sur iPhone</div>
            <div className="text-xs text-text-muted mt-1">
              Appuyez sur <span className="inline-block mx-0.5">⎋</span> Partager en bas de Safari,
              puis <strong>« Sur l&apos;écran d&apos;accueil »</strong>.
            </div>
          </div>
          <button onClick={dismiss} className="text-text-muted hover:text-text-primary">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // Android/Desktop prompt standard
  if (!deferred || dismissed) return null;

  return (
    <div className="fixed bottom-4 right-4 left-4 md:left-auto md:max-w-sm z-50 bg-white dark:bg-ink-900 border border-border-default rounded-lg shadow-xl p-4 animate-slide-up">
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-10 h-10 rounded-md bg-accent-primary/10 flex items-center justify-center">
          <Download className="w-5 h-5 text-accent-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-text-primary">Installer FinSight</div>
          <div className="text-xs text-text-muted mt-0.5">
            Raccourci bureau, plein écran, notifications — comme une vraie app.
          </div>
          <ul className="mt-2 space-y-0.5 text-[10px] text-text-muted">
            <li className="flex items-center gap-1"><CheckCircle2 className="w-2.5 h-2.5 text-accent-primary" /> Ouvre en 1 clic depuis le bureau</li>
            <li className="flex items-center gap-1"><CheckCircle2 className="w-2.5 h-2.5 text-accent-primary" /> Pas de barre navigateur</li>
            <li className="flex items-center gap-1"><CheckCircle2 className="w-2.5 h-2.5 text-accent-primary" /> Partage naturel de tickers</li>
          </ul>
          <div className="mt-3 flex gap-2">
            <button
              onClick={install}
              className="px-3 py-1.5 rounded-md bg-accent-primary text-accent-primary-fg text-xs font-semibold hover:bg-accent-primary-hover transition-colors"
            >
              Installer
            </button>
            <button
              onClick={dismiss}
              className="px-3 py-1.5 rounded-md text-xs text-text-muted hover:bg-surface-muted"
            >
              Plus tard
            </button>
          </div>
        </div>
        <button onClick={dismiss} className="text-text-muted hover:text-text-primary">
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
