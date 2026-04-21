"use client";

import { useEffect, useState } from "react";
import { Download, CheckCircle2, Monitor } from "lucide-react";
import toast from "react-hot-toast";

interface BIP extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/**
 * Bouton "Installer FinSight" à mettre dans /parametres ou footer.
 * Détecte 3 états :
 *  - déjà installé (display-mode standalone) → « Installée » disabled
 *  - install dispo (deferred prompt capturé) → bouton actif
 *  - iOS Safari → instructions manuelles
 *  - autres (Firefox mobile, non-supported) → bouton caché
 */
export function InstallAppButton() {
  const [deferred, setDeferred] = useState<BIP | null>(null);
  const [installed, setInstalled] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [showIOSHelp, setShowIOSHelp] = useState(false);

  useEffect(() => {
    // Déjà installé ?
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (window.navigator as unknown as { standalone?: boolean }).standalone === true;
    setInstalled(standalone);

    // iOS ?
    const ua = navigator.userAgent;
    setIsIOS(/iPad|iPhone|iPod/.test(ua));

    // Capture prompt
    function onBIP(e: Event) {
      e.preventDefault();
      setDeferred(e as BIP);
    }
    window.addEventListener("beforeinstallprompt", onBIP);

    // Quand installation réussit
    function onInstalled() {
      setInstalled(true);
      setDeferred(null);
      toast.success("FinSight installée sur votre appareil");
    }
    window.addEventListener("appinstalled", onInstalled);

    return () => {
      window.removeEventListener("beforeinstallprompt", onBIP);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  async function click() {
    if (isIOS && !deferred) {
      setShowIOSHelp(true);
      return;
    }
    if (!deferred) {
      toast.error("Install non supporté — copiez l'URL dans la barre Chrome et choisissez « Installer ».");
      return;
    }
    await deferred.prompt();
    const res = await deferred.userChoice;
    if (res.outcome === "accepted") {
      toast.success("Installation en cours…");
    }
    setDeferred(null);
  }

  if (installed) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-semibold">
        <CheckCircle2 className="w-4 h-4" />
        Application installée
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={click}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-navy-500 hover:bg-navy-600 text-white text-sm font-semibold transition-colors"
      >
        {isIOS ? <Monitor className="w-4 h-4" /> : <Download className="w-4 h-4" />}
        {isIOS ? "Installer sur iPhone" : "Installer FinSight"}
      </button>

      {showIOSHelp && (
        <div className="mt-3 text-xs text-ink-700 bg-amber-50 border border-amber-200 rounded p-3 max-w-md">
          <div className="font-semibold mb-1">Installation iOS Safari :</div>
          <ol className="list-decimal list-inside space-y-0.5">
            <li>Tapez sur le bouton <strong>Partager</strong> ⎋ en bas de Safari</li>
            <li>Faites défiler et sélectionnez <strong>« Sur l&apos;écran d&apos;accueil »</strong></li>
            <li>Confirmez avec <strong>« Ajouter »</strong></li>
          </ol>
        </div>
      )}
    </>
  );
}
