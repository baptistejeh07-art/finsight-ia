import Link from "next/link";
import Image from "next/image";

type Size = "sm" | "md" | "lg" | "xl";

interface LogoMarkProps {
  className?: string;
  variant?: "auto" | "inverse";
  size?: Size;
}

const SIZE_CLASS: Record<Size, string> = {
  sm: "h-8 w-auto",
  md: "h-10 w-auto",
  lg: "h-14 w-auto",
  xl: "h-20 w-auto",
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
  size = "md",
}: LogoMarkProps) {
  const isInverse = variant === "inverse";
  return (
    <Link
      href="/"
      className={`inline-flex items-center group ${className}`}
      aria-label="FinSight IA — Accueil"
    >
      {isInverse ? (
        <Image
          src="/logo-light.svg"
          alt="FinSight IA"
          width={1398}
          height={752}
          priority
          unoptimized
          className={`object-contain ${SIZE_CLASS[size]}`}
        />
      ) : (
        <>
          <Image
            src="/logo.svg"
            alt="FinSight IA"
            width={1398}
            height={752}
            priority
            unoptimized
            className={`object-contain ${SIZE_CLASS[size]} block dark:hidden`}
          />
          <Image
            src="/logo-light.svg"
            alt="FinSight IA"
            width={1398}
            height={752}
            priority
            unoptimized
            className={`object-contain ${SIZE_CLASS[size]} hidden dark:block`}
          />
        </>
      )}
    </Link>
  );
}
