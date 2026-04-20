"use client";

import { useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import toast from "react-hot-toast";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";
import { useI18n } from "@/i18n/provider";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function ComptePage() {
  const { t } = useI18n();
  const [user, setUser] = useState<User | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
  }, []);

  async function handleLogoutAll() {
    const supabase = createClient();
    await supabase.auth.signOut({ scope: "global" });
    window.location.href = "/";
  }

  function copyId() {
    if (!user?.id) return;
    navigator.clipboard.writeText(user.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleDelete() {
    if (confirmText !== "SUPPRIMER") {
      toast.error("Saisissez SUPPRIMER pour confirmer");
      return;
    }
    setDeleting(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) { toast.error("Session expirée"); return; }
      const r = await fetch(`${API}/user/delete-account`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) { toast.error("Échec suppression"); return; }
      toast.success("Compte supprimé");
      await supabase.auth.signOut({ scope: "global" });
      window.location.href = "/";
    } catch {
      toast.error("Erreur réseau");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <h2 className="text-lg font-semibold text-ink-900 mb-6">{t("settings.acc_title")}</h2>

        <div className="flex items-center justify-between py-4 border-b border-ink-100">
          <div>
            <div className="text-sm font-medium text-ink-900">{t("settings.acc_email")}</div>
            <div className="text-xs text-ink-500 mt-0.5">{user?.email || "—"}</div>
          </div>
        </div>

        <div className="flex items-center justify-between py-4 border-b border-ink-100">
          <div>
            <div className="text-sm font-medium text-ink-900">{t("settings.acc_logout_all_title")}</div>
            <div className="text-xs text-ink-500 mt-0.5">
              {t("settings.acc_logout_all_desc")}
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogoutAll}
            className="px-4 py-2 rounded-md border border-ink-300 text-sm text-ink-800 hover:bg-ink-50 transition-colors"
          >
            {t("settings.acc_logout_btn")}
          </button>
        </div>

        <div className="flex items-center justify-between py-4 border-b border-ink-100">
          <div>
            <div className="text-sm font-medium text-ink-900">{t("settings.acc_delete_title")}</div>
            <div className="text-xs text-ink-500 mt-0.5 max-w-xl">
              {t("settings.acc_delete_desc")}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            className="px-4 py-2 rounded-md border border-signal-sell text-signal-sell text-sm hover:bg-signal-sell hover:text-white transition-colors"
          >
            {t("settings.acc_delete_title")}
          </button>
        </div>

        <div className="flex items-center justify-between py-4">
          <div>
            <div className="text-sm font-medium text-ink-900">{t("settings.acc_userid")}</div>
            <div className="text-xs text-ink-500 mt-0.5">{t("settings.acc_userid_desc")}</div>
          </div>
          <button
            type="button"
            onClick={copyId}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ink-50 border border-ink-200 text-[11px] font-mono text-ink-700 hover:bg-ink-100 transition-colors"
          >
            <span className="truncate max-w-[220px]">{user?.id || "—"}</span>
            {copied ? <Check className="w-3.5 h-3.5 text-signal-buy" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </section>

      {confirmDelete && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => { setConfirmDelete(false); setConfirmText(""); }}>
          <div className="bg-white rounded-lg p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-ink-900 mb-2">{t("settings.acc_delete_modal_title")}</h3>
            <p className="text-sm text-ink-600 mb-4">
              Cette action est <strong>irréversible</strong>. Toutes vos analyses,
              documents, préférences et votre abonnement seront définitivement
              supprimés. Saisissez <code className="bg-ink-100 px-1 rounded">SUPPRIMER</code> pour confirmer.
            </p>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="SUPPRIMER"
              className="w-full px-3 py-2 rounded-md border border-ink-300 text-sm mb-4 focus:outline-none focus:border-signal-sell"
            />
            <div className="flex gap-2">
              <button
                onClick={() => { setConfirmDelete(false); setConfirmText(""); }}
                className="flex-1 py-2 rounded-md border border-ink-300 text-ink-700 text-sm hover:bg-ink-50"
                disabled={deleting}
              >
                Annuler
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting || confirmText !== "SUPPRIMER"}
                className="flex-1 py-2 rounded-md bg-signal-sell text-white text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? "Suppression…" : "Supprimer mon compte"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
