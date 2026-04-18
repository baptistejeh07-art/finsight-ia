"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "Comment FinSight calcule-t-il un DCF ?",
  "Quelles sociétés puis-je analyser ?",
  "Quelle est la différence entre les plans ?",
  "Comment est garantie la fiabilité des chiffres ?",
];

export function AnalysteChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollerRef.current?.scrollTo({
      top: scrollerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || loading) return;
    const next: Message[] = [...messages, { role: "user", content: t }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/qa-vitrine", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: next }),
      });
      if (!res.ok) throw new Error("Réponse invalide");
      const json = await res.json();
      const reply: string =
        json?.reply ||
        "Je n'ai pas pu obtenir de réponse. Réessayez dans un instant.";
      setMessages([...next, { role: "assistant", content: reply }]);
    } catch {
      setMessages([
        ...next,
        {
          role: "assistant",
          content:
            "Désolé, le service de réponse est momentanément indisponible. Réessayez dans quelques instants.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card-vitrine !p-0 overflow-hidden">
      <div
        ref={scrollerRef}
        className="min-h-[260px] max-h-[440px] overflow-y-auto p-6 space-y-4"
      >
        {messages.length === 0 && (
          <div>
            <p className="text-sm text-text-muted mb-4">
              Quelques pistes pour démarrer :
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs px-3 py-1.5 rounded-full border border-border-default text-text-secondary hover:border-accent-primary hover:text-accent-primary transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "flex justify-end"
                : "flex justify-start"
            }
          >
            <div
              className={
                m.role === "user"
                  ? "max-w-[80%] px-4 py-2.5 rounded-lg bg-accent-primary text-accent-primary-fg text-sm leading-relaxed"
                  : "max-w-[85%] px-4 py-2.5 rounded-lg bg-surface-muted text-text-primary text-sm leading-relaxed whitespace-pre-wrap"
              }
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="px-4 py-2.5 rounded-lg bg-surface-muted text-text-muted text-sm flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              FinSight réfléchit…
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="border-t border-border-default p-3 flex items-center gap-2 bg-surface"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Posez votre question…"
          disabled={loading}
          className="flex-1 px-3 py-2 bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="btn-cta !py-2 !px-3 disabled:opacity-40"
          aria-label="Envoyer"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}
