"use client";

import { useEffect, useState } from "react";
import { Bookmark, BookmarkCheck, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";
import { saveAnalysisToHistory, type HistoryKind } from "@/hooks/use-analyses-history";
import { useI18n } from "@/i18n/provider";

interface Props {
  jobId: string;
  kind: HistoryKind;
  label: string;
  ticker?: string;
}

/**
 * Bouton "Garder en mémoire" — sauvegarde l'analyse courante (depuis
 * sessionStorage analysis_{jobId}) dans la table analyses_history.
 *
 * Doit être intégré comme bloc GridBlock dans EditableGrid.
 */
export function SaveToHistoryCard({ jobId, kind, label, ticker }: Props) {
  const { t } = useI18n();
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);
  const [alreadySaved, setAlreadySaved] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      const connected = !!data.user;
      setLoggedIn(connected);
      // Check si déjà sauvé
      if (connected) {
        supabase
          .from("analyses_history")
          .select("id")
          .eq("user_id", data.user!.id)
          .eq("job_id", jobId)
          .maybeSingle()
          .then(({ data: existing }) => {
            if (existing) setAlreadySaved(true);
          });
      }
    });
  }, [jobId]);

  async function handleSave() {
    if (state === "saving") return;
    setState("saving");

    let snapshot: unknown = null;
    try {
      const raw = sessionStorage.getItem(`analysis_${jobId}`);
      if (raw) snapshot = JSON.parse(raw);
    } catch {}
    if (!snapshot) {
      toast.error(t("results.kept_error_session"));
      setState("error");
      return;
    }

    const res = await saveAnalysisToHistory({
      job_id: jobId,
      kind,
      label,
      ticker,
      data: snapshot,
    });

    if (res.saved) {
      setState("saved");
      setAlreadySaved(true);
      toast.success(t("results.kept_success"));
    } else {
      setState("error");
      toast.error(res.error || t("results.kept_error_save"));
    }
  }

  if (loggedIn === false) {
    return (
      <div className="bg-white border border-ink-200 rounded-md p-4 h-full flex flex-col items-center justify-center text-center gap-2">
        <Bookmark className="w-6 h-6 text-ink-400" />
        <div className="text-sm font-medium text-ink-800">{t("results.keep_in_memory")}</div>
        <div className="text-xs text-ink-500 max-w-[220px]">
          {t("results.kept_hint_default")}
        </div>
      </div>
    );
  }

  const saved = alreadySaved || state === "saved";
  const busy = state === "saving";

  return (
    <button
      type="button"
      onClick={handleSave}
      disabled={busy || saved}
      className={
        "w-full h-full p-4 rounded-md border flex flex-col items-center justify-center text-center gap-2 transition-all " +
        (saved
          ? "bg-signal-buy/5 border-signal-buy/30 text-signal-buy cursor-default"
          : busy
          ? "bg-ink-50 border-ink-200 text-ink-500 cursor-wait"
          : "bg-white border-ink-200 hover:border-navy-500 hover:bg-navy-50 text-ink-800")
      }
    >
      {busy ? (
        <Loader2 className="w-6 h-6 animate-spin" />
      ) : saved ? (
        <BookmarkCheck className="w-6 h-6" />
      ) : (
        <Bookmark className="w-6 h-6 text-navy-500" />
      )}
      <div className="text-sm font-semibold">
        {saved ? t("results.kept_in_memory") : busy ? t("results.saving") : t("results.keep_in_memory")}
      </div>
      <div className="text-[11px] text-ink-500 max-w-[240px]">
        {saved ? t("results.kept_hint_visible") : t("results.kept_hint_default")}
      </div>
    </button>
  );
}
