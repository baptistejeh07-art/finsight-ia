"use client";

import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function PWAInstaller() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Register service worker
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }

    // Check dismissed state
    try {
      if (localStorage.getItem("pwa-install-dismissed") === "1") setDismissed(true);
    } catch {}

    function onBIP(e: Event) {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    }
    window.addEventListener("beforeinstallprompt", onBIP);
    return () => window.removeEventListener("beforeinstallprompt", onBIP);
  }, []);

  async function install() {
    if (!deferred) return;
    await deferred.prompt();
    const res = await deferred.userChoice;
    setDeferred(null);
    if (res.outcome === "dismissed") {
      try { localStorage.setItem("pwa-install-dismissed", "1"); } catch {}
      setDismissed(true);
    }
  }

  function dismiss() {
    try { localStorage.setItem("pwa-install-dismissed", "1"); } catch {}
    setDismissed(true);
  }

  if (!deferred || dismissed) return null;

  return (
    <div className="fixed bottom-4 right-4 left-4 md:left-auto md:max-w-sm z-50 bg-white dark:bg-ink-900 border border-border-default rounded-lg shadow-xl p-4">
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-10 h-10 rounded-md bg-accent-primary/10 flex items-center justify-center">
          <Download className="w-5 h-5 text-accent-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-text-primary">Installer FinSight</div>
          <div className="text-xs text-text-muted mt-0.5">
            Accès rapide depuis votre écran d&apos;accueil, notifications, mode plein écran.
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={install}
              className="px-3 py-1.5 rounded-md bg-accent-primary text-accent-primary-fg text-xs font-semibold"
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
