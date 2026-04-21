"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  FileText,
  Presentation,
  FileSpreadsheet,
  Building2,
  Layers,
  Globe,
  GitCompare,
  Star,
  Pencil,
  Trash2,
  MoreHorizontal,
} from "lucide-react";
import { SidebarUserMenu } from "./sidebar-user-menu";
import {
  useAnalysesHistory,
  fetchHistoryItem,
  renameHistoryItem,
  toggleHistoryFavorite,
  deleteFromHistory,
  type HistoryKind,
} from "@/hooks/use-analyses-history";
import { useI18n } from "@/i18n/provider";

interface AnalysisFiles {
  pdf?: string;
  pptx?: string;
  xlsx?: string;
}

export function Sidebar() {
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const isResultats = pathname?.startsWith("/resultats/");
  const jobId = isResultats ? pathname.split("/").pop() : null;

  const { items: historyItems, loading: historyLoading, reload: reloadHistory } = useAnalysesHistory();
  const [files, setFiles] = useState<AnalysisFiles | null>(null);
  const [ticker, setTicker] = useState<string>("");
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState<string>("");
  const [favFilter, setFavFilter] = useState(false);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-history-menu]")) setMenuOpenId(null);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  async function onToggleFav(id: string, next: boolean) {
    await toggleHistoryFavorite(id, next);
    reloadHistory();
  }
  async function onRenameSubmit(id: string) {
    if (renameValue.trim()) await renameHistoryItem(id, renameValue);
    setRenamingId(null);
    setRenameValue("");
    reloadHistory();
  }
  async function onDeleteItem(id: string) {
    await deleteFromHistory(id);
    setMenuOpenId(null);
    reloadHistory();
  }

  async function openHistoryItem(id: string) {
    setLoadingId(id);
    try {
      const item = await fetchHistoryItem(id);
      if (!item) return;
      // Restaure dans sessionStorage avec la clé attendue par /resultats/[id]
      try {
        sessionStorage.setItem(
          `analysis_${item.job_id}`,
          JSON.stringify(item.payload),
        );
      } catch {}
      const qs = new URLSearchParams({
        ticker: item.ticker || item.label,
        kind: item.kind,
      });
      router.push(`/resultats/${item.job_id}?${qs.toString()}`);
    } finally {
      setLoadingId(null);
    }
  }

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
  const fileUrl = (path: string, forceDownload: boolean = false) => {
    if (path.startsWith("http")) {
      // Supabase Storage : append ?download pour forcer l'attachement si demandé
      if (forceDownload) {
        return path + (path.includes("?") ? "&" : "?") + "download=1";
      }
      return path;
    }
    // Encode segments (spaces, &, accents) pour éviter "no such file"
    const encoded = path.split("/").map(encodeURIComponent).join("/");
    const suffix = forceDownload ? "?download=1" : "";
    return `${apiBase}/file/${encoded}${suffix}`;
  };

  // Force download client-side via fetch+blob (contourne les navigateurs
  // qui ouvrent inline malgré Content-Disposition, et les URLs Supabase
  // Storage qui ne supportent pas toujours ?download).
  async function forceDownloadClient(url: string, filename: string) {
    try {
      const r = await fetch(url, { credentials: "omit" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (e) {
      // Fallback : ouverture dans nouvel onglet si fetch fail (CORS)
      window.open(url, "_blank");
      console.warn("[download] fallback window.open", e);
    }
  }

  return (
    <aside className="hidden md:flex fixed left-0 top-0 h-screen w-56 flex-col bg-white dark:bg-ink-900 text-ink-900 dark:text-ink-50 border-r border-ink-200 dark:border-ink-700 z-40">
      {/* Logo SVG vectoriel — version sombre en dark mode */}
      <Link href="/app" className="block px-4 pt-4 pb-3 border-b border-ink-100 dark:border-ink-700">
        <Image
          src="/logo.svg"
          alt="FinSight IA"
          width={1398}
          height={752}
          priority
          unoptimized
          className="object-contain h-24 w-auto block dark:hidden"
        />
        <Image
          src="/logo-finsight-white.png"
          alt="FinSight IA"
          width={1398}
          height={752}
          priority
          unoptimized
          className="object-contain h-24 w-auto hidden dark:block"
        />
      </Link>

      <nav className="flex-1 px-4 py-3 overflow-y-auto">
        {/* Livrables */}
        <div className="border-b border-ink-100 pb-3.5 mb-3.5">
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2.5">
            {t("nav.deliverables")}
          </div>
          {isResultats && files && (files.pdf || files.pptx || files.xlsx) ? (
            <div className="space-y-2">
              {files.pptx && (
                <DownloadLink
                  onClick={() =>
                    forceDownloadClient(
                      fileUrl(files.pptx!, true),
                      `${ticker || "analyse"}.pptx`,
                    )
                  }
                  icon={<Presentation className="w-3.5 h-3.5" />}
                  label={`${t("nav.pptx_pitchbook")} ${ticker} `}
                  ext=".pptx"
                />
              )}
              {files.xlsx && (
                <DownloadLink
                  onClick={() =>
                    forceDownloadClient(
                      fileUrl(files.xlsx!, true),
                      `${ticker || "analyse"}.xlsx`,
                    )
                  }
                  icon={<FileSpreadsheet className="w-3.5 h-3.5" />}
                  label={`${t("nav.xlsx_model")} ${ticker} `}
                  ext=".xlsx"
                />
              )}
              {files.pdf && (
                <DownloadLink
                  onClick={() =>
                    forceDownloadClient(
                      fileUrl(files.pdf!, true),
                      `${ticker || "analyse"}.pdf`,
                    )
                  }
                  icon={<FileText className="w-3.5 h-3.5" />}
                  label={`${t("nav.pdf_report")} ${ticker} `}
                  ext=".pdf"
                />
              )}
            </div>
          ) : (
            <div className="text-xs text-ink-400">{t("nav.deliverables_empty")}</div>
          )}
        </div>

        {/* Historique */}
        <div className="border-b border-ink-100 pb-3.5 mb-3.5">
          <div className="flex items-center justify-between mb-2.5">
            <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
              {t("nav.history_title")}
            </div>
            <button
              type="button"
              onClick={() => setFavFilter((v) => !v)}
              title={favFilter ? "Tout afficher" : "Afficher uniquement les favoris"}
              className={
                "p-0.5 rounded transition-colors " +
                (favFilter ? "text-amber-500" : "text-ink-400 hover:text-amber-500")
              }
            >
              <Star className={"w-3.5 h-3.5 " + (favFilter ? "fill-amber-500" : "")} />
            </button>
          </div>
          {historyLoading ? (
            <div className="text-xs text-ink-400">{t("common.loading")}</div>
          ) : historyItems.length === 0 ? (
            <div className="text-xs text-ink-400">
              {t("nav.history_empty")}
            </div>
          ) : (
            <div className="space-y-1">
              {historyItems
                .filter((it) => !favFilter || it.is_favorite)
                .map((it) => {
                const Icon = iconForKind(it.kind);
                const isActive = jobId === it.job_id;
                const isLoading = loadingId === it.id;
                const label = it.display_name || it.label;
                const isMenuOpen = menuOpenId === it.id;
                const isRenaming = renamingId === it.id;
                return (
                  <div
                    key={it.id}
                    className={
                      "group relative flex items-center gap-1 px-2 py-1.5 rounded-md text-xs transition-colors " +
                      (isActive
                        ? "bg-navy-50 text-navy-600 font-medium"
                        : "text-ink-700 hover:bg-ink-100/50")
                    }
                  >
                    <Icon className="w-3.5 h-3.5 shrink-0 text-ink-400" />
                    {isRenaming ? (
                      <input
                        type="text"
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onBlur={() => onRenameSubmit(it.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") onRenameSubmit(it.id);
                          if (e.key === "Escape") { setRenamingId(null); setRenameValue(""); }
                        }}
                        className="flex-1 bg-white border border-navy-300 rounded px-1 text-xs text-ink-900 focus:outline-none"
                      />
                    ) : (
                      <button
                        type="button"
                        onClick={() => openHistoryItem(it.id)}
                        disabled={isLoading}
                        className="truncate flex-1 text-left"
                        title={label}
                      >
                        {label}
                      </button>
                    )}
                    {!isRenaming && (
                      <>
                        {it.is_favorite && (
                          <Star className="w-3 h-3 shrink-0 text-amber-500 fill-amber-500" />
                        )}
                        <div className="relative" data-history-menu>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setMenuOpenId(isMenuOpen ? null : it.id);
                            }}
                            className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-ink-200 transition-opacity"
                            title="Options"
                          >
                            <MoreHorizontal className="w-3.5 h-3.5 text-ink-500" />
                          </button>
                          {isMenuOpen && (
                            <div className="absolute right-0 top-full mt-1 w-40 bg-white border border-ink-200 rounded-md shadow-lg z-50 py-1">
                              <button
                                type="button"
                                onClick={() => {
                                  setRenameValue(it.display_name || it.label);
                                  setRenamingId(it.id);
                                  setMenuOpenId(null);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-ink-700 hover:bg-ink-50"
                              >
                                <Pencil className="w-3 h-3" /> Renommer
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  onToggleFav(it.id, !it.is_favorite);
                                  setMenuOpenId(null);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-ink-700 hover:bg-ink-50"
                              >
                                <Star className={"w-3 h-3 " + (it.is_favorite ? "fill-amber-500 text-amber-500" : "")} />
                                {it.is_favorite ? "Retirer des favoris" : "Mettre en favori"}
                              </button>
                              <button
                                type="button"
                                onClick={() => onDeleteItem(it.id)}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-signal-sell hover:bg-red-50"
                              >
                                <Trash2 className="w-3 h-3" /> Supprimer
                              </button>
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </nav>

      {/* Menu utilisateur (bas de sidebar) */}
      <SidebarUserMenu />
    </aside>
  );
}

function iconForKind(kind: HistoryKind) {
  switch (kind) {
    case "societe":
    case "portrait":
      return Building2;
    case "secteur":
      return Layers;
    case "indice":
      return Globe;
    case "comparatif":
      return GitCompare;
    default:
      return Building2;
  }
}

function DownloadLink({
  href,
  onClick,
  icon,
  label,
  ext,
}: {
  href?: string;
  onClick?: () => void;
  icon: React.ReactNode;
  label: string;
  ext: string;
}) {
  // onClick prioritaire sur href : utilisé pour forceDownloadClient (PPTX/XLSX)
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="w-full flex items-center gap-2 px-2.5 py-2 rounded-md border border-ink-200 hover:border-navy-500 hover:bg-navy-50 transition-colors text-xs text-ink-800 group text-left"
      >
        <span className="text-navy-500">{icon}</span>
        <span className="flex-1 truncate">
          {label}
          <span className="text-ink-500 group-hover:text-navy-600">↓ {ext}</span>
        </span>
      </button>
    );
  }
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
