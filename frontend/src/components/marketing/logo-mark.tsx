import Link from "next/link";

export function LogoMark({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/"
      className={`inline-flex items-center gap-2 group ${className}`}
      aria-label="FinSight IA — Accueil"
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="text-text-primary"
      >
        <rect x="3" y="20" width="6" height="9" fill="currentColor" />
        <rect x="11" y="14" width="6" height="15" fill="currentColor" />
        <rect x="19" y="6" width="6" height="23" fill="currentColor" />
      </svg>
      <span className="font-bold text-base tracking-[0.18em] text-text-primary leading-none">
        FINSIGHT
      </span>
    </Link>
  );
}
