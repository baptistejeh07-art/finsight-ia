"use client";

import { useCallback, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export type HistoryKind = "societe" | "secteur" | "indice" | "comparatif" | "portrait";

export interface HistoryItem {
  id: string;
  job_id: string;
  kind: HistoryKind;
  label: string;
  ticker: string | null;
  created_at: string;
}

export interface HistoryItemFull extends HistoryItem {
  payload: Record<string, unknown>;
}

/**
 * Liste des analyses sauvegardées pour l'utilisateur courant.
 * - Refresh automatique quand un event "finsight:history-changed" est dispatché.
 * - Retourne un tableau vide si non connecté.
 */
export function useAnalysesHistory() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        setItems([]);
        setLoading(false);
        return;
      }
      const { data, error } = await supabase
        .from("analyses_history")
        .select("id, job_id, kind, label, ticker, created_at")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false })
        .limit(50);
      if (error) {
        console.warn("[useAnalysesHistory] select error", error);
        setItems([]);
      } else {
        setItems(data || []);
      }
    } catch (e) {
      console.warn("[useAnalysesHistory] load failed", e);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const onChange = () => load();
    window.addEventListener("finsight:history-changed", onChange);
    return () => window.removeEventListener("finsight:history-changed", onChange);
  }, [load]);

  return { items, loading, reload: load };
}

/**
 * Sauvegarde une analyse dans l'historique (insert or noop si déjà présent).
 * Renvoie { saved: true } si ok, { saved: false, error } sinon.
 */
export async function saveAnalysisToHistory(payload: {
  job_id: string;
  kind: HistoryKind;
  label: string;
  ticker?: string | null;
  // Snapshot complet du result (sessionStorage.analysis_{jobId})
  data: unknown;
}): Promise<{ saved: boolean; error?: string }> {
  const supabase = createClient();
  try {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      return { saved: false, error: "Non connecté" };
    }
    const { error } = await supabase
      .from("analyses_history")
      .upsert(
        {
          user_id: user.id,
          job_id: payload.job_id,
          kind: payload.kind,
          label: payload.label,
          ticker: payload.ticker ?? null,
          payload: payload.data,
        },
        { onConflict: "user_id,job_id" }
      );
    if (error) {
      return { saved: false, error: error.message };
    }
    try {
      window.dispatchEvent(new CustomEvent("finsight:history-changed"));
    } catch {}
    return { saved: true };
  } catch (e) {
    return { saved: false, error: (e as Error).message };
  }
}

/**
 * Supprime une entrée de l'historique.
 */
export async function deleteFromHistory(id: string): Promise<boolean> {
  const supabase = createClient();
  try {
    const { error } = await supabase.from("analyses_history").delete().eq("id", id);
    if (error) return false;
    try {
      window.dispatchEvent(new CustomEvent("finsight:history-changed"));
    } catch {}
    return true;
  } catch {
    return false;
  }
}

/**
 * Récupère une analyse complète par son id (pour recharger sessionStorage).
 */
export async function fetchHistoryItem(id: string): Promise<HistoryItemFull | null> {
  const supabase = createClient();
  try {
    const { data, error } = await supabase
      .from("analyses_history")
      .select("*")
      .eq("id", id)
      .maybeSingle();
    if (error || !data) return null;
    return data as HistoryItemFull;
  } catch {
    return null;
  }
}
