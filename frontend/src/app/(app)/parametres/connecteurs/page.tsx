"use client";

import { Building2, FileSpreadsheet, Database, Plus } from "lucide-react";
import { useI18n } from "@/i18n/provider";

export default function ConnecteursPage() {
  const { t } = useI18n();
  const CONNECTEURS = [
    {
      id: "pennylane",
      name: "Pennylane",
      description: t("settings.conn_pennylane_desc"),
      icon: Building2,
    },
    {
      id: "sage",
      name: "Sage",
      description: t("settings.conn_sage_desc"),
      icon: FileSpreadsheet,
    },
    {
      id: "fec",
      name: "FEC",
      description: t("settings.conn_fec_desc"),
      icon: Database,
    },
  ];
  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <h2 className="text-lg font-semibold text-ink-900 mb-2">{t("settings.conn_title")}</h2>
        <p className="text-sm text-ink-600 mb-6 max-w-xl">
          {t("settings.conn_intro")}
        </p>

        <div className="space-y-3">
          {CONNECTEURS.map((c) => {
            const Icon = c.icon;
            return (
              <div
                key={c.id}
                className="flex items-start gap-4 p-4 border border-ink-200 rounded-md bg-white hover:border-ink-300 transition-colors"
              >
                <div className="shrink-0 w-10 h-10 rounded-md bg-ink-50 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-ink-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-ink-900">{c.name}</span>
                    <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                      {t("settings.conn_badge_soon")}
                    </span>
                  </div>
                  <p className="text-xs text-ink-500 leading-relaxed">{c.description}</p>
                </div>
                <button
                  type="button"
                  disabled
                  className="px-4 py-2 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed shrink-0"
                >
                  {t("settings.conn_btn_connect")}
                </button>
              </div>
            );
          })}
        </div>

        <button
          type="button"
          disabled
          className="mt-4 flex items-center gap-2 px-4 py-2 rounded-md border border-dashed border-ink-300 text-sm text-ink-500 cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
          {t("settings.conn_btn_add")}
        </button>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-2">
          {t("settings.conn_why_title")}
        </h3>
        <p className="text-sm text-ink-600 leading-relaxed max-w-2xl">
          {t("settings.conn_why_desc")}
        </p>
      </section>
    </div>
  );
}
