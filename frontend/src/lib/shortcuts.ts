/**
 * Système de raccourcis clavier custom — utilisateur + dev (admin only).
 *
 * - Combo string format : "ctrl+shift+k" / "alt+/" / "meta+enter"
 * - Modifiers triés (ordre stable) : ctrl > meta > alt > shift
 * - Touche en lowercase ; caractères spéciaux gardés tels quels (",", "/", ".")
 */

export type UserShortcutAction =
  | "newAnalysis"
  | "openHistory"
  | "toggleFavoritesFilter"
  | "openSettings"
  | "toggleTheme"
  | "openHomepage";

export type DevShortcutAction =
  | "openAdminDashboard"
  | "clearLocalCache"
  | "reloadHardNoCache"
  | "toggleDevMode"
  | "openTrendsPage";

export type ShortcutAction = UserShortcutAction | DevShortcutAction;

export const USER_SHORTCUT_LABELS: Record<UserShortcutAction, { label: string; description: string }> = {
  newAnalysis: { label: "Nouvelle analyse", description: "Aller à la page d'accueil et focus la barre d'analyse" },
  openHistory: { label: "Ouvrir l'historique", description: "Faire défiler la sidebar vers la section historique" },
  toggleFavoritesFilter: { label: "Filtrer les favoris", description: "Basculer le filtre étoile dans l'historique" },
  openSettings: { label: "Ouvrir les paramètres", description: "Aller à /parametres" },
  toggleTheme: { label: "Basculer le thème", description: "Alterner clair / sombre" },
  openHomepage: { label: "Aller au dashboard", description: "Aller à /app" },
};

export const DEV_SHORTCUT_LABELS: Record<DevShortcutAction, { label: string; description: string }> = {
  openAdminDashboard: { label: "Dashboard admin", description: "Ouvrir /admin" },
  clearLocalCache: { label: "Vider le cache local", description: "localStorage + sessionStorage clear (sauf auth)" },
  reloadHardNoCache: { label: "Reload sans cache", description: "location.reload() forcé" },
  toggleDevMode: { label: "Toggle dev overlay", description: "Affiche/masque un overlay debug (job id, build version)" },
  openTrendsPage: { label: "Page Trends", description: "Ouvrir /admin/trends (dataset analyses)" },
};

export const DEFAULT_USER_SHORTCUTS: Record<UserShortcutAction, string> = {
  newAnalysis: "ctrl+k",
  openHistory: "ctrl+h",
  toggleFavoritesFilter: "ctrl+b",
  openSettings: "ctrl+,",
  toggleTheme: "ctrl+shift+t",
  openHomepage: "ctrl+shift+h",
};

export const DEFAULT_DEV_SHORTCUTS: Record<DevShortcutAction, string> = {
  openAdminDashboard: "ctrl+shift+d",
  clearLocalCache: "ctrl+shift+l",
  reloadHardNoCache: "ctrl+shift+r",
  toggleDevMode: "ctrl+shift+m",
  openTrendsPage: "ctrl+shift+y",
};

/** Convertit un KeyboardEvent en combo string normalisé. */
export function eventToCombo(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey) parts.push("ctrl");
  if (e.metaKey) parts.push("meta");
  if (e.altKey) parts.push("alt");
  if (e.shiftKey) parts.push("shift");
  let key = e.key;
  if (!key) return "";
  if (key === " ") key = "space";
  if (key.length === 1) key = key.toLowerCase();
  // Ignore modifier-only events
  if (["Control", "Shift", "Alt", "Meta"].includes(key)) return "";
  parts.push(key);
  return parts.join("+");
}

/** Vérifie si un event correspond à un combo. */
export function matchesCombo(e: KeyboardEvent, combo: string): boolean {
  if (!combo) return false;
  return eventToCombo(e) === combo.toLowerCase();
}

/** Format un combo pour affichage UI (Ctrl+Shift+K). */
export function formatCombo(combo: string): string {
  if (!combo) return "—";
  return combo
    .split("+")
    .map((p) => {
      if (p === "ctrl") return "Ctrl";
      if (p === "meta") return "⌘";
      if (p === "alt") return "Alt";
      if (p === "shift") return "Shift";
      if (p.length === 1) return p.toUpperCase();
      if (p === " " || p === "space") return "Espace";
      return p.charAt(0).toUpperCase() + p.slice(1);
    })
    .join(" + ");
}
