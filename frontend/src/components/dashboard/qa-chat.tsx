"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User as UserIcon, Loader2 } from "lucide-react";
import { askQA } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function QAChat({ jobId, ticker }: { jobId: string; ticker: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  // Auto-resize du textarea selon le contenu
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const max = 220; // px max (~10 lignes)
    ta.style.height = `${Math.min(ta.scrollHeight, max)}px`;
    ta.style.overflowY = ta.scrollHeight > max ? "auto" : "hidden";
  }, [input]);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    const next: Message[] = [...messages, { role: "user", content: q }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      const data = await askQA(jobId, next);
      setMessages((m) => [...m, { role: "assistant", content: data.answer || "—" }]);
    } catch (e) {
      console.error(e);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Erreur de connexion au modèle. Réessayez dans un instant." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md flex flex-col">
      <div className="px-5 pt-4 pb-2 border-b border-ink-100">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Avez-vous des questions au sujet de l&apos;analyse ?
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 px-5 py-3 max-h-[420px] min-h-[120px] overflow-y-auto space-y-3">
        {messages.length === 0 && (
          <div className="text-xs text-ink-400 italic text-center py-3">
            Posez vos questions à l&apos;IA — elle a tout le contexte de l&apos;analyse {ticker}.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className="flex gap-2">
            <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${m.role === "user" ? "bg-ink-100" : "bg-navy-500"}`}>
              {m.role === "user" ? (
                <UserIcon className="w-3.5 h-3.5 text-ink-700" />
              ) : (
                <Bot className="w-3.5 h-3.5 text-white" />
              )}
            </div>
            <div className="text-xs text-ink-800 leading-relaxed whitespace-pre-wrap pt-0.5">
              {m.content}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex gap-2">
            <div className="shrink-0 w-6 h-6 rounded-full bg-navy-500 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-white" />
            </div>
            <Loader2 className="w-4 h-4 text-ink-400 animate-spin mt-1" />
          </div>
        )}
      </div>

      <div className="border-t border-ink-100 p-3">
        {/* Boîte input style Claude.ai : textarea auto-grow + bouton en bas */}
        <div className="border border-ink-200 rounded-lg bg-white focus-within:border-navy-500 focus-within:ring-1 focus-within:ring-navy-500/20 transition-colors">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Pourquoi la conviction est-elle de tant ? · Quels sont les risques principaux ?"
            disabled={busy}
            rows={1}
            className="w-full px-3 pt-2.5 pb-1 bg-transparent text-sm text-ink-900 placeholder:text-ink-400 resize-none focus:outline-none disabled:opacity-50"
            style={{ overflowY: "hidden" }}
          />
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-2xs text-ink-400">
              <span className="hidden sm:inline">Entrée pour envoyer · Shift+Entrée pour aller à la ligne</span>
            </span>
            <button
              onClick={send}
              disabled={busy || !input.trim()}
              className="w-8 h-8 rounded-md bg-navy-500 text-white hover:bg-navy-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center"
              aria-label="Envoyer"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
