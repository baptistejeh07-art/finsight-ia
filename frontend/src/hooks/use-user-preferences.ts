"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";

export type Theme = "light" | "auto" | "dark";
export type BackgroundAnimation = "on" | "auto" | "off";
export type Font = "default" | "sans" | "system" | "dyslexia";
export type ToolsMode = "on_demand" | "preloaded";
export type LogoSize = "sm" | "md" | "lg" | "xl" | "2xl" | "3xl";

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
            notifications: { ...DEFAULT_PREFERENCES.notifications, ...(data.notifications || {}) },
            privacy: { ...DEFAULT_PREFERENCES.privacy, ...(data.privacy || {}) },
            capabilities: { ...DEFAULT_PREFERENCES.capabilities, ...(data.capabilities || {}) },
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
              notifications: next.notifications,
              privacy: next.privacy,
              capabilities: next.capabilities,
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
