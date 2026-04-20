"use client";

import { useState } from "react";
import { Bell } from "lucide-react";
import { AlertModal } from "@/components/alert-modal";
import type { HistoryKind } from "@/hooks/use-analyses-history";

interface Props {
  jobId: string;
  kind: HistoryKind;
  ticker?: string;
  label: string;
  defaultTargetPrice?: number;
  historyId?: string | null;
}

export function AlertCard({ ticker, defaultTargetPrice, historyId }: Props) {
  const [open, setOpen] = useState(false);

  // Custom date trigger fonctionne même sans ticker, donc on garde le bouton actif
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full h-full flex items-center justify-center gap-2 rounded-md border border-ink-200 bg-white hover:bg-ink-50 px-4 py-3 text-sm font-semibold text-ink-800 transition-colors"
      >
        <Bell className="w-4 h-4" />
        Créer un rappel
      </button>
      <AlertModal
        open={open}
        onClose={() => setOpen(false)}
        historyId={historyId}
        ticker={ticker}
        defaultTargetPrice={defaultTargetPrice}
      />
    </>
  );
}
