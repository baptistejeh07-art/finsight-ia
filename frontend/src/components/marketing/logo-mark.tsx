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
 * Logo FinSight — SVG vectoriel officiel.
 * variant="auto" : navy sur clair, blanc sur sombre (filter dark:invert).
 * variant="inverse" : toujours blanc (footer fond navy permanent).
 */
export function LogoMark({
  className = "",
  variant = "auto",
  size = "md",
}: LogoMarkProps) {
  // PNG haute résolution (2x) au lieu du SVG vectorisé qui rendait flou
  // (VTracer génère des chemins polygonaux anti-aliasés au render).
  // logo-finsight-2x.png : navy sur transparent vrai (1002x712)
  // logo-finsight-white-2x.png : blanc sur transparent vrai (1002x712)
  const isInverse = variant === "inverse";
  return (
    <Link
      href="/"
      className={`inline-flex items-center group ${className}`}
      aria-label="FinSight IA — Accueil"
    >
      {/* Light mode : navy. Dark mode : blanc (variante swap par CSS) */}
      {isInverse ? (
        <Image
          src="/logo-finsight-white-2x.png"
          alt="FinSight IA"
          width={1002}
          height={712}
          priority
          unoptimized
          className={`object-contain ${SIZE_CLASS[size]}`}
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
            className={`object-contain ${SIZE_CLASS[size]} block dark:hidden`}
          />
          <Image
            src="/logo-finsight-white-2x.png"
            alt="FinSight IA"
            width={1002}
            height={712}
            priority
            unoptimized
            className={`object-contain ${SIZE_CLASS[size]} hidden dark:block`}
          />
        </>
      )}
    </Link>
  );
}
