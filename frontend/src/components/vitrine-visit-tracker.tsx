"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Tracker anonyme des visites du site vitrine. À monter UNE SEULE fois
 * dans le layout racine : à chaque changement de route, envoie un beacon
 * vers POST /analytics/vitrine-visit (backend Railway).
 *
 * Session ID anonyme persisté en localStorage — un seul ID par navigateur,
 * permet de dédupliquer les visites "même visiteur, 5 pages vues".
 */
export function VitrineVisitTracker() {
  const pathname = usePathname();
  const lastTracked = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname) return;
    // Évite de tracker deux fois la même route (React strict mode)
    if (lastTracked.current === pathname) return;
    lastTracked.current = pathname;

    // Ne pas tracker les pages internes app (user connecté, déjà compté
    // dans analysis_log et user_preferences).
    if (
      pathname.startsWith("/app") ||
      pathname.startsWith("/resultats/") ||
      pathname.startsWith("/analyse") ||
      pathname.startsWith("/comparatif") ||
      pathname.startsWith("/dashboard") ||
      pathname.startsWith("/parametres") ||
      pathname.startsWith("/admin") ||
      pathname.startsWith("/pme") ||
      pathname.startsWith("/api/") ||
      pathname.startsWith("/auth/")
    ) {
      return;
    }

    let sid = "";
    try {
      sid = localStorage.getItem("finsight-anon-sid") || "";
      if (!sid) {
        sid = `a_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
        localStorage.setItem("finsight-anon-sid", sid);
      }
    } catch {
      /* localStorage blocked → pas de dédup mais on compte quand même */
    }

    const body = JSON.stringify({
      path: pathname,
      referrer: typeof document !== "undefined" ? document.referrer || null : null,
      anon_session_id: sid || null,
    });

    // fetch avec keepalive pour ne pas bloquer la nav. Fire-and-forget.
    try {
      fetch(`${API}/analytics/vitrine-visit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => {});
    } catch {
      /* no-op */
    }
  }, [pathname]);

  return null;
}
