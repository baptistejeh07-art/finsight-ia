"use client";

import Link from "next/link";
import { Shield } from "lucide-react";
import { useUserPreferences } from "@/hooks/use-user-preferences";
import { useI18n } from "@/i18n/provider";

export default function ConfidentialitePage() {
  const { prefs, update, loading } = useUserPreferences();
  const { t } = useI18n();

  if (loading) return <div className="text-sm text-ink-500">{t("common.loading")}</div>;

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-start gap-3 mb-4">
          <div className="shrink-0 w-10 h-10 rounded-md bg-ink-100 flex items-center justify-center">
            <Shield className="w-5 h-5 text-ink-700" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-ink-900">{t("settings.priv_title")}</h2>
            <p className="text-sm text-ink-600">
              {t("settings.priv_intro")}
            </p>
          </div>
        </div>

        <p className="text-sm text-ink-700 leading-relaxed">
          {t("settings.priv_discover")}{" "}
          <Link href="/privacy" className="text-navy-500 underline">
            {t("settings.priv_policy")}
          </Link>{" "}
          {t("settings.priv_and_our")}{" "}
          <Link href="/securite" className="text-navy-500 underline">
            {t("settings.priv_security")}
          </Link>{" "}
          {t("settings.priv_more_details")}
        </p>

        <div className="mt-5 space-y-2">
          <Link href="/privacy" className="block text-sm text-ink-700 hover:text-navy-500">
            {t("settings.priv_how_protect")}
          </Link>
          <Link href="/privacy" className="block text-sm text-ink-700 hover:text-navy-500">
            {t("settings.priv_how_use")}
          </Link>
        </div>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-5">{t("settings.priv_settings_title")}</h3>

        <ActionRow
          title={t("settings.priv_export_title")}
          description={t("settings.priv_export_desc")}
          buttonLabel={t("settings.priv_export_btn")}
          soon={t("settings.priv_soon")}
          disabled
        />
        <ActionRow
          title={t("settings.priv_memory_title")}
          description={t("settings.priv_memory_desc")}
          buttonLabel={t("settings.priv_memory_btn")}
          soon={t("settings.priv_soon")}
          disabled
        />

        <ToggleRow
          title={t("settings.priv_location_title")}
          description={t("settings.priv_location_desc")}
          value={prefs.privacy.location_metadata}
          onChange={(v) => update({ privacy: { ...prefs.privacy, location_metadata: v } })}
        />
        <ToggleRow
          title={t("settings.priv_improve_title")}
          description={t("settings.priv_improve_desc")}
          value={prefs.privacy.improve_models}
          onChange={(v) => update({ privacy: { ...prefs.privacy, improve_models: v } })}
        />
      </section>
    </div>
  );
}

function ToggleRow({
  title,
  description,
  value,
  onChange,
}: {
  title: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-4 border-b border-ink-100 last:border-b-0">
      <div className="flex-1">
        <div className="text-sm font-medium text-ink-900">{title}</div>
        <div className="text-xs text-ink-500 mt-0.5 leading-relaxed max-w-xl">{description}</div>
      </div>
      <button
        type="button"
        onClick={() => onChange(!value)}
        role="switch"
        aria-checked={value}
        className={
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors " +
          (value ? "bg-navy-500" : "bg-ink-300")
        }
      >
        <span
          className={
            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform " +
            (value ? "translate-x-4" : "translate-x-0.5")
          }
        />
      </button>
    </div>
  );
}

function ActionRow({
  title,
  description,
  buttonLabel,
  soon,
  disabled = false,
}: {
  title: string;
  description: string;
  buttonLabel: string;
  soon?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-4 border-b border-ink-100">
      <div className="flex-1">
        <div className="text-sm font-medium text-ink-900">{title}</div>
        <div className="text-xs text-ink-500 mt-0.5 max-w-xl">{description}</div>
      </div>
      <button
        type="button"
        disabled={disabled}
        title={disabled ? soon : undefined}
        className={
          "px-4 py-2 rounded-md border text-sm transition-colors " +
          (disabled
            ? "border-ink-200 text-ink-400 cursor-not-allowed"
            : "border-ink-300 text-ink-800 hover:bg-ink-50")
        }
      >
        {buttonLabel}
      </button>
    </div>
  );
}
