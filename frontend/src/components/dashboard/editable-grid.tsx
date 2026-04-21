"use client";

import { useEffect, useState, type ReactNode } from "react";
// react-grid-layout v1.4 (API stable)
// eslint-disable-next-line @typescript-eslint/no-require-imports
const RGL = require("react-grid-layout");
const ResponsiveReactGridLayout = RGL.WidthProvider(RGL.Responsive);

import { useEditMode } from "@/components/edit-mode-provider";
import { useI18n } from "@/i18n/provider";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

const DEFAULT_STORAGE_KEY = "finsight-dashboard-grid-layout-v2";

type LayoutItem = { i: string; x: number; y: number; w: number; h: number; minW?: number; minH?: number };
type Layouts = { [breakpoint: string]: LayoutItem[] };

export interface GridBlock {
  id: string;
  label: string;
  render: () => ReactNode;
  /** Layout default lg (12 cols). Si absent, auto-placed à la fin. */
  default?: { x: number; y: number; w: number; h: number; minW?: number; minH?: number };
}

/**
 * Mode édition V2 — vraie grid drag & drop & resize via react-grid-layout v1.4.
 *
 * Comportement :
 *  - Hors mode édition : render simple en flux vertical (zéro régression).
 *  - En mode édition : grid responsive avec drag & resize visuels.
 *  - Layout sauvé dans localStorage à chaque changement.
 *  - Bouton "Réinitialiser" pour revenir aux defaults.
 *
 * `storageKey` permet d'avoir des layouts indépendants par type d'analyse
 * (société / secteur / indice / comparatif).
 */
