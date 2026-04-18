"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { Settings2, Save, X } from "lucide-react";

interface EditModeCtx {
  enabled: boolean;
  toggle: () => void;
}

const EditModeContext = createContext<EditModeCtx>({
  enabled: false,
  toggle: () => {},
});

export function useEditMode() {
  return useContext(EditModeContext);
}

/**
 * Provider Mode Édition (Alt+E pour toggle).
 *
 * V1 (actuelle) : toggle visuel + bordures pointillées sur les blocs marqués
 * `data-editable="true"`. Les blocs ne sont pas encore drag&droppables.
 *
 * V2 (à venir) : drag&drop via react-grid-layout, resize handles, save layout
 * dans Supabase Storage `layouts/dashboard.json`. Le layout sauvé devient le
 * standard pour tous les utilisateurs en mode dev. En multi-user (V3), chaque
 * user aura son propre layout.
 */
export function EditModeProvider({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Détection robuste : on regarde e.code (KeyE) qui est indépendant
      // de la disposition clavier (AZERTY/QWERTY) et de la langue.
      const isE = e.code === "KeyE" || e.key === "e" || e.key === "E";
      if (!isE) {
        // Échap pour quitter
        if (e.key === "Escape" && enabled) {
          setEnabled(false);
        }
        return;
      }
      // Combinaisons acceptées (par ordre de robustesse) :
      //   Ctrl+Alt+E : universel, jamais conflit (recommandé)
      //   Cmd+Alt+E : équivalent Mac
      //   Alt+E : court mais peut entrer en conflit avec le menu Édition Chrome Win
      const ctrlOrMeta = e.ctrlKey || e.metaKey;
      if ((ctrlOrMeta && e.altKey) || e.altKey) {
        e.preventDefault();
        e.stopPropagation();
        setEnabled((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [enabled]);

  // CSS injecté pour styler les blocs en mode édition
  useEffect(() => {
    if (!enabled) {
      document.body.classList.remove("edit-mode");
      return;
    }
    document.body.classList.add("edit-mode");
    return () => document.body.classList.remove("edit-mode");
  }, [enabled]);

  return (
    <EditModeContext.Provider value={{ enabled, toggle: () => setEnabled((v) => !v) }}>
      {children}
      {enabled && <EditBanner onClose={() => setEnabled(false)} />}
    </EditModeContext.Provider>
  );
}

function EditBanner({ onClose }: { onClose: () => void }) {
  return (
    <>
      <div className="fixed top-0 left-0 right-0 z-50 bg-amber-500 text-amber-950 shadow-lg">
        <div className="max-w-7xl mx-auto px-6 py-2.5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Settings2 className="w-4 h-4" />
            <span>Mode édition</span>
            <span className="text-xs opacity-70 hidden md:inline">
              · Ctrl+Alt+E pour toggle · V1 : visualisation · drag&drop en V2
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled
              className="text-xs px-3 py-1 rounded bg-white/30 text-amber-950/50 cursor-not-allowed"
              title="Disponible en V2"
            >
              <Save className="w-3 h-3 inline mr-1" />
              Sauvegarder layout
            </button>
            <button
              onClick={onClose}
              className="text-xs px-2 py-1 rounded hover:bg-white/30"
              aria-label="Quitter mode édition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
      {/* Style global injecté */}
      <style jsx global>{`
        body.edit-mode {
          padding-top: 42px; /* hauteur banner */
        }
        body.edit-mode [data-editable="true"] {
          outline: 2px dashed rgb(245 158 11 / 0.6);
          outline-offset: 4px;
          position: relative;
          transition: outline-color 0.15s;
        }
        body.edit-mode [data-editable="true"]:hover {
          outline-color: rgb(245 158 11 / 1);
        }
        body.edit-mode [data-editable="true"]::before {
          content: attr(data-block-name);
          position: absolute;
          top: -22px;
          left: 0;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 1px;
          color: rgb(180 83 9);
          font-weight: 600;
          pointer-events: none;
        }
      `}</style>
    </>
  );
}
