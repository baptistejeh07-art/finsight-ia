"use client";

import { useI18n } from "@/i18n/provider";

export default function UtilisationPage() {
  const { t } = useI18n();
  const reset = t("settings.use_reset_in_days").replace("{days}", "22");
  const usage = [
    { label: t("settings.use_label_societe"), used: 4, total: 10, reset },
    { label: t("settings.use_label_secteur"), used: 1, total: 5, reset },
    { label: t("settings.use_label_indice"), used: 0, total: 2, reset },
    { label: t("settings.use_label_portrait"), used: 2, total: 5, reset },
  ];

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-ink-900">{t("settings.use_title")}</h2>
          <span className="text-xs text-ink-500">{t("settings.bil_plan_name")}</span>
        </div>
        <p className="text-sm text-ink-600 mb-6">
          {t("settings.use_intro")}
        </p>

        <div className="space-y-5">
          {usage.map((u) => {
            const pct = u.total > 0 ? Math.min((u.used / u.total) * 100, 100) : 0;
            return (
              <div key={u.label}>
                <div className="flex items-baseline justify-between mb-1">
                  <div>
                    <div className="text-sm text-ink-900">{u.label}</div>
                    <div className="text-[11px] text-ink-500">{u.reset}</div>
                  </div>
                  <div className="text-xs text-ink-600 font-mono">
                    {u.used} / {u.total}
                  </div>
                </div>
                <div className="h-1.5 w-full bg-ink-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-navy-500 rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-2">{t("settings.use_history")}</h3>
        <p className="text-sm text-ink-600">
          {t("settings.use_history_intro")}
        </p>
        <div className="mt-4 py-12 text-center text-sm text-ink-400 border border-dashed border-ink-200 rounded-md">
          {t("settings.use_chart_soon")}
        </div>
      </section>
    </div>
  );
}
