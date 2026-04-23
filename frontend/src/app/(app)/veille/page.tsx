"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, Loader2, RefreshCw, Newspaper } from "lucide-react";
import toast from "react-hot-toast";
import { BackButton } from "@/components/back-button";
import {
  fetchVeille,
  fetchVeilleHistory,
  downloadVeillePdf,
  runVeille,
  waitForJob,
  type VeilleArticle,
  type VeilleHistoryItem,
} from "@/lib/api";

export default function VeillePage() {
  const [article, setArticle] = useState<VeilleArticle | null>(null);
  const [history, setHistory] = useState<VeilleHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const loadLatest = useCallback(async () => {
    setLoading(true);
    try {
      const [art, hist] = await Promise.all([
        fetchVeille().catch(() => null),
        fetchVeilleHistory(10).catch(() => []),
      ]);
      setArticle(art);
      setHistory(hist);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLatest();
  }, [loadLatest]);

  async function handleRun() {
    if (running) return;
    setRunning(true);
    const toastId = toast.loading("Génération de la veille en cours...");
    try {
      const submitted = await runVeille();
      const final = await waitForJob(submitted.job_id, undefined, 4000);
      if (final.status === "done") {
        toast.success("Veille générée.", { id: toastId });
        await loadLatest();
      } else {
        toast.error(final.error || "Échec génération veille.", { id: toastId });
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erreur lors de la génération.",
        { id: toastId },
      );
    } finally {
      setRunning(false);
    }
  }

  async function handleDownload() {
    if (!article?.has_pdf) return;
    setDownloading(true);
    try {
      await downloadVeillePdf(article.pdf_name || "veille.pdf");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Téléchargement impossible.",
      );
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-10 w-full">
      <BackButton className="mb-6" />

      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[2px] text-ink-500 mb-1 flex items-center gap-2">
            <Newspaper className="w-3.5 h-3.5" />
            FinSight IA · Veille IA &amp; Finance d&apos;Entreprise
            {article?.date_fr && <span className="text-ink-400">· {article.date_fr}</span>}
          </div>
          <h1 className="text-3xl font-bold text-ink-900 tracking-tight">
            {article?.title || "Veille IA & Finance d'Entreprise"}
          </h1>
          {article?.subtitle && (
            <p className="text-sm text-ink-600 italic mt-1">{article.subtitle}</p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleRun}
            disabled={running}
            className="btn-secondary !py-2 !px-3 flex items-center gap-2"
            title="Lancer une nouvelle édition de veille"
          >
            {running ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {running ? "Génération..." : "Lancer la veille"}
          </button>
          {article?.has_pdf && (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="btn-primary !py-2 !px-3 flex items-center gap-2"
            >
              {downloading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              Télécharger PDF
            </button>
          )}
        </div>
      </div>

      <div className="border-t border-ink-200 mb-8" />

      {/* Corps de l'article */}
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-ink-500 py-10">
          <Loader2 className="w-4 h-4 animate-spin" />
          Chargement de la dernière édition...
        </div>
      ) : article && article.article_md ? (
        <article className="veille-article text-ink-800 leading-relaxed">
          <MarkdownBody source={article.article_md} />
        </article>
      ) : (
        <div className="bg-ink-50 border border-ink-200 rounded-md p-6 text-sm text-ink-700">
          <p className="font-medium text-ink-900 mb-1">
            Aucune édition de veille disponible pour le moment.
          </p>
          <p className="text-ink-600">
            Cliquez sur <strong>Lancer la veille</strong> pour générer la première
            édition. La collecte RSS + rédaction IA prend en général 1 à 2 minutes.
          </p>
        </div>
      )}

      {/* Historique */}
      {history.length > 1 && (
        <>
          <div className="border-t border-ink-200 mt-12 mb-4" />
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
            Éditions précédentes
          </div>
          <ul className="divide-y divide-ink-100 border border-ink-200 rounded-md overflow-hidden">
            {history.slice(1).map((h) => (
              <li
                key={h.pdf_name}
                className="flex items-center justify-between px-4 py-2.5 text-sm hover:bg-ink-50 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-ink-900 truncate">{h.title || h.pdf_name}</div>
                  {h.date_fr && (
                    <div className="text-xs text-ink-500">{h.date_fr}</div>
                  )}
                </div>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || ""}${h.pdf_url}?download=1`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-navy-600 hover:underline flex items-center gap-1 shrink-0 ml-3"
                >
                  <Download className="w-3 h-3" />
                  PDF
                </a>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="border-t border-ink-200 mt-12 pt-4 text-2xs text-ink-500">
        FinSight IA v1.2 — Veille générée par IA. Ne constitue pas un conseil en
        investissement.
      </div>
    </main>
  );
}

/**
 * Rendu markdown minimaliste — supporte les conventions utilisées par
 * tools/veille.py : ### titres, listes à puces, paragraphes, **bold**, *italic*,
 * `code`, liens [texte](url). Pas de dépendance externe.
 */
function MarkdownBody({ source }: { source: string }) {
  const blocks = parseMarkdownBlocks(source);
  return (
    <>
      {blocks.map((b, i) => {
        if (b.type === "h1") return <h1 key={i} className="text-2xl font-bold text-ink-900 mt-8 mb-3">{renderInline(b.content)}</h1>;
        if (b.type === "h2") return <h2 key={i} className="text-xl font-bold text-ink-900 mt-7 mb-3">{renderInline(b.content)}</h2>;
        if (b.type === "h3") return <h3 key={i} className="text-base font-semibold text-ink-900 mt-6 mb-2 tracking-tight">{renderInline(b.content)}</h3>;
        if (b.type === "ul")
          return (
            <ul key={i} className="list-disc pl-6 space-y-1 my-3 text-sm">
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it)}</li>
              ))}
            </ul>
          );
        if (b.type === "ol")
          return (
            <ol key={i} className="list-decimal pl-6 space-y-1 my-3 text-sm">
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it)}</li>
              ))}
            </ol>
          );
        if (b.type === "hr") return <hr key={i} className="my-6 border-ink-200" />;
        if (b.type === "p") {
          return (
            <p key={i} className="my-3 text-sm">
              {renderInline(b.content)}
            </p>
          );
        }
        return null;
      })}
    </>
  );
}

type MdBlock =
  | { type: "h1" | "h2" | "h3" | "p"; content: string }
  | { type: "ul" | "ol"; items: string[] }
  | { type: "hr" };

function parseMarkdownBlocks(source: string): MdBlock[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: MdBlock[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }
    if (/^---+$/.test(trimmed)) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }
    const h3 = /^###\s+(.+)$/.exec(trimmed);
    if (h3) {
      blocks.push({ type: "h3", content: h3[1] });
      i++;
      continue;
    }
    const h2 = /^##\s+(.+)$/.exec(trimmed);
    if (h2) {
      blocks.push({ type: "h2", content: h2[1] });
      i++;
      continue;
    }
    const h1 = /^#\s+(.+)$/.exec(trimmed);
    if (h1) {
      blocks.push({ type: "h1", content: h1[1] });
      i++;
      continue;
    }
    // liste à puces
    if (/^[-*+]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*+]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*+]\s+/, ""));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }
    // liste numérotée
    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }
    // paragraphe : regroupe les lignes consécutives
    const para: string[] = [line];
    i++;
    while (i < lines.length) {
      const nxt = lines[i];
      const nxtTrim = nxt.trim();
      if (!nxtTrim) break;
      if (/^(#{1,3}\s+|[-*+]\s+|\d+\.\s+|---+$)/.test(nxtTrim)) break;
      para.push(nxt);
      i++;
    }
    blocks.push({ type: "p", content: para.join(" ") });
  }
  return blocks;
}

/**
 * Inline formatters : **bold**, *italic*, `code`, [text](url).
 * Renvoie un tableau de ReactNodes pour injection dans JSX.
 */
function renderInline(text: string): React.ReactNode[] {
  // Regex combiné (ordre important : code puis lien puis bold puis italic)
  const tokenRe = /(`[^`]+`)|(\[[^\]]+\]\([^)]+\))|(\*\*[^*]+\*\*)|(\*[^*]+\*)/g;
  const out: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = tokenRe.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) {
      out.push(
        <code
          key={key++}
          className="px-1 py-0.5 rounded bg-ink-100 text-ink-800 font-mono text-xs"
        >
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith("[")) {
      const linkMatch = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok);
      if (linkMatch) {
        out.push(
          <a
            key={key++}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-navy-600 hover:underline"
          >
            {linkMatch[1]}
          </a>,
        );
      } else {
        out.push(tok);
      }
    } else if (tok.startsWith("**")) {
      out.push(
        <strong key={key++} className="font-semibold text-ink-900">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else if (tok.startsWith("*")) {
      out.push(
        <em key={key++} className="italic">
          {tok.slice(1, -1)}
        </em>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
