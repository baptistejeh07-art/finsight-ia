"use client";

import { useState } from "react";
import { Send, CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export function ContactForm() {
  const [form, setForm] = useState({
    name: "", email: "", subject: "", message: "", honeypot: "",
  });
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.email || !form.message || form.message.length < 10) {
      toast.error("Complétez tous les champs (message ≥10 caractères)");
      return;
    }
    setSending(true);
    try {
      const r = await fetch(`${API}/contact/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (r.ok || r.status === 204) {
        setSent(true);
        toast.success("Message envoyé — réponse sous 48h");
      } else if (r.status === 429) {
        toast.error("Trop de messages envoyés. Réessayez dans quelques minutes.");
      } else {
        const err = await r.text();
        toast.error("Envoi échoué : " + err.slice(0, 100));
      }
    } catch {
      toast.error("Erreur réseau, réessayez");
    } finally {
      setSending(false);
    }
  }

  if (sent) {
    return (
      <div className="bg-emerald-50 border border-emerald-200 rounded-md p-6 text-center">
        <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
        <div className="text-sm font-semibold text-emerald-800">Message envoyé</div>
        <div className="text-xs text-emerald-700 mt-1">
          Nous revenons vers vous sous 48h en jour ouvré.
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <input
          type="text"
          required
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Votre nom"
          className="px-3 py-2 border border-ink-200 rounded text-sm focus:outline-none focus:border-navy-500"
          maxLength={120}
        />
        <input
          type="email"
          required
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="Votre email"
          className="px-3 py-2 border border-ink-200 rounded text-sm focus:outline-none focus:border-navy-500"
          maxLength={200}
        />
      </div>
      <input
        type="text"
        required
        value={form.subject}
        onChange={(e) => setForm({ ...form, subject: e.target.value })}
        placeholder="Sujet"
        className="w-full px-3 py-2 border border-ink-200 rounded text-sm focus:outline-none focus:border-navy-500"
        maxLength={200}
      />
      <textarea
        required
        value={form.message}
        onChange={(e) => setForm({ ...form, message: e.target.value })}
        placeholder="Votre message…"
        rows={5}
        minLength={10}
        maxLength={5000}
        className="w-full px-3 py-2 border border-ink-200 rounded text-sm focus:outline-none focus:border-navy-500 resize-y"
      />
      {/* Honeypot anti-spam — caché via CSS, bots remplissent quand même */}
      <input
        type="text"
        tabIndex={-1}
        autoComplete="off"
        value={form.honeypot}
        onChange={(e) => setForm({ ...form, honeypot: e.target.value })}
        style={{ position: "absolute", left: "-9999px" }}
        aria-hidden="true"
      />
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] text-ink-500">
          Nous répondons sous 48h. Aucune donnée partagée à des tiers.
        </p>
        <button
          type="submit"
          disabled={sending}
          className="inline-flex items-center gap-2 bg-navy-500 hover:bg-navy-600 disabled:bg-ink-300 text-white text-sm font-semibold px-4 py-2 rounded transition-colors"
        >
          <Send className="w-3.5 h-3.5" />
          {sending ? "Envoi…" : "Envoyer"}
        </button>
      </div>
    </form>
  );
}
