"use client";

import { useState } from "react";
import { Sparkles, Loader2, Download, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";
import { useI18n } from "@/i18n/provider";

interface PortraitJob {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  progress?: number;
  result?: { files?: { pdf?: string } };
  error?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function fileUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}/file/${path}`;
}

export function PortraitCard({
  ticker,
  companyName,
}: {
  ticker: string;
  companyName: string;
}) {
  const { t } = useI18n();
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
          const pr = await fetch(`${API_BASE}/jobs/${submitted.job_id}`);
          if (!pr.ok) {
            if (pr.status === 404) {
              throw new Error(t("kpi.portrait_error_job_lost"));
            }
            continue;
          }
          const job: PortraitJob = await pr.json();
          if (typeof job.progress === "number") setProgress(job.progress);
          if (job.status === "done") return job;
          if (job.status === "error") throw new Error(job.error || t("kpi.portrait_error_generic"));
        }
        throw new Error(t("kpi.portrait_timeout"));
      };

      const final = await pollUntilDone();
      const pdfPath = final.result?.files?.pdf;
      if (pdfPath) {
        const url = fileUrl(pdfPath);
        setPdfUrl(url);
        toast.success(t("kpi.portrait_success"));
      } else {
        throw new Error(t("kpi.portrait_error_generic"));
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("common.error");
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-gradient-to-br from-navy-50 to-white border border-navy-200 rounded-md p-5 h-full overflow-auto">
      <div className="flex items-start gap-3 mb-3">
        <div className="shrink-0 w-9 h-9 rounded-md bg-navy-500 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div>
          <div className="text-sm font-bold text-ink-900">
            {t("kpi.portrait_title")}
          </div>
          <div className="text-xs text-ink-600 mt-0.5">
            {t("kpi.portrait_subtitle")}
          </div>
        </div>
      </div>

      <ul className="text-[11px] text-ink-600 mb-4 space-y-1 pl-9">
        <li>• {t("kpi.portrait_bullet_1")}</li>
        <li>• {t("kpi.portrait_bullet_2")}</li>
        <li>• {t("kpi.portrait_bullet_3")}</li>
        <li>• {t("kpi.portrait_bullet_4")}</li>
      </ul>

      {/* Progress bar pendant la génération */}
      {busy && (
        <div className="mb-3">
          <div className="flex items-center gap-2 text-[11px] text-ink-700 mb-1.5">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>{t("kpi.portrait_generating")} {progress > 0 ? `${progress}%` : ""}</span>
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
              {t("kpi.portrait_generating")}
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              {t("kpi.portrait_cta")} {ticker || companyName}
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
          {t("kpi.portrait_download")}
        </a>
      )}

      <div className="text-[10px] text-ink-500 italic text-center mt-2">
        {t("kpi.portrait_hint")}
      </div>
    </div>
  );
}
