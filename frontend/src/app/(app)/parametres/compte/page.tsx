"use client";

import { useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";
import { useI18n } from "@/i18n/provider";

export default function ComptePage() {
  const { t } = useI18n();
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
            disabled
            className="px-4 py-2 rounded-md bg-ink-300 text-white text-sm cursor-not-allowed"
            title={t("settings.priv_soon")}
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
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setConfirmDelete(false)}>
          <div className="bg-white rounded-lg p-6 max-w-md" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-ink-900 mb-2">{t("settings.acc_delete_modal_title")}</h3>
            <p className="text-sm text-ink-600 mb-4">
              {t("settings.acc_delete_modal_desc")}
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
