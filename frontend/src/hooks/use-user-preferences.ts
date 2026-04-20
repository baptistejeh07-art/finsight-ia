"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { DEFAULT_USER_SHORTCUTS, DEFAULT_DEV_SHORTCUTS } from "@/lib/shortcuts";

export type Theme = "light" | "auto" | "dark";
export type BackgroundAnimation = "on" | "auto" | "off";
export type Font = "default" | "sans" | "system" | "dyslexia";
export type ToolsMode = "on_demand" | "preloaded";
export type LogoSize = "sm" | "md" | "lg" | "xl" | "2xl" | "3xl";
export type Currency = "EUR" | "USD" | "GBP" | "CHF" | "JPY" | "CAD";
export type Language = "fr" | "en" | "es" | "de" | "it" | "pt";

export const SUPPORTED_CURRENCIES: { code: Currency; label: string; symbol: string }[] = [
  { code: "EUR", label: "Euro", symbol: "€" },
  { code: "USD", label: "Dollar US", symbol: "$" },
  { code: "GBP", label: "Livre sterling", symbol: "£" },
  { code: "CHF", label: "Franc suisse", symbol: "CHF" },
  { code: "JPY", label: "Yen", symbol: "¥" },
  { code: "CAD", label: "Dollar canadien", symbol: "C$" },
];

export const SUPPORTED_LANGUAGES: { code: Language; label: string; native: string }[] = [
  { code: "fr", label: "Français", native: "Français" },
  { code: "en", label: "Anglais", native: "English" },
  { code: "es", label: "Espagnol", native: "Español" },
  { code: "de", label: "Allemand", native: "Deutsch" },
  { code: "it", label: "Italien", native: "Italiano" },
  { code: "pt", label: "Portugais", native: "Português" },
];

export interface UserPreferences {
  user_id?: string;
  // Profil
  full_name: string;
  nickname: string;
  profession: string;
  llm_preferences: string;
  // Apparence
  theme: Theme;
  background_animation: BackgroundAnimation;
  font: Font;
  logo_size: LogoSize;
  // Internationalisation
  currency: Currency;
  language: Language;
  // Mode explicatif : quand actif, les commentaires LLM expliquent simplement chaque concept
  explanatory_mode: boolean;
  // Flag onboarding tour (premier passage)
  onboarded: boolean;
  // Notifications
  notifications: {
    completion: boolean;
    email_reports: boolean;
    push_messages: boolean;
  };
  // Privacy
  privacy: {
    location_metadata: boolean;
    improve_models: boolean;
    memory_enabled: boolean;
  };
  // Capacités
  capabilities: {
    memory_search: boolean;
    memory_generate: boolean;
    tools_mode: ToolsMode;
  };
  // Raccourcis clavier custom (action → combo)
  shortcuts: Record<string, string>;
  dev_shortcuts: Record<string, string>;
}

export const DEFAULT_PREFERENCES: UserPreferences = {
  full_name: "",
  nickname: "",
  profession: "",
  llm_preferences: "",
  theme: "auto",
  background_animation: "auto",
  font: "default",
  logo_size: "lg",
  currency: "EUR",
  language: "fr",
  explanatory_mode: false,
  onboarded: false,
  notifications: {
    completion: false,
    email_reports: false,
    push_messages: false,
  },
  privacy: {
    location_metadata: true,
    improve_models: true,
    memory_enabled: true,
  },
  capabilities: {
    memory_search: true,
    memory_generate: true,
    tools_mode: "on_demand",
  },
  shortcuts: { ...DEFAULT_USER_SHORTCUTS },
  dev_shortcuts: { ...DEFAULT_DEV_SHORTCUTS },
};

/**
 * Hook de préférences utilisateur avec persistance Supabase.
 *
 * - Charge au mount depuis la table `user_preferences`
 * - `update(patch)` fusionne localement et upsert en base (debounce 500ms)
 * - Si pas connecté ou erreur : fallback localStorage
 */
