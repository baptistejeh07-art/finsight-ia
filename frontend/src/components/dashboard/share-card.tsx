"use client";

import { useEffect, useState } from "react";
import { Share2 } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";
import { saveAnalysisToHistory, type HistoryKind } from "@/hooks/use-analyses-history";
import { ShareModal } from "@/components/share-modal";

interface Props {
  jobId: string;
  kind: HistoryKind;
  label: string;
  ticker?: string;
}

/**
 * Bouton "Partager" — vérifie/crée l'entrée historique puis ouvre la ShareModal.
 * Le partage requiert un history_id (donc l'analyse doit être persistée Supabase).
 */
export function ShareCard({ jobId, kind, label, ticker }: Props) {
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(async ({ data }) => {
      if (!data.user) return;
      setLoggedIn(true);
      const { data: existing } = await supabase
        .from("analyses_history")
        .select("id")
        .eq("user_id", data.user.id)
        .eq("job_id", jobId)
        .maybeSingle();
      if (existing?.id) setHistoryId(existing.id as string);
    });
  }, [jobId]);

  async function ensureSavedAndOpen() {
    if (!loggedIn) { toast.error("Connectez-vous pour partager"); return; }
    if (historyId) { setModalOpen(true); return; }

    setLoadingId(true);
    try {
      let snapshot: unknown = null;
      try {
        const raw = sessionStorage.getItem(`analysis_${jobId}`);
        if (raw) snapshot = JSON.parse(raw);
      } catch {}
      if (!snapshot) {
        toast.error("Session expirée, rechargez la page");
        return;
      }
      const res = await saveAnalysisToHistory({ job_id: jobId, kind, label, ticker, data: snapshot });
      if (!res.saved) {
        toast.error(res.error || "Échec sauvegarde");
        return;
      }
      // Re-fetch the id (avoid race)
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data: row } = await supabase
        .from("analyses_history")
        .select("id")
        .eq("user_id", user.id)
        .eq("job_id", jobId)
        .maybeSingle();
      if (row?.id) {
        setHistoryId(row.id as string);
        setModalOpen(true);
      } else {
        toast.error("Sauvegarde non confirmée");
      }
    } finally {
      setLoadingId(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={ensureSavedAndOpen}
        disabled={loadingId}
        className="w-full h-full flex items-center justify-center gap-2 rounded-md border border-ink-200 bg-white hover:bg-ink-50 px-4 py-3 text-sm font-semibold text-ink-800 transition-colors"
      >
        <Share2 className="w-4 h-4" />
        {loadingId ? "Préparation…" : "Partager"}
      </button>
      <ShareModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        historyId={historyId}
        analysisLabel={label}
      />
    </>
  );
}
