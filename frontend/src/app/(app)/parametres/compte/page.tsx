"use client";

import { useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";

export default function ComptePage() {
  const [user, setUser] = useState<User | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

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

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <h2 className="text-lg font-semibold text-ink-900 mb-6">Compte</h2>

        {/* Email */}
        <div className="flex items-center justify-between py-4 border-b border-ink-100">
          <div>
            <div className="text-sm font-medium text-ink-900">Adresse e-mail</div>
            <div className="text-xs text-ink-500 mt-0.5">{user?.email || "—"}</div>
          </div>
        </div>

        {/* Déconnexion tous appareils */}
        <div className="flex items-center justify-between py-4 border-b border-ink-100">
          <div>
            <div className="text-sm font-medium text-ink-900">Se déconnecter de tous les appareils</div>
            <div className="text-xs text-ink-500 mt-0.5">
              Invalide les sessions sur tous les navigateurs où vous êtes connecté.
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogoutAll}
            className="px-4 py-2 rounded-md border border-ink-300 text-sm text-ink-800 hover:bg-ink-50 transition-colors"
          >
            Se déconnecter
          </button>
        </div>

        {/* Suppression */}
        <div className="flex items-center justify-between py-4 border-b border-ink-100">
          <div>
            <div className="text-sm font-medium text-ink-900">Supprimer le compte</div>
            <div className="text-xs text-ink-500 mt-0.5 max-w-xl">
              Pour supprimer votre compte, veuillez d&apos;abord annuler votre
              abonnement si vous en avez un. Cette action est irréversible.
            </div>
          </div>
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            disabled
            className="px-4 py-2 rounded-md bg-ink-300 text-white text-sm cursor-not-allowed"
            title="Bientôt disponible"
          >
            Supprimer le compte
          </button>
        </div>

        {/* User ID */}
        <div className="flex items-center justify-between py-4">
          <div>
            <div className="text-sm font-medium text-ink-900">ID utilisateur</div>
            <div className="text-xs text-ink-500 mt-0.5">Identifiant interne FinSight.</div>
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
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setConfirmDelete(false)}>
          <div className="bg-white rounded-lg p-6 max-w-md" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-ink-900 mb-2">Suppression non disponible</h3>
            <p className="text-sm text-ink-600 mb-4">
              La suppression automatique n&apos;est pas encore branchée. Envoyez-nous un e-mail
              pour faire supprimer votre compte manuellement.
            </p>
            <button
              onClick={() => setConfirmDelete(false)}
              className="w-full py-2 rounded-md bg-navy-500 text-white hover:bg-navy-600 transition-colors"
            >
              OK
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
