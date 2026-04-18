import type { CompanyInfo } from "./types";
import { CompanyLogo } from "./company-logo";
import { trSector } from "@/lib/sectors";

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

  return (
    <div className="flex items-center gap-4">
      <CompanyLogo
        ticker={ci.ticker}
        companyName={ci.company_name}
        size={56}
      />
      <div>
        <h1 className="text-2xl font-bold text-ink-900 tracking-tight leading-tight">
          {ci.company_name || ci.ticker}
        </h1>
        <div className="text-xs text-ink-600 font-mono mt-1">
          {ci.ticker} · {trSector(ci.sector).toUpperCase() || "—"} · {ci.currency || "USD"} · {date}
          {typeof elapsedMs === "number" && elapsedMs > 0
            ? ` · ${(elapsedMs / 1000).toFixed(1)}s`
            : ""}
        </div>
      </div>
    </div>
  );
}
