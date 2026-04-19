"use client";

import { useEffect } from "react";
import { useUserPreferences } from "@/hooks/use-user-preferences";

/**
 * Applique les préférences utilisateur (thème + police) globalement sur <html>.
 * À inclure dans le layout (app) au-dessus des children.
 */
export function UserPreferencesProvider({ children }: { children: React.ReactNode }) {
  const { prefs } = useUserPreferences();

  useEffect(() => {
    const root = document.documentElement;

    // --- Thème ---
    const resolveTheme = (): "light" | "dark" => {
      if (prefs.theme === "light") return "light";
      if (prefs.theme === "dark") return "dark";
      // auto = pref OS
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    };
    const themeApplied = resolveTheme();
    root.classList.toggle("dark", themeApplied === "dark");
    root.dataset.theme = themeApplied;

    // Écoute le changement OS si auto
    let mql: MediaQueryList | null = null;
    let onChange: ((e: MediaQueryListEvent) => void) | null = null;
    if (prefs.theme === "auto") {
      mql = window.matchMedia("(prefers-color-scheme: dark)");
      onChange = (e) => {
        root.classList.toggle("dark", e.matches);
        root.dataset.theme = e.matches ? "dark" : "light";
      };
      mql.addEventListener("change", onChange);
    }

    // --- Police ---
    root.dataset.font = prefs.font;

    // --- Animation arrière-plan ---
    root.dataset.bgAnim = prefs.background_animation;

    return () => {
      if (mql && onChange) mql.removeEventListener("change", onChange);
    };
  }, [prefs.theme, prefs.font, prefs.background_animation]);

  return <>{children}</>;
}
