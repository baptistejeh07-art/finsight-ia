"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { GripVertical } from "lucide-react";
import { useEditMode } from "@/components/edit-mode-provider";

const STORAGE_KEY = "finsight-dashboard-section-order-v1";

interface SectionItem {
  id: string;
  label: string;
  render: () => ReactNode;
}

/**
 * Mode édition V2 (drag & drop natif HTML5).
 * Permet à Baptiste (et tout user en mode édition Ctrl+Alt+E) de réordonner
 * les grandes sections du dashboard. Ordre sauvegardé dans localStorage.
 *
 * V2.1 (à venir) : sauvegarde côté Supabase Storage pour devenir le standard
 * partagé entre tous les utilisateurs (en mode dev), puis user-specific (multi-user).
 */
export function SortableSections({ items }: { items: SectionItem[] }) {
  const { enabled } = useEditMode();
  const [order, setOrder] = useState<string[]>(() => items.map((i) => i.id));
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const initialized = useRef(false);

  // Charge l'ordre sauvegardé au premier mount
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved: string[] = JSON.parse(raw);
        if (Array.isArray(saved)) {
          const knownIds = new Set(items.map((i) => i.id));
          const filtered = saved.filter((id) => knownIds.has(id));
          const newIds = items.map((i) => i.id).filter((id) => !filtered.includes(id));
          setOrder([...filtered, ...newIds]);
        }
      }
    } catch {
      /* no-op */
    }
  }, [items]);

  // Si la liste d'items change, on s'assure qu'on a tous les ids
  useEffect(() => {
    setOrder((prev) => {
      const known = new Set(items.map((i) => i.id));
      const filtered = prev.filter((id) => known.has(id));
      const missing = items.map((i) => i.id).filter((id) => !filtered.includes(id));
      if (filtered.length === prev.length && missing.length === 0) return prev;
      return [...filtered, ...missing];
    });
  }, [items]);

  function moveItem(fromId: string, toId: string) {
    setOrder((prev) => {
      const fromIdx = prev.indexOf(fromId);
      const toIdx = prev.indexOf(toId);
      if (fromIdx === -1 || toIdx === -1 || fromIdx === toIdx) return prev;
      const next = [...prev];
      next.splice(fromIdx, 1);
      next.splice(toIdx, 0, fromId);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* no-op */
      }
      return next;
    });
  }

  function reset() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
    setOrder(items.map((i) => i.id));
  }

  const itemsById = Object.fromEntries(items.map((i) => [i.id, i]));

  return (
    <>
      {/* Bouton reset visible uniquement en mode édition */}
      {enabled && (
        <div className="mb-3 flex items-center justify-between text-xs">
          <span className="text-amber-700 font-medium">
            Glissez les sections par leur poignée gauche pour les réordonner.
          </span>
          <button
            onClick={reset}
            className="text-xs px-3 py-1 rounded border border-amber-400 text-amber-700 hover:bg-amber-50 transition-colors"
          >
            Réinitialiser l&apos;ordre
          </button>
        </div>
      )}

      {order.map((id) => {
        const item = itemsById[id];
        if (!item) return null;
        const isDragging = draggedId === id;
        const isOver = dragOverId === id && draggedId !== id;
        return (
          <div
            key={id}
            draggable={enabled}
            onDragStart={(e) => {
              if (!enabled) return;
              setDraggedId(id);
              e.dataTransfer.effectAllowed = "move";
              try {
                e.dataTransfer.setData("text/plain", id);
              } catch {}
            }}
            onDragOver={(e) => {
              if (!enabled || !draggedId || draggedId === id) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
              setDragOverId(id);
            }}
            onDragLeave={() => {
              if (dragOverId === id) setDragOverId(null);
            }}
            onDrop={(e) => {
              e.preventDefault();
              if (draggedId && draggedId !== id) moveItem(draggedId, id);
              setDraggedId(null);
              setDragOverId(null);
            }}
            onDragEnd={() => {
              setDraggedId(null);
              setDragOverId(null);
            }}
            className={`relative mb-5 transition-opacity ${
              isDragging ? "opacity-40" : "opacity-100"
            } ${isOver ? "ring-2 ring-amber-400 rounded-md" : ""}`}
            data-section-id={id}
          >
            {enabled && (
              <>
                <div
                  className="absolute -left-7 top-1 text-amber-600 cursor-move select-none"
                  title={`Glisser : ${item.label}`}
                >
                  <GripVertical className="w-4 h-4" />
                </div>
                <div className="absolute -top-5 left-0 text-2xs uppercase tracking-widest text-amber-700 font-semibold pointer-events-none">
                  {item.label}
                </div>
              </>
            )}
            {item.render()}
          </div>
        );
      })}
    </>
  );
}
