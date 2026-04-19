"use client";

import { CreditCard, Sparkles } from "lucide-react";
import { useI18n } from "@/i18n/provider";

export default function FacturationPage() {
  const { t, fc } = useI18n();
  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="shrink-0 w-12 h-12 rounded-md bg-navy-50 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-navy-500" />
            </div>
            <div>
              <div className="text-base font-semibold text-ink-900">{t("settings.bil_plan_name")}</div>
              <div className="text-xs text-ink-500 mt-0.5">
                {t("settings.bil_plan_desc")}
              </div>
              <div className="text-xs text-ink-400 mt-0.5">
                {t("settings.bil_plan_note")}
              </div>
            </div>
          </div>
          <button
            type="button"
            disabled
            className="px-4 py-2 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed"
            title={t("settings.priv_soon")}
          >
            {t("settings.bil_modify")}
          </button>
        </div>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-5">{t("settings.bil_payment")}</h3>
        <div className="flex items-center justify-between py-4 border border-ink-200 rounded-md px-4">
          <div className="flex items-center gap-3 text-sm text-ink-500">
            <CreditCard className="w-5 h-5 text-ink-400" />
            <span>{t("settings.bil_no_payment")}</span>
          </div>
          <button
            type="button"
            disabled
            className="px-4 py-1.5 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed"
          >
            {t("settings.bil_add")}
          </button>
        </div>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-2">{t("settings.bil_usage")}</h3>
        <p className="text-sm text-ink-600 mb-5 max-w-xl">
          {t("settings.bil_usage_intro")}
        </p>
        <div className="flex items-center justify-between py-4 border border-ink-200 rounded-md px-4">
          <div>
            <div className="text-sm font-mono text-ink-900">{fc(0)}</div>
            <div className="text-xs text-ink-500 mt-0.5">{t("settings.bil_balance")}</div>
          </div>
          <button
            type="button"
            disabled
            className="px-4 py-1.5 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed"
          >
            {t("settings.bil_buy")}
          </button>
        </div>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-5">{t("settings.bil_invoices")}</h3>
        <div className="py-8 text-center text-sm text-ink-500 border border-dashed border-ink-200 rounded-md">
          {t("settings.bil_no_invoices")}
        </div>
      </section>
    </div>
  );
}
