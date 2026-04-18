"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { submitCmpSocieteJob } from "@/lib/api";

export function CompareCard({ targetTicker }: { targetTicker: string }) {
  const router = useRouter();
  const [other, setOther] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleCompare() {
    const t = other.trim().toUpperCase();
    if (!t) return;
    if (t === targetTicker.toUpperCase()) {
      toast.error("Choisissez un ticker différent");
      return;
    }
    setBusy(true);
    try {
      const res = await submitCmpSocieteJob(targetTicker, t);
      router.push(`/analyse?id=${res.job_id}&kind=comparatif&label=${targetTicker} vs ${t}`);
    } catch (e) {
      toast.error("Erreur de lancement comparatif");
      console.error(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md p-5">
      <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
        Analyse comparative
      </div>
      <p className="text-xs text-ink-600 mb-3">
        Comparer <span className="font-mono font-semibold">{targetTicker}</span> avec une autre société
      </p>
      <input
        type="text"
        value={other}
        onChange={(e) => setOther(e.target.value)}
        placeholder="Par ex. MSFT"
        className="w-full px-3 py-2 border border-ink-200 rounded text-sm font-mono uppercase mb-3 focus:outline-none focus:border-navy-500"
        onKeyDown={(e) => e.key === "Enter" && !busy && handleCompare()}
      />
      <button
        onClick={handleCompare}
        disabled={busy || !other.trim()}
        className="w-full px-3 py-2 rounded bg-navy-500 text-white text-xs font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {busy ? "Lancement..." : "Comparer"}
      </button>
    </div>
  );
}
