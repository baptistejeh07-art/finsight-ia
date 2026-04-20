"use client";

import { useState, useEffect } from "react";
import { X, Linkedin, Mail, Copy, Check, Trash2, Link2 } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface ShareModalProps {
  open: boolean;
  onClose: () => void;
  historyId: string | null;
  analysisLabel: string;
}

export function ShareModal({ open, onClose, historyId, analysisLabel }: ShareModalProps) {
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) {
      setShareUrl(null);
      setToken(null);
      setCopied(false);
    }
  }, [open]);

  async function createShare() {
    if (!historyId) {
      toast.error("Cette analyse doit être enregistrée dans l'historique avant d'être partagée.");
      return;
    }
    setCreating(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const tok = data.session?.access_token;
      if (!tok) { toast.error("Connectez-vous d'abord"); return; }

      const r = await fetch(`${API}/share/create`, {
        method: "POST",
        headers: { Authorization: `Bearer ${tok}`, "Content-Type": "application/json" },
        body: JSON.stringify({ history_id: historyId }),
      });
      const j = await r.json();
      if (!r.ok) { toast.error(j.detail || "Échec création"); return; }
      const url = `${window.location.origin}/share/${j.token}`;
      setToken(j.token);
      setShareUrl(url);
    } catch {
      toast.error("Erreur réseau");
    } finally {
      setCreating(false);
    }
  }

  async function revokeShare() {
    if (!token) return;
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const tok = data.session?.access_token;
      if (!tok) return;
      await fetch(`${API}/share/${token}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${tok}` },
      });
      setShareUrl(null);
      setToken(null);
      toast.success("Lien révoqué");
    } catch {
      toast.error("Erreur révocation");
    }
  }

  async function copyUrl() {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    toast.success("URL copiée");
    setTimeout(() => setCopied(false), 2000);
  }

  if (!open) return null;

  const text = encodeURIComponent(
    `Analyse FinSight : ${analysisLabel} — DCF, ratios, scénarios. Vu sur FinSight IA.`,
  );
  const url = encodeURIComponent(shareUrl || "");

  const shareTargets = shareUrl ? [
    {
      name: "LinkedIn",
      icon: Linkedin,
      color: "bg-[#0a66c2] text-white",
      url: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`,
    },
    {
      name: "Reddit",
      icon: RedditIcon,
      color: "bg-[#ff4500] text-white",
      url: `https://www.reddit.com/submit?url=${url}&title=${text}`,
    },
    {
      name: "Facebook",
      icon: FacebookIcon,
      color: "bg-[#1877f2] text-white",
      url: `https://www.facebook.com/sharer/sharer.php?u=${url}`,
    },
    {
      name: "Gmail",
      icon: Mail,
      color: "bg-[#ea4335] text-white",
      url: `https://mail.google.com/mail/?view=cm&fs=1&su=${text}&body=${text}%20%0A%0A${url}`,
    },
  ] : [];

  return (
    <div className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white dark:bg-ink-900 rounded-lg shadow-2xl w-full max-w-md overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
          <div className="flex items-center gap-2">
            <Link2 className="w-4 h-4 text-accent-primary" />
            <h2 className="font-semibold text-text-primary">Partager l&apos;analyse</h2>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5">
          {!shareUrl ? (
            <>
              <p className="text-sm text-text-secondary mb-5">
                Génère un lien public en lecture seule pour <strong>{analysisLabel}</strong>. Toute personne avec
                le lien pourra consulter l&apos;analyse, sans pouvoir la modifier ni voir votre compte.
              </p>
              <button
                onClick={createShare}
                disabled={creating}
                className="w-full py-2.5 rounded-md bg-accent-primary text-accent-primary-fg font-semibold text-sm hover:opacity-90 disabled:opacity-50"
              >
                {creating ? "Génération…" : "Créer un lien public"}
              </button>
            </>
          ) : (
            <>
              <label className="block text-2xs uppercase tracking-widest text-text-muted font-semibold mb-2">
                Lien public
              </label>
              <div className="flex gap-2 mb-5">
                <input
                  readOnly
                  value={shareUrl}
                  className="flex-1 px-3 py-2 border border-border-default rounded-md text-xs font-mono bg-surface-muted truncate"
                />
                <button
                  onClick={copyUrl}
                  className="shrink-0 px-3 py-2 rounded-md border border-border-default hover:bg-surface-muted"
                  title="Copier"
                >
                  {copied ? <Check className="w-4 h-4 text-signal-buy" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-4">
                {shareTargets.map((t) => {
                  const Icon = t.icon;
                  return (
                    <a
                      key={t.name}
                      href={t.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`flex items-center justify-center gap-2 py-2.5 rounded-md text-sm font-semibold transition-opacity hover:opacity-90 ${t.color}`}
                    >
                      <Icon className="w-4 h-4" /> {t.name}
                    </a>
                  );
                })}
              </div>

              <button
                onClick={revokeShare}
                className="w-full flex items-center justify-center gap-1.5 py-2 text-xs text-signal-sell hover:bg-red-50 rounded-md"
              >
                <Trash2 className="w-3 h-3" /> Révoquer ce lien
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function RedditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5.5 11.16c.04.21.06.43.06.65 0 2.32-2.7 4.2-6.04 4.2s-6.04-1.88-6.04-4.2c0-.22.02-.44.06-.65a1.5 1.5 0 1 1 1.91-2.05c1.04-.7 2.46-1.15 4.04-1.21l.85-3.99 2.78.59a1.05 1.05 0 1 1-.04.4l-2.49-.53-.74 3.51c1.59.06 3.03.51 4.07 1.23a1.5 1.5 0 1 1 1.58 2.05zM8.5 13.5a1 1 0 1 1 2 0 1 1 0 0 1-2 0zm5 0a1 1 0 1 1 2 0 1 1 0 0 1-2 0zm.27 2.45c-.4.4-1.13.43-1.77.43s-1.37-.03-1.77-.43a.4.4 0 0 1 .57-.57c.13.13.55.16 1.2.16s1.07-.03 1.2-.16a.4.4 0 1 1 .57.57z" />
    </svg>
  );
}

function FacebookIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  );
}
