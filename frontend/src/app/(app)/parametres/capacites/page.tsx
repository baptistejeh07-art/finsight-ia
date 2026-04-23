"use client";

import Link from "next/link";
import { useUserPreferences } from "@/hooks/use-user-preferences";
import type { ToolsMode } from "@/hooks/use-user-preferences";
import { useI18n } from "@/i18n/provider";

export default function CapacitesPage() {
  const { prefs, update, loading } = useUserPreferences();
  const { t } = useI18n();

  if (loading) return <div className="text-sm text-ink-500">{t("common.loading")}</div>;

  return (
    <div className="space-y-10 max-w-3xl">
      {/* === Mémoire === */}
      <section>
        <h2 className="text-lg font-semibold text-ink-900 mb-5">{t("settings.cap_memory_title")}</h2>

        <ToggleRow
          title={t("settings.cap_memory_search_title")}
          description={t("settings.cap_memory_search_desc")}
          value={prefs.capabilities.memory_search}
          onChange={(v) => update({ capabilities: { ...prefs.capabilities, memory_search: v } })}
        />
        <ToggleRow
          title={t("settings.cap_memory_gen_title")}
          description={t("settings.cap_memory_gen_desc")}
          value={prefs.capabilities.memory_generate}
          onChange={(v) => update({ capabilities: { ...prefs.capabilities, memory_generate: v } })}
        />

        <div className="mt-6 p-4 rounded-md border border-ink-200 bg-ink-50/50">
          <div className="text-sm font-medium text-ink-900 mb-1">{t("settings.cap_memory_box_title")}</div>
          <div className="text-xs text-ink-500 mb-3 leading-relaxed">{t("settings.cap_memory_box_empty")}</div>
          <Link
            href="/dashboard"
            className="inline-block px-3 py-1.5 rounded-md border border-ink-300 text-xs text-ink-700 hover:border-navy-500 hover:text-navy-500 transition-colors"
          >
            {t("settings.cap_memory_manage")}
          </Link>
        </div>
      </section>

      {/* === Accès aux outils === */}
      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-2">{t("settings.cap_tools_title")}</h3>
        <p className="text-sm text-ink-600 mb-5 max-w-xl">
          {t("settings.cap_tools_intro")}
        </p>

        <div className="space-y-3">
          <RadioCard
            active={prefs.capabilities.tools_mode === "on_demand"}
            onClick={() => update({ capabilities: { ...prefs.capabilities, tools_mode: "on_demand" as ToolsMode } })}
            title={t("settings.cap_tools_on_demand_title")}
            description={t("settings.cap_tools_on_demand_desc")}
          />
          <RadioCard
            active={prefs.capabilities.tools_mode === "preloaded"}
            onClick={() => update({ capabilities: { ...prefs.capabilities, tools_mode: "preloaded" as ToolsMode } })}
            title={t("settings.cap_tools_preloaded_title")}
            description={t("settings.cap_tools_preloaded_desc")}
          />
        </div>
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

function RadioCard({
  active,
  onClick,
  title,
  description,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "w-full text-left p-4 rounded-md border-2 transition-all flex items-start gap-3 " +
        (active ? "border-navy-500 bg-navy-50/30" : "border-ink-200 hover:border-ink-300")
      }
    >
      <span
        className={
          "mt-0.5 shrink-0 w-4 h-4 rounded-full border-2 flex items-center justify-center " +
          (active ? "border-navy-500" : "border-ink-300")
        }
      >
        {active && <span className="w-2 h-2 rounded-full bg-navy-500" />}
      </span>
      <span className="flex-1">
        <span className="block text-sm font-medium text-ink-900">{title}</span>
        <span className="block text-xs text-ink-500 mt-0.5">{description}</span>
      </span>
    </button>
  );
}
