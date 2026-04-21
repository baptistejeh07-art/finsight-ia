"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X, Search, Linkedin, MessageCircle, Users, Newspaper, Mic, Sparkles, ArrowRight } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface AttributionSource {
  key: string;
  label: string;
  icon: React.ReactNode;
}

const SOURCES: AttributionSource[] = [
  { key: "google",   label: "Recherche Google",            icon: <Search className="w-4 h-4" /> },
  { key: "linkedin", label: "LinkedIn",                    icon: <Linkedin className="w-4 h-4" /> },
  { key: "reddit",   label: "Reddit",                      icon: <MessageCircle className="w-4 h-4" /> },
  { key: "friend",   label: "Bouche-à-oreille",            icon: <Users className="w-4 h-4" /> },
  { key: "press",    label: "Presse / médias",             icon: <Newspaper className="w-4 h-4" /> },
  { key: "podcast",  label: "Podcast",                     icon: <Mic className="w-4 h-4" /> },
  { key: "x",        label: "X (Twitter)",                 icon: <Sparkles className="w-4 h-4" /> },
  { key: "other",    label: "Autre",                       icon: <Sparkles className="w-4 h-4" /> },
];

interface Props {
  /** Quel plan a déclenché le pop-up (decouverte/essentiel/pro/equipe/enterprise/api) */
  planClicked: string;
  /** URL de redirection à exécuter après confirmation */
  ctaHref: string;
  /** Callback close (sans réponse) — l'utilisateur peut quitter sans répondre */
  onClose: () => void;
}

/**
 * Modal "Comment avez-vous entendu parler de FinSight ?" — affichée AVANT
 * la redirection vers /app ou /contact. Stocke la réponse dans Supabase
 * pour mesurer le ROI par canal d'acquisition.
 *
 * L'utilisateur peut skip — on stocke alors source="skipped".
 */
export function AttributionModal({ planClicked, ctaHref, onClose }: Props) {
  const router = useRouter();
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  async function send(source: string, source_detail?: string) {
    setSubmitting(true);
    try {
      let sid: string | null = null;
      try { sid = localStorage.getItem("finsight-anon-sid"); } catch {}
      const referrer = typeof document !== "undefined" ? document.referrer : null;
      await fetch(`${API}/analytics/signup-attribution`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          source,
          source_detail: source_detail || null,
          plan_clicked: planClicked,
          anon_session_id: sid,
          referrer,
        }),
        keepalive: true,
      }).catch(() => {});
      // Mémorise la source pour ne pas re-demander
      try {
        localStorage.setItem("finsight-attribution-source", source);
      } catch {}
    } finally {
      setSubmitting(false);
      onClose();
      // Redirection finale (interne /app ou /contact)
      if (ctaHref.startsWith("http")) {
        window.location.href = ctaHref;
      } else {
        router.push(ctaHref);
      }
    }
  }

  function handleSubmit() {
    if (!selected) return;
    send(selected, detail.trim() || undefined);
  }

  function handleSkip() {
    send("skipped");
  }

  return (
    <div
      className="fixed inset-0 z-[100] bg-ink-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-surface-elevated border border-border-default rounded-lg shadow-xl max-w-md w-full overflow-hidden animate-slide-up"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-border-default flex items-start justify-between">
          <div>
            <h3 className="font-serif text-lg font-bold text-text-primary">
              Comment nous avez-vous découverts ?
            </h3>
            <p className="text-xs text-text-muted mt-1">
              Une seconde — ça nous aide à mesurer ce qui fonctionne.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors -m-2 p-2"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sources grid */}
        <div className="p-5 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {SOURCES.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setSelected(s.key)}
                className={
                  "flex items-center gap-2 px-3 py-2.5 rounded-md border text-sm font-medium transition-all " +
                  (selected === s.key
                    ? "bg-accent-primary/10 border-accent-primary text-accent-primary"
                    : "bg-surface border-border-default text-text-secondary hover:border-text-muted hover:text-text-primary")
                }
              >
                {s.icon}
                <span>{s.label}</span>
              </button>
            ))}
          </div>

          {/* Optionnel : détail */}
          {selected && selected !== "skipped" && (
            <div>
              <label className="text-xs text-text-muted block mb-1.5">
                Précisez si vous voulez (optionnel)
              </label>
              <input
                type="text"
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                placeholder={
                  selected === "podcast" ? "Ex: GDIY, Tonton & Tata, etc."
                  : selected === "press" ? "Ex: L'Usine Digitale, Les Echos…"
                  : selected === "friend" ? "Ex: collègue analyste, étudiant école finance…"
                  : "Ex: hashtag, post, événement…"
                }
                className="w-full px-3 py-2 border border-border-default rounded-md text-sm bg-surface focus:outline-none focus:border-accent-primary"
                maxLength={200}
              />
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="px-5 pb-5 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={handleSkip}
            disabled={submitting}
            className="text-xs text-text-muted hover:text-text-secondary transition-colors"
          >
            Passer
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!selected || submitting}
            className="inline-flex items-center gap-2 btn-cta disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "…" : "Continuer"}
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
