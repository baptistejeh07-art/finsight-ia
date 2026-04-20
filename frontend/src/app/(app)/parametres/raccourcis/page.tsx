"use client";

import { useEffect, useState } from "react";
import { Keyboard, RotateCcw, Shield } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { useUserPreferences } from "@/hooks/use-user-preferences";
import {
  USER_SHORTCUT_LABELS,
  DEV_SHORTCUT_LABELS,
  DEFAULT_USER_SHORTCUTS,
  DEFAULT_DEV_SHORTCUTS,
  eventToCombo,
  formatCombo,
  type UserShortcutAction,
  type DevShortcutAction,
} from "@/lib/shortcuts";

export default function RaccourcisPage() {
  const { prefs, update, loading } = useUserPreferences();
  const [isAdmin, setIsAdmin] = useState(false);
  const [recordingKey, setRecordingKey] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) return;
      const { data } = await supabase
        .from("user_preferences")
        .select("is_admin")
        .eq("user_id", user.id)
        .maybeSingle();
      setIsAdmin(!!data?.is_admin);
    });
  }, []);

  useEffect(() => {
    if (!recordingKey) return;
    function onKey(e: KeyboardEvent) {
      e.preventDefault();
      e.stopPropagation();
      if (e.key === "Escape") { setRecordingKey(null); return; }
      const combo = eventToCombo(e);
      if (!combo) return;
      if (recordingKey!.startsWith("user:")) {
        const action = recordingKey!.slice(5);
        update({ shortcuts: { ...prefs.shortcuts, [action]: combo } });
      } else if (recordingKey!.startsWith("dev:")) {
        const action = recordingKey!.slice(4);
        update({ dev_shortcuts: { ...prefs.dev_shortcuts, [action]: combo } });
      }
      setRecordingKey(null);
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [recordingKey, prefs.shortcuts, prefs.dev_shortcuts, update]);

  function resetUserDefaults() {
    update({ shortcuts: { ...DEFAULT_USER_SHORTCUTS } });
  }
  function resetDevDefaults() {
    update({ dev_shortcuts: { ...DEFAULT_DEV_SHORTCUTS } });
  }

  if (loading) return <div className="text-sm text-ink-500">Chargement…</div>;

  return (
    <div className="space-y-10 max-w-3xl">
      {/* User shortcuts */}
      <section>
        <div className="flex items-start justify-between mb-5">
          <div>
            <div className="flex items-center gap-2">
              <Keyboard className="w-5 h-5 text-ink-700" />
              <h2 className="text-lg font-semibold text-ink-900">Raccourcis clavier</h2>
            </div>
            <p className="text-sm text-ink-600 mt-1">
              Personnalisez les raccourcis pour naviguer plus vite. Cliquez sur un combo et
              tapez la combinaison souhaitée. Les raccourcis sont désactivés quand vous tapez
              dans un champ texte.
            </p>
          </div>
          <button
            type="button"
            onClick={resetUserDefaults}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-ink-300 text-xs text-ink-700 hover:bg-ink-50"
          >
            <RotateCcw className="w-3 h-3" /> Réinitialiser
          </button>
        </div>

        <div className="border border-ink-200 rounded-md divide-y divide-ink-100 bg-white">
          {(Object.keys(USER_SHORTCUT_LABELS) as UserShortcutAction[]).map((action) => {
            const meta = USER_SHORTCUT_LABELS[action];
            const combo = prefs.shortcuts[action] || "";
            const isRecording = recordingKey === `user:${action}`;
            return (
              <div key={action} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink-900">{meta.label}</div>
                  <div className="text-xs text-ink-500 mt-0.5">{meta.description}</div>
                </div>
                <button
                  type="button"
                  onClick={() => setRecordingKey(isRecording ? null : `user:${action}`)}
                  className={
                    "shrink-0 min-w-[140px] px-3 py-1.5 rounded-md border text-xs font-mono transition-colors " +
                    (isRecording
                      ? "border-navy-500 bg-navy-50 text-navy-700 animate-pulse"
                      : "border-ink-300 bg-ink-50 text-ink-800 hover:bg-ink-100")
                  }
                >
                  {isRecording ? "Tapez la combinaison…" : formatCombo(combo)}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* Dev shortcuts (admin only) */}
      {isAdmin && (
        <section className="border-t border-ink-200 pt-8">
          <div className="flex items-start justify-between mb-5">
            <div>
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-amber-600" />
                <h2 className="text-lg font-semibold text-ink-900">Raccourcis développeur</h2>
                <span className="text-2xs uppercase tracking-widest text-amber-600 font-bold bg-amber-50 px-2 py-0.5 rounded">
                  Admin
                </span>
              </div>
              <p className="text-sm text-ink-600 mt-1">
                Raccourcis avancés réservés aux administrateurs FinSight (vidage cache,
                reload sans cache, dashboard admin, overlay debug…). Inactifs pour les
                comptes non-admin même si configurés.
              </p>
            </div>
            <button
              type="button"
              onClick={resetDevDefaults}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-ink-300 text-xs text-ink-700 hover:bg-ink-50"
            >
              <RotateCcw className="w-3 h-3" /> Réinitialiser
            </button>
          </div>

          <div className="border border-amber-200 rounded-md divide-y divide-amber-100 bg-amber-50/30">
            {(Object.keys(DEV_SHORTCUT_LABELS) as DevShortcutAction[]).map((action) => {
              const meta = DEV_SHORTCUT_LABELS[action];
              const combo = prefs.dev_shortcuts[action] || "";
              const isRecording = recordingKey === `dev:${action}`;
              return (
                <div key={action} className="flex items-center justify-between gap-4 px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink-900">{meta.label}</div>
                    <div className="text-xs text-ink-500 mt-0.5">{meta.description}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setRecordingKey(isRecording ? null : `dev:${action}`)}
                    className={
                      "shrink-0 min-w-[140px] px-3 py-1.5 rounded-md border text-xs font-mono transition-colors " +
                      (isRecording
                        ? "border-amber-500 bg-amber-100 text-amber-900 animate-pulse"
                        : "border-amber-300 bg-white text-ink-800 hover:bg-amber-50")
                    }
                  >
                    {isRecording ? "Tapez la combinaison…" : formatCombo(combo)}
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="border-t border-ink-200 pt-6">
        <p className="text-xs text-ink-500">
          Les raccourcis sont sauvegardés automatiquement et synchronisés sur tous vos
          appareils. Pressez <kbd className="px-1.5 py-0.5 bg-ink-100 rounded text-2xs font-mono">Échap</kbd>{" "}
          pour annuler une capture en cours.
        </p>
      </section>
    </div>
  );
}
