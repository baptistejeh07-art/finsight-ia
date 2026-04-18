import type { CompanyInfo } from "./types";

export function HeaderSociete({
  ci,
  elapsedMs,
}: {
  ci: CompanyInfo;
  elapsedMs?: number;
}) {
  const date = ci.analysis_date
    ? new Date(ci.analysis_date).toLocaleDateString("fr-FR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : new Date().toLocaleDateString("fr-FR");

  const logoUrl = ci.ticker
    ? `https://logo.clearbit.com/${slugDomain(ci.company_name, ci.ticker)}.com`
    : "";

  return (
    <div className="flex items-center gap-4">
      {logoUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt={ci.company_name}
          className="w-12 h-12 rounded object-contain bg-ink-50"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      )}
      <div>
        <h1 className="text-2xl font-bold text-ink-900 tracking-tight leading-tight">
          {ci.company_name || ci.ticker}
        </h1>
        <div className="text-xs text-ink-600 font-mono mt-1">
          {ci.ticker} · {(ci.sector || "—").toUpperCase()} · {ci.currency || "USD"} · {date}
          {typeof elapsedMs === "number" && elapsedMs > 0
            ? ` · ${(elapsedMs / 1000).toFixed(1)}s`
            : ""}
        </div>
      </div>
    </div>
  );
}

function slugDomain(name: string, ticker: string): string {
  // best-effort domain guess: strip "Inc.", "Corp.", spaces
  const base = (name || ticker)
    .toLowerCase()
    .replace(/\b(inc|corp|corporation|ltd|sa|plc|nv|ag|se)\b\.?/g, "")
    .replace(/[^a-z0-9]/g, "")
    .trim();
  return base || ticker.toLowerCase();
}
