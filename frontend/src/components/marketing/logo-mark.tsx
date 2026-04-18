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
        className={`object-contain ${SIZE_CLASS[size]} ${filterClasses}`}
      />
    </Link>
  );
}
