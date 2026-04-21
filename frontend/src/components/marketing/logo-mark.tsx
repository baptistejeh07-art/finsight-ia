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
  sm: "h-8 w-auto",
  md: "h-12 w-auto",
  lg: "h-16 w-auto",
  xl: "h-24 w-auto",
  "2xl": "h-32 w-auto",
  "3xl": "h-40 w-auto",
};

/**
 * Logo FinSight — SVG vectoriel (transparent).
 * variant="auto"   : navy (logo.svg) en clair, blanc (logo-light.svg) en dark.
 * variant="inverse" : toujours blanc (footer fond navy permanent).
 *
 * Retour au SVG après que le PNG "2x" ait été repéré avec un fond blanc plein
 * qui créait un halo rectangulaire sur les zones colorées (ex: hero navy).
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
        /* Footer : PNG 2x net (la version SVG tracée par VTracer pixélise aux
           grandes tailles car polygonal plutôt que vectoriel). */
        <Image
          src="/logo-finsight-white-2x.png"
          alt="FinSight IA"
          width={1002}
          height={712}
          priority
          unoptimized
          className={`object-contain ${SIZE_CLASS[effectiveSize]}`}
        />
      ) : (
        <>
          <Image
            src="/logo-finsight-2x.png"
            alt="FinSight IA"
            width={1002}
            height={712}
            priority
            unoptimized
            className={`object-contain ${SIZE_CLASS[effectiveSize]} block dark:hidden`}
          />
          <Image
            src="/logo-finsight-white-2x.png"
            alt="FinSight IA"
            width={1002}
            height={712}
            priority
            unoptimized
            className={`object-contain ${SIZE_CLASS[effectiveSize]} hidden dark:block`}
          />
        </>
      )}
    </Link>
  );
}
