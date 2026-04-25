"use client";

import { useEffect, useState } from "react";
import {
  ExternalLink,
  Copy,
  CheckCircle2,
  Send,
  MessageSquare,
  Trophy,
  Ghost,
  Upload,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { apiGet, apiPost, getAuthHeader, API_URL } from "@/lib/api";

interface Prospect {
  id: string;
  linkedin_url: string;
  name?: string;
  headline?: string;
  bio?: string;
  recent_posts?: Array<{ date?: string; text?: string; url?: string }>;
  qualification_score?: number;
  qualification_breakdown?: Record<string, number>;
  qualification_reasoning?: string;
  target_ticker?: string;
  dm_draft?: string;
  pdf_demo_path?: string;
  discovered_at?: string;
}

interface Stats {
  sent_today?: number;
  sent_7d?: number;
  replied_7d?: number;
  converted_7d?: number;
  ghosted_7d?: number;
  revenue_7d?: number;
  reply_rate?: number;
  conversion_rate?: number;
  cap_daily?: number;
  cap_remaining_today?: number;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  sent: { label: "Envoyé", color: "bg-blue-100 text-blue-700 border-blue-200" },
  replied: { label: "A répondu", color: "bg-amber-100 text-amber-700 border-amber-200" },
  converted: { label: "Converti", color: "bg-green-100 text-green-700 border-green-200" },
  ghosted: { label: "Ghosted", color: "bg-gray-100 text-gray-600 border-gray-200" },
};

export default function SalesAgentPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [qualifying, setQualifying] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [topR, statsR] = await Promise.all([
        apiGet<{ prospects: Prospect[] }>("/admin/sales-agent/top-today?limit=10"),
        apiGet<Stats>("/admin/sales-agent/stats"),
      ]);
      setProspects(topR.prospects || []);
      setStats(statsR);
    } catch (e) {
      console.error("[sales-agent] load fail:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const auth = await getAuthHeader();
      const r = await fetch(`${API_URL}/admin/sales-agent/import-csv`, {
        method: "POST",
        headers: { ...auth },
        body: fd,
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      alert(`Import OK : ${data.imported} prospects ajoutés (${data.failed} échecs sur ${data.total})`);
      await load();
    } catch (err) {
      alert(`Import échoué : ${err}`);
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  };

  const handleQualifyAll = async () => {
    setQualifying(true);
    try {
      const r = await apiPost<{ qualified: number }>(
        "/admin/sales-agent/qualify-all?limit=30",
        {}
      );
      alert(`${r.qualified} prospects qualifiés`);
      await load();
    } catch (err) {
      alert(`Qualif échouée : ${err}`);
    } finally {
      setQualifying(false);
    }
  };

  const handleStatus = async (
    id: string,
    status: "sent" | "replied" | "converted" | "ghosted"
  ) => {
    try {
      await apiPost(`/admin/sales-agent/status/${id}?status=${status}`, {});
      // Tous les statuts (sent/replied/converted/ghosted) sortent le
      // prospect de la queue "à contacter aujourd'hui" — on filtre.
      setProspects((p) => p.filter((x) => x.id !== id));
      await load();
    } catch (e) {
      alert(`Status update fail : ${e}`);
    }
  };

  const copyDm = async (p: Prospect) => {
    if (!p.dm_draft) return;
    try {
      await navigator.clipboard.writeText(p.dm_draft);
      setCopiedId(p.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // fallback
    }
  };

  const capPct = stats.cap_daily
    ? Math.min(100, ((stats.sent_today || 0) / stats.cap_daily) * 100)
    : 0;
  const capColor =
    capPct < 70 ? "bg-green-500" : capPct < 90 ? "bg-amber-500" : "bg-red-500";

  return (
    <div className="container mx-auto px-6 py-8 max-w-7xl">
      <header className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-serif font-semibold text-ink-900 mb-1">
              Sales Agent — LinkedIn
            </h1>
            <p className="text-sm text-ink-500">
              AI co-pilot · cap 15 DM/jour · zéro automation côté LinkedIn
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={load}
              disabled={loading}
              className="px-3 py-2 text-sm border border-ink-200 rounded-md hover:bg-ink-50 disabled:opacity-50 flex items-center gap-2"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Recharger
            </button>
            <button
              onClick={handleQualifyAll}
              disabled={qualifying}
              className="px-3 py-2 text-sm bg-navy-500 text-white rounded-md hover:bg-navy-600 disabled:opacity-50 flex items-center gap-2"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {qualifying ? "Qualif en cours…" : "Qualifier non scorés"}
            </button>
            <label className="px-3 py-2 text-sm border border-ink-200 rounded-md hover:bg-ink-50 cursor-pointer flex items-center gap-2">
              <Upload className="w-3.5 h-3.5" />
              {importing ? "Import…" : "Importer CSV"}
              <input
                type="file"
                accept=".csv"
                disabled={importing}
                onChange={handleCsvUpload}
                className="hidden"
              />
            </label>
          </div>
        </div>

        {/* Stats header */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <StatCard label="DM aujourd'hui" value={`${stats.sent_today || 0} / ${stats.cap_daily || 15}`} sub={`${stats.cap_remaining_today || 0} restants`} />
          <StatCard label="DM 7 jours" value={`${stats.sent_7d || 0}`} sub={`Cap hebdo 105`} />
          <StatCard label="Taux réponse" value={`${stats.reply_rate || 0}%`} sub={`${stats.replied_7d || 0} répondants`} />
          <StatCard label="Conversions" value={`${stats.converted_7d || 0}`} sub={`${stats.conversion_rate || 0}% réplyés`} />
          <StatCard label="Revenue 7j" value={`${stats.revenue_7d?.toFixed(0) || 0} €`} sub="Early Backers" />
        </div>

        {/* Cap progress bar */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-ink-600 mb-1">
            <span>Cap journalier (anti-ban)</span>
            <span className="font-mono">{stats.sent_today || 0} / {stats.cap_daily || 15}</span>
          </div>
          <div className="h-2 bg-ink-100 rounded-full overflow-hidden">
            <div className={`h-full ${capColor} transition-all`} style={{ width: `${capPct}%` }} />
          </div>
        </div>
      </header>

      <h2 className="text-lg font-semibold text-ink-900 mb-3">
        Top {prospects.length} aujourd'hui
      </h2>

      {prospects.length === 0 ? (
        <div className="bg-white border border-ink-200 rounded-lg p-12 text-center text-ink-500">
          {loading
            ? "Chargement…"
            : "Aucun prospect prêt à contacter. Importe un CSV ou lance la qualification sur les prospects non scorés."}
        </div>
      ) : (
        <div className="space-y-4">
          {prospects.map((p) => (
            <ProspectCard
              key={p.id}
              prospect={p}
              copied={copiedId === p.id}
              onCopy={() => copyDm(p)}
              onStatus={(s) => handleStatus(p.id, s)}
            />
          ))}
        </div>
      )}

      {/* Section Relances J+3 / J+7 */}
      <RelancesSection />
    </div>
  );
}

interface RelanceRow {
  id: string;
  prospect_id: string;
  status: string;
  sent_at?: string;
  relance_1_text?: string;
  relance_1_sent_at?: string;
  relance_2_text?: string;
  relance_2_sent_at?: string;
  sales_prospects?: {
    name?: string;
    headline?: string;
    linkedin_url?: string;
    target_ticker?: string;
    dm_draft?: string;
  };
}

function RelancesSection() {
  const [r3, setR3] = useState<RelanceRow[]>([]);
  const [r7, setR7] = useState<RelanceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [drafting, setDrafting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await apiGet<{
        prospects_to_relance_3: RelanceRow[];
        prospects_to_relance_7: RelanceRow[];
      }>("/admin/sales-agent/relances/queue");
      setR3(data.prospects_to_relance_3 || []);
      setR7(data.prospects_to_relance_7 || []);
    } catch (e) {
      console.error("[relances] load fail:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDraft = async () => {
    setDrafting(true);
    try {
      const data = await apiPost<{ count: number }>(
        "/admin/sales-agent/relances/draft-pending?limit=20",
        {}
      );
      alert(`${data.count} relances rédigées par l'IA. Recharge pour voir.`);
      await load();
    } catch (e) {
      alert(`Draft fail : ${e}`);
    } finally {
      setDrafting(false);
    }
  };

  const handleAutoGhost = async () => {
    if (!confirm("Marquer tous les prospects sans réponse depuis 14j comme 'ghosted' ?")) return;
    try {
      const r = await apiPost<{ ghosted: number }>(
        "/admin/sales-agent/relances/auto-ghost?days_threshold=14",
        {}
      );
      alert(`${r.ghosted} prospects archivés en 'ghosted'.`);
      await load();
    } catch (e) {
      alert(`Auto-ghost fail : ${e}`);
    }
  };

  const handleSent = async (id: string, type: "J3" | "J7") => {
    try {
      await apiPost(
        `/admin/sales-agent/relances/sent/${id}?relance_type=${type}`,
        {}
      );
      await load();
    } catch (e) {
      alert(`Mark sent fail : ${e}`);
    }
  };

  const total = r3.length + r7.length;
  const drafted = r3.filter((r) => r.relance_1_text).length
                 + r7.filter((r) => r.relance_2_text).length;

  return (
    <section className="mt-12">
      <div className="flex items-end justify-between mb-3">
        <div>
          <h2 className="text-lg font-semibold text-ink-900">
            Relances en attente
          </h2>
          <p className="text-xs text-ink-500">
            {total} prospects à relancer · {drafted} relances déjà rédigées par l'IA
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleDraft}
            disabled={drafting || total === 0}
            className="px-3 py-2 text-sm bg-navy-500 text-white rounded-md hover:bg-navy-600 disabled:opacity-50"
          >
            {drafting ? "Rédaction…" : "✨ Rédiger les relances en attente"}
          </button>
          <button
            onClick={handleAutoGhost}
            className="px-3 py-2 text-sm border border-ink-200 rounded-md hover:bg-ink-50"
            title="Marque comme ghosted les prospects sans réponse depuis 14j"
          >
            🧹 Auto-ghost &gt;14j
          </button>
        </div>
      </div>
      {loading && <div className="text-xs text-ink-500">Chargement…</div>}
      {!loading && total === 0 && (
        <div className="bg-white border border-ink-200 rounded-lg p-6 text-center text-sm text-ink-500">
          Aucune relance en attente. Bonne nouvelle : soit tu n'as pas encore
          envoyé de DM, soit tous tes contacts sont &lt; 3 jours.
        </div>
      )}
      {r3.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-ink-700 mb-2">
            J+3 ({r3.length}) — premier rebond, angle question ouverte
          </h3>
          <div className="space-y-3">
            {r3.map((r) => (
              <RelanceCard
                key={r.id}
                row={r}
                type="J3"
                onSent={() => handleSent(r.id, "J3")}
              />
            ))}
          </div>
        </div>
      )}
      {r7.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-ink-700 mb-2">
            J+7 ({r7.length}) — dernier ping, offre asymétrique
          </h3>
          <div className="space-y-3">
            {r7.map((r) => (
              <RelanceCard
                key={r.id}
                row={r}
                type="J7"
                onSent={() => handleSent(r.id, "J7")}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function RelanceCard({
  row, type, onSent,
}: {
  row: RelanceRow;
  type: "J3" | "J7";
  onSent: () => void;
}) {
  const text = type === "J3" ? row.relance_1_text : row.relance_2_text;
  const sent = type === "J3"
    ? !!row.relance_1_sent_at
    : !!row.relance_2_sent_at;
  const p = row.sales_prospects || {};
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden">
      <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 flex items-center gap-2">
        <span className="text-xs font-mono px-2 py-0.5 bg-amber-200 text-amber-800 rounded">
          {type}
        </span>
        <span className="font-semibold text-sm text-ink-900">{p.name || "—"}</span>
        <span className="text-xs text-ink-500 truncate flex-1">{p.headline || ""}</span>
        {p.target_ticker && (
          <span className="text-xs font-mono text-navy-700 bg-navy-100 px-2 py-0.5 rounded">
            {p.target_ticker}
          </span>
        )}
      </div>
      <div className="px-4 py-3">
        {text ? (
          <div className="bg-ink-50 border border-ink-100 rounded p-2 text-sm text-ink-800 whitespace-pre-wrap">
            {text}
          </div>
        ) : (
          <div className="text-xs text-ink-400 italic">
            Texte non encore rédigé. Clique « Rédiger les relances en attente » en haut.
          </div>
        )}
      </div>
      <div className="px-4 py-2 border-t border-ink-100 bg-ink-50 flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={copy}
            disabled={!text}
            className="px-2 py-1 text-xs bg-navy-500 text-white rounded hover:bg-navy-600 disabled:opacity-40"
          >
            {copied ? "Copié !" : "Copier relance"}
          </button>
          {p.linkedin_url && (
            <a
              href={p.linkedin_url}
              target="_blank"
              rel="noreferrer"
              className="px-2 py-1 text-xs border border-ink-200 rounded hover:bg-white"
            >
              Ouvrir LinkedIn
            </a>
          )}
        </div>
        <button
          onClick={onSent}
          disabled={!text || sent}
          className="px-3 py-1 text-xs border border-green-300 bg-green-50 text-green-700 rounded hover:bg-green-100 disabled:opacity-40"
        >
          {sent ? "✓ Envoyée" : "Marquer envoyée"}
        </button>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white border border-ink-200 rounded-md p-3">
      <div className="text-[10px] uppercase tracking-wider text-ink-500 font-semibold">
        {label}
      </div>
      <div className="text-xl font-bold text-ink-900 mt-1">{value}</div>
      {sub && <div className="text-[10px] text-ink-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function ProspectCard({
  prospect: p,
  copied,
  onCopy,
  onStatus,
}: {
  prospect: Prospect;
  copied: boolean;
  onCopy: () => void;
  onStatus: (s: "sent" | "replied" | "converted" | "ghosted") => void;
}) {
  const score = p.qualification_score || 0;
  const scoreColor =
    score >= 85
      ? "bg-green-500"
      : score >= 70
      ? "bg-blue-500"
      : "bg-amber-500";
  return (
    <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
      <div className="px-5 py-3 border-b border-ink-100 flex items-center gap-3 bg-ink-50">
        <div className={`${scoreColor} text-white font-bold rounded-full w-10 h-10 flex items-center justify-center text-sm`}>
          {score}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-ink-900 truncate">{p.name || "—"}</div>
          <div className="text-xs text-ink-500 truncate">{p.headline || "—"}</div>
        </div>
        {p.target_ticker && (
          <div className="px-2 py-1 bg-navy-100 text-navy-700 text-xs font-mono rounded">
            {p.target_ticker}
          </div>
        )}
        <a
          href={p.linkedin_url}
          target="_blank"
          rel="noreferrer"
          className="text-ink-500 hover:text-navy-600"
          title="Ouvrir profil LinkedIn"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>

      <div className="px-5 py-3">
        {p.qualification_reasoning && (
          <details className="text-xs text-ink-600 mb-3">
            <summary className="cursor-pointer hover:text-ink-900">Raisonnement IA</summary>
            <div className="mt-2 italic">{p.qualification_reasoning}</div>
            {p.qualification_breakdown && (
              <div className="mt-2 grid grid-cols-5 gap-1">
                {Object.entries(p.qualification_breakdown).map(([k, v]) => (
                  <div key={k} className="text-center">
                    <div className="text-[10px] text-ink-500">{k}</div>
                    <div className="font-mono font-semibold">{v}</div>
                  </div>
                ))}
              </div>
            )}
          </details>
        )}
        {p.dm_draft ? (
          <div className="bg-ink-50 border border-ink-100 rounded p-3 text-sm text-ink-800 whitespace-pre-wrap font-sans">
            {p.dm_draft}
          </div>
        ) : (
          <div className="text-xs text-ink-400 italic">DM non encore rédigé</div>
        )}
      </div>

      <div className="px-5 py-3 border-t border-ink-100 bg-ink-50 flex flex-wrap gap-2 items-center justify-between">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={onCopy}
            disabled={!p.dm_draft}
            className="px-3 py-1.5 text-xs bg-navy-500 text-white rounded hover:bg-navy-600 disabled:opacity-40 flex items-center gap-1"
          >
            {copied ? <CheckCircle2 className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            {copied ? "Copié !" : "Copier DM"}
          </button>
          <a
            href={p.linkedin_url}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 text-xs border border-ink-200 rounded hover:bg-white flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            Ouvrir LinkedIn
          </a>
          {p.pdf_demo_path && p.target_ticker && (
            <a
              href={`/preview/${p.target_ticker}/${p.target_ticker}_report.pdf`}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 text-xs border border-ink-200 rounded hover:bg-white"
            >
              📎 PDF démo {p.target_ticker}
            </a>
          )}
        </div>
        <div className="flex gap-1">
          <StatusButton onClick={() => onStatus("sent")} icon={<Send className="w-3 h-3" />} label="Envoyé" />
          <StatusButton onClick={() => onStatus("replied")} icon={<MessageSquare className="w-3 h-3" />} label="A répondu" />
          <StatusButton onClick={() => onStatus("converted")} icon={<Trophy className="w-3 h-3" />} label="Converti" />
          <StatusButton onClick={() => onStatus("ghosted")} icon={<Ghost className="w-3 h-3" />} label="Ghost" />
        </div>
      </div>
    </div>
  );
}

function StatusButton({ onClick, icon, label }: { onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className="px-2.5 py-1.5 text-xs border border-ink-200 rounded hover:bg-white flex items-center gap-1 text-ink-700"
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
