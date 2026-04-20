"use client";

import { useCallback, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export type TriggerType =
  | "price_target"
  | "earnings_date"
  | "dividend_exdate"
  | "news"
  | "custom_date"
  | "quarterly_results";

export type Channel = "email" | "push";

export interface Alert {
  id: string;
  user_id: string;
  history_id: string | null;
  ticker: string | null;
  trigger_type: TriggerType;
  trigger_value: Record<string, unknown>;
  channels: Channel[];
  label: string | null;
  enabled: boolean;
  last_checked: string | null;
  fired_at: string | null;
  fired_payload: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

async function getToken(): Promise<string | null> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || null;
}

export async function createAlert(payload: {
  history_id?: string;
  ticker?: string;
  trigger_type: TriggerType;
  trigger_value: Record<string, unknown>;
  channels: Channel[];
  label?: string;
}): Promise<Alert | null> {
  const token = await getToken();
  if (!token) return null;
  const r = await fetch(`${API}/alerts/create`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) return null;
  const j = await r.json();
  return j.alert || null;
}

export async function patchAlert(id: string, fields: Partial<Pick<Alert, "enabled" | "label" | "channels" | "trigger_value">>): Promise<boolean> {
  const token = await getToken();
  if (!token) return false;
  const r = await fetch(`${API}/alerts/${id}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  return r.ok;
}

export async function deleteAlert(id: string): Promise<boolean> {
  const token = await getToken();
  if (!token) return false;
  const r = await fetch(`${API}/alerts/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  return r.ok;
}

export function useAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { setAlerts([]); return; }
      const r = await fetch(`${API}/alerts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) { setAlerts([]); return; }
      const j = await r.json();
      setAlerts(j.alerts || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const onChange = () => load();
    window.addEventListener("finsight:alerts-changed", onChange);
    return () => window.removeEventListener("finsight:alerts-changed", onChange);
  }, [load]);

  return { alerts, loading, reload: load };
}
