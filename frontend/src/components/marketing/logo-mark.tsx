import Link from "next/link";

interface LogoMarkProps {
  className?: string;
  variant?: "auto" | "inverse";
}

/**
 * Logo FinSight — vectoriel, fidèle au logo original (3 barres montantes + wordmark).
 * variant="auto" suit le thème (text-text-primary). variant="inverse" reste toujours clair.
 */
export function LogoMark({ className = "", variant = "auto" }: LogoMarkProps) {
  const colorClass = variant === "inverse" ? "text-white" : "text-text-primary";

  return (
    <Link
      href="/"
      className={`inline-flex items-center group ${className}`}
      aria-label="FinSight IA — Accueil"
    >
      <FinSightLogo className={`h-8 w-auto ${colorClass}`} />
    </Link>
  );
}

function FinSightLogo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 60"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="FinSight"
      className={className}
    >
      {/* Picto : 3 barres montantes (style bar chart) */}
      <g fill="currentColor">
        <rect x="0" y="34" width="11" height="24" rx="1.5" />
        <rect x="15" y="22" width="11" height="36" rx="1.5" />
        <rect x="30" y="6" width="13" height="52" rx="1.5" />
      </g>

      {/* Wordmark FINSIGHT */}
      <text
        x="55"
        y="42"
        fill="currentColor"
        fontFamily="var(--font-dm-sans), system-ui, -apple-system, 'Segoe UI', sans-serif"
        fontWeight="800"
        fontSize="26"
        letterSpacing="0.5"
      >
        FINSIGHT
      </text>
    </svg>
  );
}
