"use client";

import { useState } from "react";
import { Sparkles, Loader2, Download, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";

interface PortraitJob {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  progress?: number;
  pdf_url?: string;
  error?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function PortraitCard({
  ticker,
  companyName,
}: {
  ticker: string;
  companyName: string;
}) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    setPdfUrl(null);
    setProgress(0);

    try {
      // Submit job
      const r = await fetch(`${API_BASE}/portrait/societe`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ticker }),
      });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`API ${r.status} : ${txt}`);
      }
      const submitted: { job_id: string } = await r.json();

      // Poll toutes les 3s jusqu'à done/error
      const pollUntilDone = async (): Promise<PortraitJob> => {
        for (let i = 0; i < 200; i++) {
          await new Promise((res) => setTimeout(res, 3000));
          const pr = await fetch(`${API_BASE}/portrait/${submitted.job_id}`);
          if (!pr.ok) {
            if (pr.status === 404) throw new Error("Job introuvable (serveur redémarré). Relancez.");
            continue;
          }
          const job: PortraitJob = await pr.json();
          if (typeof job.progress === "number") setProgress(job.progress);
          if (job.status === "done") return job;
          if (job.status === "error") throw new Error(job.error || "Erreur génération");
        }
        throw new Error("Timeout (>10 min)");
      };

      const final = await pollUntilDone();
      if (final.pdf_url) {
        setPdfUrl(final.pdf_url);
        toast.success("Portrait généré ! Téléchargez-le.");
      } else {
        throw new Error("PDF manquant");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-gradient-to-br from-navy-50 to-white border border-navy-200 rounded-md p-5">
      <div className="flex items-start gap-3 mb-3">
        <div className="shrink-0 w-9 h-9 rounded-md bg-navy-500 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div>
          <div className="text-sm font-bold text-ink-900">
            Portrait d&apos;entreprise
          </div>
          <div className="text-xs text-ink-600 mt-0.5">
            Rapport qualitatif 15 pages — dirigeants, ADN, signaux stratégiques.
          </div>
        </div>
      </div>

      <ul className="text-[11px] text-ink-600 mb-4 space-y-1 pl-9">
        <li>• Profil CEO + management + photos officielles</li>
        <li>• Histoire, ADN, crises traversées</li>
        <li>• Modèle économique + paysage concurrentiel</li>
        <li>• Stratégie, risques, devil&apos;s advocate, verdict</li>
      </ul>

      {/* Progress bar pendant la génération */}
      {busy && (
        <div className="mb-3">
          <div className="flex items-center gap-2 text-[11px] text-ink-700 mb-1.5">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Génération en cours… {progress > 0 ? `${progress}%` : ""}</span>
          </div>
          <div className="w-full h-1 bg-ink-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-navy-500 transition-all"
              style={{ width: `${Math.max(progress, 5)}%` }}
            />
          </div>
        </div>
      )}

      {/* Erreur éventuelle */}
      {error && !busy && (
        <div className="mb-3 flex items-start gap-2 px-2.5 py-2 bg-signal-sell/10 border border-signal-sell/20 rounded text-[11px] text-signal-sell">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span className="leading-snug">{error}</span>
        </div>
      )}

      {/* CTA principal */}
      {!pdfUrl && (
        <button
          onClick={handleClick}
          disabled={busy}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded bg-navy-500 text-white text-xs font-semibold hover:bg-navy-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Génération en cours…
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              Générer le portrait de {ticker || companyName}
            </>
          )}
        </button>
      )}

      {/* Download après succès */}
      {pdfUrl && (
        <a
          href={pdfUrl}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded bg-signal-buy text-white text-xs font-semibold hover:opacity-90 transition-opacity"
        >
          <Download className="w-3.5 h-3.5" />
          Télécharger le portrait PDF
        </a>
      )}

      <div className="text-[10px] text-ink-500 italic text-center mt-2">
        Génération typique 60-120 s — données yfinance + Wikipedia + IA cascade
      </div>
    </div>
  );
}
