import Link from "next/link";
import Image from "next/image";

interface LogoMarkProps {
  className?: string;
  variant?: "auto" | "inverse";
}

/**
 * Logo FinSight — SVG vectoriel officiel.
 * variant="auto" : navy sur clair, blanc sur sombre (filter dark:invert).
 * variant="inverse" : toujours blanc (footer fond navy permanent).
 */
export function LogoMark({ className = "", variant = "auto" }: LogoMarkProps) {
  const filterClasses =
    variant === "inverse"
      ? "brightness-0 invert"
      : "dark:brightness-0 dark:invert";

  return (
    <Link
      href="/"
      className={`inline-flex items-center group ${className}`}
      aria-label="FinSight IA — Accueil"
    >
      <Image
        src="/logo.svg"
        alt="FinSight IA"
        width={1398}
        height={752}
        priority
        unoptimized
        className={`object-contain h-10 w-auto ${filterClasses}`}
      />
    </Link>
  );
}
