"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Star, Plus, Trash2, X, ListPlus, ChevronDown, ChevronRight } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";
import { BackButton } from "@/components/back-button";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface WLTicker {
  id: number;
  ticker: string;
  company_name: string | null;
  position: number;
}

interface Watchlist {
  id: string;
  name: string;
  description: string | null;
  color: string;
  created_at: string;
  updated_at: string;
  watchlist_tickers: WLTicker[];
}

async function getToken(): Promise<string | null> {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token || null;
}

async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = await getToken();
  const r = await fetch(`${API}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok && r.status !== 204) {
    const err = await r.text();
    throw new Error(err || `HTTP ${r.status}`);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export default function WatchlistsPage() {
  const [wls, setWls] = useState<Watchlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const j = await api<{ watchlists: Watchlist[] }>("GET", "/watchlists");
      setWls(j.watchlists || []);
    } catch (e) {
      console.warn(e);
      toast.error("Impossible de charger les watchlists");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createWl() {
    if (!newName.trim()) return;
    try {
      await api("POST", "/watchlists", { name: newName.trim(), description: newDesc.trim() || null });
      toast.success("Watchlist créée");
      setNewName(""); setNewDesc(""); setShowCreate(false);
      load();
    } catch (e) {
      toast.error("Création échouée");
      console.warn(e);
    }
  }

  async function deleteWl(id: string) {
    if (!confirm("Supprimer cette watchlist et tous ses tickers ?")) return;
    try {
      await api("DELETE", `/watchlists/${id}`);
      toast.success("Watchlist supprimée");
      load();
    } catch (e) {
      toast.error("Échec suppression");
      console.warn(e);
    }
  }

  return (
    <div className="min-h-screen bg-ink-50/30">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <BackButton fallback="/app" />

        <header className="flex items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-1">
              <Star className="w-3 h-3" />
              Watchlists
            </div>
            <h1 className="text-2xl font-bold text-ink-900">Mes listes de suivi</h1>
            <p className="text-sm text-ink-600 mt-1">
              Regroupez les tickers par thématique pour les analyser en lot ou
              recevoir des alertes ciblées.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate((v) => !v)}
            className="inline-flex items-center gap-2 bg-navy-500 hover:bg-navy-600 text-white text-sm font-semibold px-3 py-2 rounded-md transition-colors"
          >
            <Plus className="w-4 h-4" /> Nouvelle watchlist
          </button>
        </header>

        {showCreate && (
          <div className="bg-white border border-ink-200 rounded-md p-4 space-y-3">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Nom (ex: Luxe européen, Cloud US, Banques FR…)"
              className="w-full px-3 py-2 border border-ink-200 rounded text-sm focus:outline-none focus:border-navy-500"
              autoFocus
            />
            <input
              type="text"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description (optionnel)"
              className="w-full px-3 py-2 border border-ink-200 rounded text-sm focus:outline-none focus:border-navy-500"
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="text-sm text-ink-600 hover:text-ink-900 px-3 py-2"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={createWl}
                disabled={!newName.trim()}
                className="text-sm font-semibold bg-navy-500 hover:bg-navy-600 disabled:bg-ink-200 disabled:text-ink-500 text-white px-4 py-2 rounded transition-colors"
              >
                Créer
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="text-sm text-ink-500 italic">Chargement…</div>
        ) : wls.length === 0 ? (
          <div className="bg-white border border-ink-200 rounded-md p-8 text-center">
            <Star className="w-8 h-8 text-ink-300 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-ink-800 mb-1">
              Aucune watchlist pour l&apos;instant
            </h3>
            <p className="text-sm text-ink-500 max-w-md mx-auto">
              Créez une liste pour grouper vos tickers favoris par thématique
              (sectoriel, géographique, conviction…).
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {wls.map((wl) => (
              <WatchlistCard
                key={wl.id}
                wl={wl}
                expanded={expandedId === wl.id}
                onToggle={() => setExpandedId(expandedId === wl.id ? null : wl.id)}
                onDelete={() => deleteWl(wl.id)}
                onChange={load}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function WatchlistCard({
  wl, expanded, onToggle, onDelete, onChange,
}: {
  wl: Watchlist;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onChange: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [newTicker, setNewTicker] = useState("");

  async function addTicker() {
    const tk = newTicker.trim().toUpperCase();
    if (!tk) return;
    try {
      await api("POST", `/watchlists/${wl.id}/tickers`, { ticker: tk });
      toast.success(`${tk} ajouté`);
      setNewTicker("");
      setAdding(false);
      onChange();
    } catch (e) {
      const msg = (e as Error).message || "";
      if (msg.includes("409") || msg.includes("déjà")) {
        toast.error("Ticker déjà dans cette watchlist");
      } else {
        toast.error("Ajout échoué");
      }
    }
  }

  async function removeTicker(t: string) {
    try {
      await api("DELETE", `/watchlists/${wl.id}/tickers/${t}`);
      toast.success(`${t} retiré`);
      onChange();
    } catch {
      toast.error("Suppression échouée");
    }
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3">
        <button
          type="button"
          onClick={onToggle}
          className="flex items-center gap-2 text-left flex-1"
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-ink-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-ink-500" />
          )}
          <div>
            <div className="text-sm font-semibold text-ink-900">{wl.name}</div>
            {wl.description && (
              <div className="text-xs text-ink-500 mt-0.5">{wl.description}</div>
            )}
          </div>
          <span className="ml-3 text-[10px] uppercase tracking-wider bg-ink-100 text-ink-600 rounded px-2 py-0.5">
            {wl.watchlist_tickers?.length || 0} ticker{(wl.watchlist_tickers?.length || 0) > 1 ? "s" : ""}
          </span>
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="p-1.5 text-ink-400 hover:text-signal-sell rounded transition-colors"
          title="Supprimer la watchlist"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-ink-100 p-4 space-y-3">
          {(wl.watchlist_tickers || []).length === 0 ? (
            <p className="text-xs text-ink-500 italic">
              Aucun ticker dans cette watchlist.
            </p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {wl.watchlist_tickers.map((t) => (
                <div
                  key={t.id}
                  className="group flex items-center justify-between bg-ink-50 border border-ink-100 rounded px-2.5 py-1.5"
                >
                  <Link
                    href={`/analyse?q=${encodeURIComponent(t.ticker)}`}
                    className="text-xs font-mono font-semibold text-ink-900 hover:text-navy-600"
                    title="Analyser"
                  >
                    {t.ticker}
                  </Link>
                  <button
                    type="button"
                    onClick={() => removeTicker(t.ticker)}
                    className="opacity-0 group-hover:opacity-100 text-ink-400 hover:text-signal-sell transition-opacity"
                    title="Retirer"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Ajouter un ticker */}
          {adding ? (
            <div className="flex gap-2">
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addTicker();
                  if (e.key === "Escape") setAdding(false);
                }}
                placeholder="Ticker (ex: AAPL, MC.PA…)"
                autoFocus
                className="flex-1 px-3 py-1.5 border border-ink-200 rounded text-xs font-mono uppercase focus:outline-none focus:border-navy-500"
              />
              <button
                type="button"
                onClick={addTicker}
                className="text-xs font-semibold bg-navy-500 hover:bg-navy-600 text-white px-3 py-1.5 rounded transition-colors"
              >
                Ajouter
              </button>
              <button
                type="button"
                onClick={() => { setAdding(false); setNewTicker(""); }}
                className="text-xs text-ink-500 hover:text-ink-900 px-2"
              >
                Annuler
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="inline-flex items-center gap-1.5 text-xs text-navy-500 hover:text-navy-700 font-semibold"
            >
              <ListPlus className="w-3.5 h-3.5" />
              Ajouter un ticker
            </button>
          )}
        </div>
      )}
    </div>
  );
}
