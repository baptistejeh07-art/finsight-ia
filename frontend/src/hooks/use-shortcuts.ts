"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useUserPreferences } from "@/hooks/use-user-preferences";
import {
  matchesCombo,
  type ShortcutAction,
  type UserShortcutAction,
  type DevShortcutAction,
} from "@/lib/shortcuts";

/**
 * Hook global qui écoute les keydown et déclenche les actions configurées
 * par l'utilisateur. À monter une seule fois (dans (app)/layout.tsx).
 */
export function useShortcutsRuntime(opts: { isAdmin: boolean }) {
  const { prefs } = useUserPreferences();
  const router = useRouter();

  useEffect(() => {
    function isTypingTarget(e: KeyboardEvent): boolean {
      const t = e.target as HTMLElement | null;
      if (!t) return false;
      const tag = (t.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return true;
      if (t.isContentEditable) return true;
      return false;
    }

    function runUserAction(action: UserShortcutAction) {
      switch (action) {
        case "newAnalysis":
          router.push("/app");
          setTimeout(() => {
            const el = document.querySelector<HTMLInputElement>("input[type='text'], input[type='search']");
            el?.focus();
          }, 250);
          break;
        case "openHistory": {
          const heading = Array.from(document.querySelectorAll("aside *"))
            .find((n) => n.textContent?.toLowerCase().includes("historique"));
          (heading as HTMLElement | undefined)?.scrollIntoView({ behavior: "smooth", block: "start" });
          break;
        }
        case "toggleFavoritesFilter": {
          const star = document.querySelector<HTMLButtonElement>("aside button[title*='favoris']");
          star?.click();
          break;
        }
        case "openSettings":
          router.push("/parametres/general");
          break;
        case "toggleTheme": {
          const html = document.documentElement;
          const next = html.classList.contains("dark") ? "light" : "dark";
          if (next === "dark") html.classList.add("dark");
          else html.classList.remove("dark");
          try { localStorage.setItem("finsight-theme", next); } catch {}
          toast(`Thème : ${next === "dark" ? "sombre" : "clair"}`);
          break;
        }
        case "openHomepage":
          router.push("/app");
          break;
      }
    }

    function runDevAction(action: DevShortcutAction) {
      if (!opts.isAdmin) return;
      switch (action) {
        case "openAdminDashboard":
          router.push("/admin");
          break;
        case "openTrendsPage":
          router.push("/admin/trends");
          break;
        case "clearLocalCache": {
          const authKeys = Object.keys(localStorage).filter((k) => k.startsWith("sb-"));
          const saved: Record<string, string> = {};
          for (const k of authKeys) saved[k] = localStorage.getItem(k) || "";
          localStorage.clear();
          sessionStorage.clear();
          for (const [k, v] of Object.entries(saved)) localStorage.setItem(k, v);
          toast.success("Cache local vidé (auth conservée)");
          break;
        }
        case "reloadHardNoCache":
          location.reload();
          break;
        case "toggleDevMode": {
          const id = "__finsight_dev_overlay__";
          const existing = document.getElementById(id);
          if (existing) { existing.remove(); toast("Dev overlay OFF"); return; }
          const div = document.createElement("div");
          div.id = id;
          div.style.cssText = "position:fixed;bottom:8px;left:8px;z-index:99999;background:rgba(0,0,0,0.85);color:#0f0;font:11px/1.4 monospace;padding:8px 10px;border-radius:4px;pointer-events:none;max-width:320px;";
          div.textContent = `path: ${location.pathname}\nbuild: ${process.env.NEXT_PUBLIC_BUILD_ID || "dev"}\nUA: ${navigator.userAgent.slice(0, 80)}`;
          document.body.appendChild(div);
          toast("Dev overlay ON");
          break;
        }
      }
    }

    function onKeyDown(e: KeyboardEvent) {
      if (isTypingTarget(e)) return;
      const userMap = prefs.shortcuts || {};
      const devMap = prefs.dev_shortcuts || {};
      // User shortcuts
      for (const [action, combo] of Object.entries(userMap) as [UserShortcutAction, string][]) {
        if (matchesCombo(e, combo)) {
          e.preventDefault();
          runUserAction(action);
          return;
        }
      }
      // Dev shortcuts (admin only)
      if (opts.isAdmin) {
        for (const [action, combo] of Object.entries(devMap) as [DevShortcutAction, string][]) {
          if (matchesCombo(e, combo)) {
            e.preventDefault();
            runDevAction(action);
            return;
          }
        }
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [prefs.shortcuts, prefs.dev_shortcuts, opts.isAdmin, router]);
}
