"use client";

import { useEffect, useState, useCallback } from "react";
import { MessageSquare, Send, Trash2, X } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import toast from "react-hot-toast";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface Comment {
  id: string;
  job_id: string;
  user_id: string;
  user_email: string | null;
  block_id: string | null;
  body: string;
  parent_id: string | null;
  resolved: boolean;
  created_at: string;
}

interface Props {
  jobId: string;
  /** Si présent, panneau ouvert par défaut */
  open?: boolean;
}

async function getToken() {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token || null;
}

/**
 * Panneau latéral droite (slide-in) avec tous les commentaires d'une analyse.
 * Permet le partage collaboratif : équipe M&A, comité d'investissement.
 */
export function CommentsPanel({ jobId, open: openInit = false }: Props) {
  const [open, setOpen] = useState(openInit);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(false);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/jobs/${jobId}/comments`);
      if (r.ok) {
        const j = await r.json();
        setComments(j.comments || []);
      }
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => {
      setCurrentUserId(data.user?.id || null);
    });
  }, []);

  async function send() {
    const text = body.trim();
    if (!text) return;
    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) {
        toast.error("Connectez-vous pour commenter");
        return;
      }
      const r = await fetch(`${API}/jobs/${jobId}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ body: text }),
      });
      if (!r.ok) throw new Error(await r.text());
      setBody("");
      load();
    } catch (e) {
      toast.error("Impossible d'envoyer le commentaire");
      console.warn(e);
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: string) {
    try {
      const token = await getToken();
      await fetch(`${API}/jobs/${jobId}/comments/${id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      load();
    } catch {
      toast.error("Suppression échouée");
    }
  }

  return (
    <>
      {/* FAB */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed right-4 bottom-4 z-40 inline-flex items-center gap-2 bg-navy-500 hover:bg-navy-600 text-white text-xs font-semibold px-3 py-2 rounded-full shadow-lg"
        title="Ouvrir les commentaires"
      >
        <MessageSquare className="w-3.5 h-3.5" />
        Discussion
        {comments.length > 0 && (
          <span className="bg-white text-navy-700 text-[10px] font-bold rounded-full w-5 h-5 inline-flex items-center justify-center">
            {comments.length}
          </span>
        )}
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 bg-ink-900/30 z-40"
            onClick={() => setOpen(false)}
          />
          <aside className="fixed right-0 top-0 h-screen w-96 bg-white border-l border-ink-200 z-50 flex flex-col shadow-2xl">
            <header className="flex items-center justify-between px-4 py-3 border-b border-ink-100">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
                  Discussion
                </div>
                <div className="text-sm font-semibold text-ink-900">
                  {comments.length} commentaire{comments.length > 1 ? "s" : ""}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-ink-500 hover:text-ink-900"
              >
                <X className="w-4 h-4" />
              </button>
            </header>

            {/* Liste */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {loading ? (
                <div className="text-xs text-ink-500 italic">Chargement…</div>
              ) : comments.length === 0 ? (
                <div className="text-xs text-ink-500 italic text-center py-8">
                  Aucun commentaire.<br />
                  Lancez la discussion ci-dessous.
                </div>
              ) : (
                comments.map((c) => {
                  const isOwn = currentUserId === c.user_id;
                  const initial = (c.user_email || "?")[0].toUpperCase();
                  return (
                    <div key={c.id} className="bg-ink-50 rounded-md p-3 group">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="w-6 h-6 rounded-full bg-navy-500 text-white text-xs font-bold flex items-center justify-center">
                          {initial}
                        </span>
                        <span className="text-xs font-semibold text-ink-800">
                          {(c.user_email || "user").split("@")[0]}
                        </span>
                        <span className="text-[10px] text-ink-500 ml-auto">
                          {new Date(c.created_at).toLocaleDateString("fr-FR", {
                            day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
                          })}
                        </span>
                        {isOwn && (
                          <button
                            type="button"
                            onClick={() => remove(c.id)}
                            className="opacity-0 group-hover:opacity-100 text-ink-400 hover:text-signal-sell transition-opacity"
                            title="Supprimer"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                      <div className="text-xs text-ink-700 whitespace-pre-wrap leading-relaxed">
                        {c.body}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Input */}
            <div className="border-t border-ink-100 p-3">
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") send();
                }}
                placeholder="Écrire un commentaire… (Cmd/Ctrl+Enter pour envoyer)"
                rows={3}
                className="w-full px-2 py-1.5 border border-ink-200 rounded text-xs resize-none focus:outline-none focus:border-navy-500"
              />
              <button
                type="button"
                onClick={send}
                disabled={submitting || !body.trim()}
                className="mt-2 w-full inline-flex items-center justify-center gap-2 bg-navy-500 hover:bg-navy-600 disabled:bg-ink-200 text-white text-xs font-semibold py-2 rounded transition-colors"
              >
                <Send className="w-3 h-3" />
                {submitting ? "Envoi…" : "Envoyer"}
              </button>
            </div>
          </aside>
        </>
      )}
    </>
  );
}
