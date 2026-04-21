"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GitCompare } from "lucide-react";
import toast from "react-hot-toast";
import { submitCmpSecteurJob } from "@/lib/api";

interface Props {
  sector: string;
  universe: string;
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
 * Carte "Comparer ce secteur" — parité avec CompareCard société.
 * L'utilisateur saisit un autre secteur (dans le même univers par
 * défaut) et on lance un job /cmp/secteur.
 */
export function SectorCompareLauncher({ sector, universe }: Props) {
  const router = useRouter();
  const [other, setOther] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleCompare() {
    const s = other.trim();
    if (!s) return;
    if (s.toLowerCase() === sector.toLowerCase()) {
      toast.error("Choisissez un secteur différent");
      return;
    }
    setBusy(true);
    try {
      const res = await submitCmpSecteurJob(sector, universe, s, universe);
      router.push(
        `/analyse?id=${res.job_id}&kind=comparatif&label=${encodeURIComponent(
          `${sector} vs ${s}`
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
        Comparer ce secteur
      </div>
      <p className="text-xs text-ink-600 mb-3">
        Lancez un comparatif entre <span className="font-semibold">{sector}</span> et un autre
        secteur de <span className="font-semibold">{universe}</span>.
      </p>
      <input
        type="text"
        value={other}
        onChange={(e) => setOther(e.target.value)}
        placeholder="Ex: Healthcare, Energy…"
        list="sector-suggestions"
        className="w-full px-3 py-2 border border-ink-200 rounded text-sm mb-2 focus:outline-none focus:border-navy-500"
        onKeyDown={(e) => e.key === "Enter" && !busy && handleCompare()}
      />
      <datalist id="sector-suggestions">
        {POPULAR_SECTORS.filter((s) => s.toLowerCase() !== sector.toLowerCase()).map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      <button
        type="button"
        onClick={handleCompare}
        disabled={busy || !other.trim()}
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
