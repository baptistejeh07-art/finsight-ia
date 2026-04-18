import Link from "next/link";
import Image from "next/image";

interface LogoMarkProps {
  className?: string;
  variant?: "auto" | "inverse";
}

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
        src="/logo-finsight.png"
        alt="FinSight IA"
        width={501}
        height={356}
        priority
        className={`object-contain h-12 w-auto transition-opacity ${filterClasses}`}
      />
    </Link>
  );
}