export function useUserPreferences() {
  const [prefs, setPrefs] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const supabase = createClient();

  // === Charge au mount ===
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (cancelled) return;
        if (!user) {
          // Fallback : lecture localStorage si non connecté
          try {
            const raw = localStorage.getItem("finsight-user-preferences");
            if (raw) setPrefs({ ...DEFAULT_PREFERENCES, ...JSON.parse(raw) });
          } catch {}
          setLoading(false);
          return;
        }
        setUserId(user.id);

        const { data, error } = await supabase
          .from("user_preferences")
          .select("*")
          .eq("user_id", user.id)
          .maybeSingle();

        if (cancelled) return;

        if (error) {
          console.warn("[useUserPreferences] select error", error);
        }

        if (data) {
          setPrefs({
            ...DEFAULT_PREFERENCES,
            full_name: data.full_name ?? "",
            nickname: data.nickname ?? "",
            profession: data.profession ?? "",
            llm_preferences: data.llm_preferences ?? "",
            theme: data.theme ?? "auto",
            background_animation: data.background_animation ?? "auto",
            font: data.font ?? "default",
            logo_size: data.logo_size ?? "lg",
            currency: data.currency ?? "EUR",
            language: data.language ?? "fr",
            explanatory_mode: !!data.explanatory_mode,
            onboarded: !!data.onboarded,
            notifications: { ...DEFAULT_PREFERENCES.notifications, ...(data.notifications || {}) },
            privacy: { ...DEFAULT_PREFERENCES.privacy, ...(data.privacy || {}) },
            capabilities: { ...DEFAULT_PREFERENCES.capabilities, ...(data.capabilities || {}) },
            shortcuts: { ...DEFAULT_PREFERENCES.shortcuts, ...(data.shortcuts || {}) },
            dev_shortcuts: { ...DEFAULT_PREFERENCES.dev_shortcuts, ...(data.dev_shortcuts || {}) },
          });
        }
        setLoading(false);
      } catch (e) {
        console.warn("[useUserPreferences] load failed", e);
        setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [supabase]);

  // === Update (merge + save debounced) ===
  const update = useCallback((patch: Partial<UserPreferences>) => {
    setPrefs((prev) => {
      const next = { ...prev, ...patch };
      // Fusion profonde pour objets imbriqués
      if (patch.notifications) {
        next.notifications = { ...prev.notifications, ...patch.notifications };
      }
      if (patch.privacy) {
        next.privacy = { ...prev.privacy, ...patch.privacy };
      }
      if (patch.capabilities) {
        next.capabilities = { ...prev.capabilities, ...patch.capabilities };
      }
      if (patch.shortcuts) {
        next.shortcuts = { ...prev.shortcuts, ...patch.shortcuts };
      }
      if (patch.dev_shortcuts) {
        next.dev_shortcuts = { ...prev.dev_shortcuts, ...patch.dev_shortcuts };
      }

      // Debounce persistance
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(async () => {
        // Fallback localStorage systématique
        try {
          localStorage.setItem("finsight-user-preferences", JSON.stringify(next));
        } catch {}

        if (!userId) return;
        try {
          const { error } = await supabase
            .from("user_preferences")
            .upsert({
              user_id: userId,
              full_name: next.full_name,
              nickname: next.nickname,
              profession: next.profession,
              llm_preferences: next.llm_preferences,
              theme: next.theme,
              background_animation: next.background_animation,
              font: next.font,
              logo_size: next.logo_size,
              currency: next.currency,
              language: next.language,
              explanatory_mode: next.explanatory_mode,
              onboarded: next.onboarded,
              notifications: next.notifications,
              privacy: next.privacy,
              capabilities: next.capabilities,
              shortcuts: next.shortcuts,
              dev_shortcuts: next.dev_shortcuts,
            }, { onConflict: "user_id" });
          if (error) {
            console.warn("[useUserPreferences] upsert error", error);
          }
        } catch (e) {
          console.warn("[useUserPreferences] save failed", e);
        }
      }, 500);

      return next;
    });
  }, [userId, supabase]);

  return { prefs, update, loading };
}
