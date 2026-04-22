"use client";

import Link from "next/link";
import Image from "next/image";
import { useUserPreferences } from "@/hooks/use-user-preferences";

type Size = "sm" | "md" | "lg" | "xl" | "2xl" | "3xl";

interface LogoMarkProps {
  className?: string;
  variant?: "auto" | "inverse";
  /** Taille par défaut. Peut être surchargée par l'utilisateur via préférences. */
  size?: Size;
  /** Ignore les préférences user et force la taille (pour les ctx où ça dérange). */
  noUserOverride?: boolean;
}

const SIZE_CLASS: Record<Size, string> = {
  sm: "h-10 w-auto",
  md: "h-14 w-auto",
  lg: "h-20 w-auto",
  xl: "h-28 w-auto",
  "2xl": "h-36 w-auto",
  "3xl": "h-48 w-auto",
};

/**
 * Logo FinSight — SVG vectoriel re-tracé (Gemini, 210 Ko, vraies courbes).
 * variant="auto"    : version couleur en clair, version blanche en dark.
 * variant="inverse" : toujours blanc (footer fond navy permanent).
 *
 * Passage au vrai SVG vectoriel (2026-04-22) pour ne plus pixéliser aux grandes
 * tailles. Les anciens PNG 2x 1002x712 pixélisaient dès 300 px de hauteur.
 */
export function LogoMark({
  className = "",
  variant = "auto",
  size = "lg",
  noUserOverride = false,
}: LogoMarkProps) {
  const { prefs } = useUserPreferences();
  const isInverse = variant === "inverse";
  // Override user (si défini dans préférences)
  const effectiveSize: Size = (
    !noUserOverride && prefs.logo_size && prefs.logo_size in SIZE_CLASS
      ? prefs.logo_size
      : size
  ) as Size;
  return (
    <Link
      href="/"
      className={`inline-flex items-center group ${className}`}
      aria-label="FinSight IA — Accueil"
    >
      {isInverse ? (
        /* Footer : version blanche (fond navy permanent). */
        <Image
          src="/logo-finsight-vector-white.svg"
          alt="FinSight IA"
          width={1398}
          height={752}
          priority
          unoptimized
          className={`object-contain ${SIZE_CLASS[effectiveSize]}`}
        />
      ) : (
        <>
          <Image
            src="/logo-finsight-vector.svg"
            alt="FinSight IA"
            width={1398}
            height={752}
            priority
            unoptimized
            className={`object-contain ${SIZE_CLASS[effectiveSize]} block dark:hidden`}
          />
          <Image
            src="/logo-finsight-vector-white.svg"
            alt="FinSight IA"
            width={1398}
            height={752}
            priority
            unoptimized
            className={`object-contain ${SIZE_CLASS[effectiveSize]} hidden dark:block`}
          />
        </>
      )}
    </Link>
  );
}
