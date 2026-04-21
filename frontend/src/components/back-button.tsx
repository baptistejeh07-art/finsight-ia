"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

interface Props {
  /** URL de fallback si window.history est vide (nouvel onglet). Par défaut "/". */
  fallback?: string;
  /** Libellé. Par défaut "Retour". */
  label?: string;
  /** className additionnel. */
  className?: string;
}

/**
 * Bouton "Retour" réutilisable — fait history.back() si possible,
 * sinon redirige vers `fallback`. Résout le cas où l'utilisateur
 * arrive sur une page secondaire (contact, légal, roadmap...) et
 * ne peut pas retourner là où il était.
 */
export function BackButton({ fallback = "/", label = "Retour", className = "" }: Props) {
  const router = useRouter();

  function handleClick() {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push(fallback);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={
        "inline-flex items-center gap-1.5 text-sm text-ink-600 hover:text-ink-900 transition-colors " +
        className
      }
    >
      <ArrowLeft className="w-4 h-4" />
      {label}
    </button>
  );
}
