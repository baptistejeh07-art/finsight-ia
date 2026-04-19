"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { FileText, Presentation, FileSpreadsheet } from "lucide-react";
import { SidebarUserMenu } from "./sidebar-user-menu";

interface AnalysisFiles {
  pdf?: string;
  pptx?: string;
  xlsx?: string;
}

export function Sidebar() {
  const pathname = usePathname();
  const isResultats = pathname?.startsWith("/resultats/");
  const jobId = isResultats ? pathname.split("/").pop() : null;

  const [files, setFiles] = useState<AnalysisFiles | null>(null);
  const [ticker, setTicker] = useState<string>("");

  useEffect(() => {
    if (!jobId) {
      setFiles(null);
      setTicker("");
      return;
    }
    try {
      const stored = sessionStorage.getItem(`analysis_${jobId}`);
      if (stored) {
        const parsed = JSON.parse(stored);
        setFiles(parsed?.files || null);
        const data = parsed?.data || {};
        const t =
          data?.ticker ||
          data?.raw_data?.company_info?.ticker ||
          parsed?.label ||
          "";
        setTicker(typeof t === "string" ? t : "");
      }
    } catch {
      /* noop */
    }
  }, [jobId]);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
  const fileUrl = (path: string) =>
    path.startsWith("http") ? path : `${apiBase}/file/${path}`;

  return (
    <aside className="hidden md:flex fixed left-0 top-0 h-screen w-56 flex-col bg-white text-ink-900 border-r border-ink-200 z-40">
      {/* Logo SVG vectoriel (sans fond) */}
      <Link href="/app" className="block px-4 pt-4 pb-3 border-b border-ink-100">
        <Image
          src="/logo.svg"
          alt="FinSight IA"
          width={1398}
          height={752}
          priority
          unoptimized
          className="object-contain h-24 w-auto"
        />
      </Link>

      <nav className="flex-1 px-4 py-3 overflow-y-auto">
        {/* Livrables */}
        <div className="border-b border-ink-100 pb-3.5 mb-3.5">
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2.5">
            Livrables
          </div>
          {isResultats && files && (files.pdf || files.pptx || files.xlsx) ? (
            <div className="space-y-2">
              {files.pptx && (
                <DownloadLink
                  href={fileUrl(files.pptx)}
                  icon={<Presentation className="w-3.5 h-3.5" />}
                  label={`Pitchbook ${ticker} `}
                  ext=".pptx"
                />
              )}
              {files.xlsx && (
                <DownloadLink
                  href={fileUrl(files.xlsx)}
                  icon={<FileSpreadsheet className="w-3.5 h-3.5" />}
                  label={`Excel financier ${ticker} `}
                  ext=".xlsx"
                />
              )}
              {files.pdf && (
                <DownloadLink
                  href={fileUrl(files.pdf)}
                  icon={<FileText className="w-3.5 h-3.5" />}
                  label={`Rapport PDF ${ticker} `}
                  ext=".pdf"
                />
              )}
            </div>
          ) : (
            <div className="text-xs text-ink-400">Disponibles après analyse</div>
          )}
        </div>

        {/* Historique */}
        <div className="border-b border-ink-100 pb-3.5 mb-3.5">
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2.5">
            Historique d&apos;analyses
          </div>
          <div className="text-xs text-ink-400">Disponibles après analyse</div>
        </div>

      </nav>

      {/* Menu utilisateur (bas de sidebar) */}
      <SidebarUserMenu />
    </aside>
  );
}

function DownloadLink({
  href,
  icon,
  label,
  ext,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  ext: string;
}) {
  return (
    <a
      href={href}
      download
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 px-2.5 py-2 rounded-md border border-ink-200 hover:border-navy-500 hover:bg-navy-50 transition-colors text-xs text-ink-800 group"
    >
      <span className="text-navy-500">{icon}</span>
      <span className="flex-1 truncate">
        {label}
        <span className="text-ink-500 group-hover:text-navy-600">↓ {ext}</span>
      </span>
    </a>
  );
}
