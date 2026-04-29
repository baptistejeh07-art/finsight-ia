"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GitCompare } from "lucide-react";
import toast from "react-hot-toast";
import { submitCmpSecteurJob } from "@/lib/api";

interface Props {
  /** Nom de l'indice analysé (ex: "CAC 40", "S&P 500"). */
  universe: string;
  /** Liste optionnelle des secteurs présents dans l'indice (pour pré-remplir le datalist). */
  availableSectors?: string[];
}

const POPULAR_SECTORS = [
  "Technology",
  "Healthcare",
  "Financials",
  "Consumer Discretionary",
  "Consumer Defensive",
  "Industrials",
  "Energy",
  "Materials",
  "Utilities",
  "Real Estate",
  "Communication Services",
];

/**
 * Phase 2 roadmap (project_roadmap_long_terme.md) — Comparaison de 2 secteurs
 * AU SEIN d'un indice spécifique. Distinct du cmp_secteur "global" qui passe
 * par /comparatif/secteur (qui peut comparer Tech US vs Tech FR par ex.).
 *
 * Ici : l'utilisateur analyse CAC 40 et veut comparer Industrials vs Financials
 * **dans le CAC 40 uniquement** → universe est forcé à l'indice courant.
 */
export function IndiceSectorCompareLauncher({ universe, availableSectors }: Props) {
  const router = useRouter();
  const [sectorA, setSectorA] = useState("");
  const [sectorB, setSectorB] = useState("");
  const [busy, setBusy] = useState(false);

  // Datalist suggestions = secteurs réellement présents dans l'indice (priorité),
  // sinon liste populaire générique en fallback.
  const suggestions = (availableSectors && availableSectors.length > 0)
    ? availableSectors
    : POPULAR_SECTORS;

  async function handleCompare() {
    const a = sectorA.trim();
    const b = sectorB.trim();
    if (!a || !b) {
      toast.error("Saisissez 2 secteurs");
      return;
    }
    if (a.toLowerCase() === b.toLowerCase()) {
      toast.error("Choisissez 2 secteurs différents");
      return;
    }
    setBusy(true);
    try {
      // Les 2 secteurs comparés DANS le même univers (l'indice courant)
      const res = await submitCmpSecteurJob(a, universe, b, universe);
      router.push(
        `/analyse?id=${res.job_id}&kind=comparatif&label=${encodeURIComponent(
          `${a} vs ${b} (${universe})`
        )}`
      );
    } catch (e) {
      toast.error("Impossible de lancer la comparaison");
      console.error(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[1.5px] text-ink-500 font-semibold mb-2">
        <GitCompare className="w-3.5 h-3.5" />
        Comparer 2 secteurs
      </div>
      <p className="text-xs text-ink-600 mb-3">
        Comparer 2 secteurs au sein de <span className="font-semibold">{universe}</span> uniquement
        (analyse parallèle sur le même univers).
      </p>
      <input
        type="text"
        value={sectorA}
        onChange={(e) => setSectorA(e.target.value)}
        placeholder="Secteur A (ex: Technology)"
        list="indice-sector-suggestions"
        className="w-full px-3 py-2 border border-ink-200 rounded text-sm mb-2 focus:outline-none focus:border-navy-500"
        onKeyDown={(e) => e.key === "Enter" && !busy && handleCompare()}
      />
      <input
        type="text"
        value={sectorB}
        onChange={(e) => setSectorB(e.target.value)}
        placeholder="Secteur B (ex: Financials)"
        list="indice-sector-suggestions"
        className="w-full px-3 py-2 border border-ink-200 rounded text-sm mb-2 focus:outline-none focus:border-navy-500"
        onKeyDown={(e) => e.key === "Enter" && !busy && handleCompare()}
      />
      <datalist id="indice-sector-suggestions">
        {suggestions.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      <button
        type="button"
        onClick={handleCompare}
        disabled={busy || !sectorA.trim() || !sectorB.trim()}
        className={
          "w-full py-2 rounded text-sm font-semibold transition-colors " +
          (busy
            ? "bg-ink-200 text-ink-500 cursor-wait"
            : "bg-navy-500 text-white hover:bg-navy-600 disabled:bg-ink-200 disabled:text-ink-500 disabled:cursor-not-allowed")
        }
      >
        {busy ? "Lancement…" : "Comparer"}
      </button>
      <p className="mt-auto pt-2 text-[10px] text-ink-500 leading-snug">
        Génère PDF, PPTX et Excel comparatifs en ~2 min.
      </p>
    </div>
  );
}
