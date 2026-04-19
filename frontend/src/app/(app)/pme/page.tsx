"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Info, Building2 } from "lucide-react";
import { analyzePmeSync } from "@/lib/api";

export default function PmePage() {
  const router = useRouter();
  const [siren, setSiren] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    const cleanSiren = siren.replace(/\s/g, "");
    if (!/^\d{9}$/.test(cleanSiren)) {
      setError("Le SIREN doit contenir exactement 9 chiffres.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await analyzePmeSync(cleanSiren);
      if (res.success) {
        try {
          sessionStorage.setItem(
            `analysis_${res.request_id}`,
            JSON.stringify({
              success: true,
              request_id: res.request_id,
              elapsed_ms: res.elapsed_ms,
              data: res.data,
              files: res.files,
              kind: "pme",
              label: (res.data as { denomination?: string })?.denomination || cleanSiren,
            })
          );
        } catch {}
        router.push(
          `/resultats/${res.request_id}?ticker=${encodeURIComponent(
            (res.data as { denomination?: string })?.denomination || cleanSiren
          )}&kind=pme`
        );
      } else {
        setError(res.error || "Erreur inconnue");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur API");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-md bg-navy-50 flex items-center justify-center">
          <Building2 className="w-5 h-5 text-navy-500" />
        </div>
        <h1 className="text-3xl font-bold text-ink-900">Analyse PME non cotée</h1>
      </div>
      <p className="text-ink-600 mb-8 max-w-2xl">
        Analyse financière complète d&apos;une société française non cotée via son SIREN :
        identité, dirigeants, SIG 5 ans, ratios, benchmark sectoriel, scoring santé &
        bankabilité, Altman Z, procédures BODACC. Sources : Pappers API + BODACC open data.
      </p>

      <form onSubmit={handleAnalyze} className="bg-white border border-ink-200 rounded-md p-6 mb-6">
        <label className="block text-sm font-medium text-ink-700 mb-2">
          SIREN de la société
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={siren}
            onChange={(e) => setSiren(e.target.value)}
            placeholder="ex : 552 032 534"
            className="flex-1 px-4 py-3 border border-ink-200 rounded-md text-base font-mono focus:outline-none focus:border-navy-500"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || siren.trim().length < 9}
            className="px-6 py-3 rounded-md bg-navy-500 text-white font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analyse…
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                Analyser
              </>
            )}
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-signal-sell">{error}</p>}
        <p className="mt-2 text-xs text-ink-500">
          9 chiffres, espaces ignorés. Exemples : 552 032 534 (Danone), 552 081 317 (EDF).
        </p>
      </form>

      <div className="bg-navy-50 border border-navy-200 rounded-md p-5 flex items-start gap-3">
        <Info className="w-5 h-5 text-navy-500 shrink-0 mt-0.5" />
        <div className="text-sm text-ink-700">
          <p className="font-medium text-ink-900 mb-1">Comment ça marche ?</p>
          <ul className="space-y-1 text-ink-600">
            <li>• <strong>Identité & dirigeants</strong> récupérés via Pappers API</li>
            <li>• <strong>Comptes 5 ans</strong> téléchargés depuis la liasse fiscale XLSX Pappers (si publics)</li>
            <li>• <strong>Benchmark</strong> vs 50 profils sectoriels FinSight ou peers réels</li>
            <li>• <strong>Scoring</strong> Altman Z (non coté) + santé FinSight + bankabilité + BODACC</li>
            <li>• <strong>Livrables</strong> : PDF 12p (contrôle de gestion), XLSX 5 feuilles, PPTX 10 slides</li>
          </ul>
          <p className="mt-2 text-xs text-ink-500">
            Cette analyse ne constitue pas un conseil en investissement (MiFID II).
          </p>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-3 gap-4 text-center">
        <ExampleCard siren="552032534" name="Danone" sector="Holding" onClick={setSiren} />
        <ExampleCard siren="552081317" name="EDF" sector="Énergie" onClick={setSiren} />
        <ExampleCard siren="542107651" name="LVMH" sector="Luxe" onClick={setSiren} />
      </div>
    </div>
  );
}

function ExampleCard({
  siren,
  name,
  sector,
  onClick,
}: {
  siren: string;
  name: string;
  sector: string;
  onClick: (s: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onClick(siren)}
      className="bg-white border border-ink-200 rounded-md px-3 py-2 hover:border-navy-500 hover:bg-navy-50 transition-colors text-left"
    >
      <div className="text-xs text-ink-500 uppercase tracking-wider">{sector}</div>
      <div className="text-sm font-semibold text-ink-900">{name}</div>
      <div className="text-xs font-mono text-ink-500">{siren}</div>
    </button>
  );
}
