"use client";

/**
 * Modal de sélection de graphiques à ajouter au dashboard (edit mode).
 * Catégories à gauche, liste filtrée par kind + data disponible à droite.
 */

import { useState, useMemo } from "react";
import { X, Plus } from "lucide-react";
import {
  CATEGORY_LABELS,
  filterCatalog,
  type ChartDef,
  type ChartCategory,
  type ChartKind,
} from "@/lib/chart-catalog";
import type { AnalysisData } from "./types";

interface Props {
  open: boolean;
  onClose: () => void;
  kind: ChartKind;
  data: AnalysisData | undefined;
  existingIds: Set<string>;
  onPick: (chart: ChartDef) => void;
}

export function ChartPickerModal({
  open,
  onClose,
  kind,
  data,
  existingIds,
  onPick,
}: Props) {
  const [activeCategory, setActiveCategory] = useState<ChartCategory>("performance");

  const available = useMemo(
    () => filterCatalog(kind, data as unknown as Record<string, unknown>),
    [kind, data]
  );

  const categoriesWithCharts = useMemo(() => {
    const set = new Set<ChartCategory>();
    available.forEach((c) => set.add(c.category));
    return Array.from(set);
  }, [available]);

  const filtered = useMemo(
    () => available.filter((c) => c.category === activeCategory),
    [available, activeCategory]
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-ink-200">
          <div>
            <div className="text-[10px] uppercase tracking-[1.5px] text-ink-500 font-semibold">
              Ajouter un graphique
            </div>
            <div className="text-sm font-semibold text-ink-900">
              Palette de graphiques disponibles
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-ink-100 text-ink-600"
            title="Fermer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar catégories */}
          <aside className="w-40 border-r border-ink-200 bg-ink-50 p-2 overflow-auto flex-none">
            <div className="text-[9px] uppercase tracking-wider text-ink-500 font-semibold px-2 pb-1.5">
              Catégories
            </div>
            {(["performance", "valuation", "risk", "composition", "quality"] as ChartCategory[]).map(
              (cat) => {
                const disabled = !categoriesWithCharts.includes(cat);
                const active = cat === activeCategory;
                return (
                  <button
                    key={cat}
                    disabled={disabled}
                    onClick={() => setActiveCategory(cat)}
                    className={`w-full text-left text-xs px-2.5 py-2 rounded transition-colors ${
                      active
                        ? "bg-navy-900 text-white font-semibold"
                        : disabled
                        ? "text-ink-400 cursor-not-allowed"
                        : "text-ink-700 hover:bg-white"
                    }`}
                  >
                    {CATEGORY_LABELS[cat]}
                    {!disabled && (
                      <span
                        className={`ml-1.5 text-[10px] ${
                          active ? "opacity-70" : "text-ink-400"
                        }`}
                      >
                        ({available.filter((c) => c.category === cat).length})
                      </span>
                    )}
                  </button>
                );
              }
            )}
          </aside>

          {/* Liste charts */}
          <div className="flex-1 overflow-auto p-4">
            {filtered.length === 0 ? (
              <div className="text-center text-sm text-ink-500 py-10">
                Aucun graphique disponible dans cette catégorie pour ce type d'analyse.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filtered.map((chart) => {
                  const alreadyAdded = existingIds.has(chart.id);
                  return (
                    <button
                      key={chart.id}
                      onClick={() => !alreadyAdded && onPick(chart)}
                      disabled={alreadyAdded}
                      className={`text-left border rounded-md p-3 transition-colors ${
                        alreadyAdded
                          ? "border-ink-200 bg-ink-50 opacity-60 cursor-not-allowed"
                          : "border-ink-200 hover:border-navy-500 hover:bg-navy-50 cursor-pointer"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-ink-900 truncate">
                            {chart.label}
                          </div>
                          <div className="text-[11px] text-ink-600 mt-0.5 leading-snug">
                            {chart.description}
                          </div>
                          <div className="text-[9px] uppercase tracking-wider text-ink-500 font-semibold mt-1.5">
                            {CATEGORY_LABELS[chart.category]}
                          </div>
                        </div>
                        {alreadyAdded ? (
                          <div className="shrink-0 text-[10px] text-ink-500 font-semibold">
                            Déjà ajouté
                          </div>
                        ) : (
                          <Plus className="w-4 h-4 text-navy-600 shrink-0 mt-0.5" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="px-5 py-2 border-t border-ink-200 bg-ink-50 text-[10px] text-ink-500">
          Les graphiques ajoutés sont sauvegardés localement (par type d'analyse).
        </div>
      </div>
    </div>
  );
}