export function EditableGrid({
  blocks,
  storageKey,
}: {
  blocks: GridBlock[];
  storageKey?: string;
}) {
  const STORAGE_KEY = storageKey || DEFAULT_STORAGE_KEY;
  const HIDDEN_KEY = STORAGE_KEY + ":hidden";
  const { enabled } = useEditMode();
  const { t } = useI18n();
  const [layouts, setLayouts] = useState<Layouts>({});
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);

  function buildFallback(): LayoutItem[] {
    return blocks.map((b, i) => ({
      i: b.id,
      x: b.default?.x ?? (i * 4) % 12,
      y: b.default?.y ?? Math.floor(i / 3) * 4,
      w: b.default?.w ?? 4,
      h: b.default?.h ?? 4,
      minW: b.default?.minW ?? 2,
      minH: b.default?.minH ?? 2,
    }));
  }

  useEffect(() => {
    let saved: Layouts | null = null;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) saved = JSON.parse(raw);
      const hraw = localStorage.getItem(HIDDEN_KEY);
      if (hraw) setHidden(new Set(JSON.parse(hraw)));
    } catch {
      /* no-op */
    }
    const fallback = buildFallback();
    if (saved && saved.lg) {
      // Merge : si de nouveaux blocs existent mais ne sont pas dans saved.lg,
      // on les ajoute avec leur position default (sinon ils resteraient invisibles
      // tant que l'utilisateur n'a pas reset manuellement le layout — fix UX
      // majeur pour les mises à jour qui ajoutent des blocs).
      const savedIds = new Set(saved.lg.map((l) => l.i));
      const missing = fallback.filter((f) => !savedIds.has(f.i));
      if (missing.length > 0) {
        // Place les nouveaux blocs tout en bas
        const maxY = Math.max(0, ...saved.lg.map((l) => l.y + l.h));
        missing.forEach((m, idx) => {
          m.y = maxY + idx * (m.h || 4);
          m.x = m.x ?? 0;
        });
        saved = { ...saved, lg: [...saved.lg, ...missing] };
      }
      setLayouts(saved);
    } else {
      setLayouts({ lg: fallback });
    }
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocks.map((b) => b.id).join("|")]);

  function onLayoutChange(_curr: LayoutItem[], all: Layouts) {
    if (!enabled) return;
    setLayouts(all);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
    } catch {
      /* no-op */
    }
    // Force Recharts (et autres ResponsiveContainer) à recalculer
    // leurs dimensions quand un bloc est resized.
    requestAnimationFrame(() => {
      try {
        window.dispatchEvent(new Event("resize"));
      } catch {}
    });
  }

  function reset() {
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(HIDDEN_KEY);
    } catch {}
    setHidden(new Set());
    setLayouts({ lg: buildFallback() });
  }

  function persistHidden(h: Set<string>) {
    try {
      localStorage.setItem(HIDDEN_KEY, JSON.stringify([...h]));
    } catch {}
  }

  function hideBlock(id: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      next.add(id);
      persistHidden(next);
      return next;
    });
  }

  function showBlock(id: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      next.delete(id);
      persistHidden(next);
      return next;
    });
  }

  const visibleBlocks = blocks.filter((b) => !hidden.has(b.id));
  const hiddenBlocks = blocks.filter((b) => hidden.has(b.id));

  if (!hydrated) {
    return <div className="text-xs text-ink-500">{t("grid.loading_layout")}</div>;
  }

  return (
    <>
      {enabled && (
        <div className="mb-3 flex items-center justify-between text-xs">
          <span className="text-amber-700 font-medium">
            {t("grid.edit_hint")} · Clique × pour masquer un bloc.
          </span>
          <button
            onClick={reset}
            className="text-xs px-3 py-1 rounded border border-amber-400 text-amber-700 hover:bg-amber-50 transition-colors"
          >
            {t("grid.reset_layout")}
          </button>
        </div>
      )}

      {enabled && hiddenBlocks.length > 0 && (
        <div className="mb-3 bg-ink-50 border border-ink-200 rounded-md p-3">
          <div className="text-2xs uppercase tracking-widest text-ink-500 font-semibold mb-2">
            Blocs masqués ({hiddenBlocks.length}) — cliquez pour restaurer
          </div>
          <div className="flex flex-wrap gap-1.5">
            {hiddenBlocks.map((b) => (
              <button
                key={b.id}
                onClick={() => showBlock(b.id)}
                className="text-xs px-2 py-1 rounded border border-ink-300 bg-white hover:bg-ink-100 text-ink-700 flex items-center gap-1.5"
              >
                <span>+</span> {b.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <ResponsiveReactGridLayout
        className="editable-grid"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 8, sm: 4, xs: 2, xxs: 1 }}
        rowHeight={50}
        margin={[12, 12]}
        containerPadding={[0, 0]}
        isDraggable={enabled}
        isResizable={enabled}
        onLayoutChange={onLayoutChange}
        compactType="vertical"
        useCSSTransforms={true}
        draggableHandle=".grid-drag-handle"
      >
        {visibleBlocks.map((b) => (
          <div
            key={b.id}
            className={
              enabled
                ? "h-full bg-white border border-amber-400/40 rounded-md overflow-hidden shadow-sm flex flex-col"
                : "h-full overflow-hidden flex flex-col"
            }
          >
            {enabled && (
              <div className="grid-drag-handle bg-amber-50 border-b border-amber-200 px-3 py-1.5 text-2xs uppercase tracking-widest text-amber-700 font-semibold cursor-move select-none flex items-center justify-between flex-none gap-2">
                <span className="truncate">⋮⋮ {b.label}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    hideBlock(b.id);
                  }}
                  onMouseDown={(e) => e.stopPropagation()}
                  className="shrink-0 text-amber-700 hover:text-signal-sell hover:bg-red-50 rounded w-5 h-5 flex items-center justify-center text-sm leading-none"
                  title="Masquer ce bloc"
                >
                  ×
                </button>
              </div>
            )}
            <div className={enabled ? "p-3 flex-1 min-h-0 overflow-auto" : "flex-1 min-h-0"}>{b.render()}</div>
          </div>
        ))}
      </ResponsiveReactGridLayout>
    </>
  );
}
