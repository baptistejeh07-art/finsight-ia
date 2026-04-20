"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { useShortcutsRuntime } from "@/hooks/use-shortcuts";

/**
 * Composant transparent qui monte le hook global d'écoute clavier.
 * Lit is_admin depuis user_preferences pour activer/désactiver les dev shortcuts.
 */
export function ShortcutsRuntime() {
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (!user || cancelled) return;
      const { data } = await supabase
        .from("user_preferences")
        .select("is_admin")
        .eq("user_id", user.id)
        .maybeSingle();
      if (!cancelled) setIsAdmin(!!data?.is_admin);
    }
    load();
    return () => { cancelled = true; };
  }, []);

  useShortcutsRuntime({ isAdmin });
  return null;
}
