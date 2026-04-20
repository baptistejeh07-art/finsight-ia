"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  useUserPreferences,
  SUPPORTED_CURRENCIES,
  SUPPORTED_LANGUAGES,
} from "@/hooks/use-user-preferences";
import type {
  Theme,
  BackgroundAnimation,
  Font,
  LogoSize,
  Currency,
  Language,
} from "@/hooks/use-user-preferences";

const LOGO_SIZES: { value: LogoSize; label: string; px: string }[] = [
  { value: "sm", label: "Petit", px: "32 px" },
  { value: "md", label: "Moyen", px: "48 px" },
  { value: "lg", label: "Grand", px: "64 px" },
  { value: "xl", label: "Très grand", px: "96 px" },
  { value: "2xl", label: "Énorme", px: "128 px" },
  { value: "3xl", label: "Maximum", px: "160 px" },
];

const PROFESSIONS = [
  "Étudiant",
  "Analyste financier",
  "Gestionnaire de fonds",
  "Conseiller en gestion de patrimoine",
  "Expert-comptable",
  "Dirigeant / CFO",
  "Investisseur particulier",
  "Journaliste économique",
  "Chercheur",
  "Autre",
];

export default function GeneralPage() {
  const { prefs, update, loading } = useUserPreferences();
  const [email, setEmail] = useState<string>("");

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email || ""));
  }, []);

  if (loading) {
    return <div className="text-sm text-ink-500">Chargement…</div>;
  }

  const initial = ((prefs.nickname || prefs.full_name || email)[0] || "?").toUpperCase();

  return (
    <div className="space-y-10 max-w-3xl">
      {/* === Profil === */}
      <section>
        <h2 className="text-lg font-semibold text-ink-900 mb-5">Profil</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm text-ink-700 mb-1.5">Nom complet</label>
            <div className="flex items-center gap-2">
              <span className="shrink-0 w-10 h-10 rounded-full bg-ink-900 text-white font-semibold text-sm flex items-center justify-center">
                {initial}
              </span>
              <input
                type="text"
                value={prefs.full_name}
                onChange={(e) => update({ full_name: e.target.value })}
                placeholder="Votre nom"
                className="flex-1 px-3 py-2 border border-ink-200 rounded-md text-sm focus:outline-none focus:border-navy-500 bg-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-ink-700 mb-1.5">
              Comment souhaitez-vous que FinSight vous appelle&nbsp;? *
            </label>
            <input
              type="text"
              value={prefs.nickname}
              onChange={(e) => update({ nickname: e.target.value })}
              placeholder="Votre prénom"
              className="w-full px-3 py-2 border border-ink-200 rounded-md text-sm focus:outline-none focus:border-navy-500 bg-white"
            />
          </div>
        </div>

        <div className="mt-5">
          <label className="block text-sm text-ink-700 mb-1.5">
            Quelle est la meilleure description de votre travail&nbsp;?
          </label>
          <select
            value={prefs.profession}
            onChange={(e) => update({ profession: e.target.value })}
            className="w-full px-3 py-2 border border-ink-200 rounded-md text-sm focus:outline-none focus:border-navy-500 bg-white"
          >
            <option value="">Sélectionnez votre fonction professionnelle</option>
            {PROFESSIONS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        <div className="mt-5">
          <label className="block text-sm text-ink-700 mb-1">
            Quelles <span className="underline">préférences personnelles</span> FinSight
            doit-il prendre en compte dans ses réponses&nbsp;?
          </label>
          <p className="text-xs text-ink-500 mb-2">
            Vos préférences s&apos;appliqueront à toutes les analyses.
          </p>
          <textarea
            value={prefs.llm_preferences}
            onChange={(e) => update({ llm_preferences: e.target.value })}
            placeholder="ex. : garder les explications brèves et précises"
            rows={4}
            className="w-full px-3 py-2 border border-ink-200 rounded-md text-sm focus:outline-none focus:border-navy-500 bg-white resize-none"
          />
        </div>

        <div className="mt-6 flex items-start justify-between gap-4 py-4 border-t border-ink-100">
          <div className="flex-1">
            <div className="text-sm font-medium text-ink-900">Tour guidé</div>
            <div className="text-xs text-ink-500 mt-0.5 max-w-xl">
              Revoyez la présentation rapide de FinSight (4 étapes, ~30 secondes).
            </div>
          </div>
          <button
            type="button"
            onClick={() => update({ onboarded: false })}
            className="px-4 py-2 rounded-md border border-ink-300 text-sm text-ink-800 hover:bg-ink-50 transition-colors"
          >
            Relancer
          </button>
        </div>

        <div className="mt-6 flex items-start justify-between gap-4 py-4 border-t border-ink-100">
          <div className="flex-1">
            <div className="text-sm font-medium text-ink-900">Mode explicatif</div>
            <div className="text-xs text-ink-500 mt-0.5 max-w-xl">
              Quand activé, l&apos;assistant Q&amp;R définit en langage simple chaque
              ratio ou concept financier qu&apos;il mentionne (P/E, EV/EBITDA, WACC,
              FCF…). Pratique pour les débutants ou pour partager une analyse à un
              non-initié.
            </div>
          </div>
          <button
            type="button"
            onClick={() => update({ explanatory_mode: !prefs.explanatory_mode })}
            role="switch"
            aria-checked={prefs.explanatory_mode}
            className={
              "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors mt-0.5 " +
              (prefs.explanatory_mode ? "bg-navy-500" : "bg-ink-300")
            }
          >
            <span
              className={
                "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform " +
                (prefs.explanatory_mode ? "translate-x-4" : "translate-x-0.5")
              }
            />
          </button>
        </div>
      </section>

      {/* === Notifications === */}
      <section className="border-t border-ink-200 pt-8">
        <h2 className="text-lg font-semibold text-ink-900 mb-5">Notifications</h2>

        <ToggleRow
          title="Complétion d'analyse"
          description="Recevez une notification quand FinSight termine l'analyse d'une société, un secteur ou un indice."
          value={prefs.notifications.completion}
          onChange={(v) => update({ notifications: { ...prefs.notifications, completion: v } })}
        />
        <ToggleRow
          title="E-mails de rapports"
          description="Recevez un e-mail hebdomadaire récapitulant vos analyses."
          value={prefs.notifications.email_reports}
          onChange={(v) => update({ notifications: { ...prefs.notifications, email_reports: v } })}
        />
        <ToggleRow
          title="Messages push"
          description="Recevez une notification push sur votre navigateur pour les événements importants."
          value={prefs.notifications.push_messages}
          onChange={(v) => update({ notifications: { ...prefs.notifications, push_messages: v } })}
        />
      </section>

      {/* === Internationalisation (devise + langue) === */}
      <section className="border-t border-ink-200 pt-8">
        <h2 className="text-lg font-semibold text-ink-900 mb-5">Internationalisation</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl mb-8">
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-2">
              Devise d&apos;affichage
            </label>
            <select
              value={prefs.currency}
              onChange={(e) => update({ currency: e.target.value as Currency })}
              className="w-full px-3 py-2 border border-ink-200 rounded-md text-sm focus:outline-none focus:border-navy-500"
            >
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.symbol} — {c.label} ({c.code})
                </option>
              ))}
            </select>
            <p className="text-xs text-ink-500 mt-1.5">
              Devise utilisée dans tous les tableaux, graphiques et rapports.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink-700 mb-2">
              Langue
            </label>
            <select
              value={prefs.language}
              onChange={(e) => update({ language: e.target.value as Language })}
              className="w-full px-3 py-2 border border-ink-200 rounded-md text-sm focus:outline-none focus:border-navy-500"
            >
              {SUPPORTED_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.native} ({l.label})
                </option>
              ))}
            </select>
            <p className="text-xs text-ink-500 mt-1.5">
              Langue de l&apos;interface, des commentaires IA et des rapports.
            </p>
          </div>
        </div>
      </section>

      {/* === Apparence === */}
      <section className="border-t border-ink-200 pt-8">
        <h2 className="text-lg font-semibold text-ink-900 mb-5">Apparence</h2>
        <p className="text-sm text-ink-600 mb-4">Thème</p>

        <div className="grid grid-cols-3 gap-3 mb-8 max-w-md">
          <ThemeCard
            label="Clair"
            active={prefs.theme === "light"}
            onClick={() => update({ theme: "light" as Theme })}
            variant="light"
          />
          <ThemeCard
            label="Auto"
            active={prefs.theme === "auto"}
            onClick={() => update({ theme: "auto" as Theme })}
            variant="auto"
          />
          <ThemeCard
            label="Sombre"
            active={prefs.theme === "dark"}
            onClick={() => update({ theme: "dark" as Theme })}
            variant="dark"
          />
        </div>

        <p className="text-sm text-ink-600 mb-4">Animation d&apos;arrière-plan</p>
        <div className="grid grid-cols-3 gap-3 mb-8 max-w-md">
          <AnimCard
            label="Activé"
            active={prefs.background_animation === "on"}
            onClick={() => update({ background_animation: "on" as BackgroundAnimation })}
            dots={3}
          />
          <AnimCard
            label="Auto"
            active={prefs.background_animation === "auto"}
            onClick={() => update({ background_animation: "auto" as BackgroundAnimation })}
            dots={2}
          />
          <AnimCard
            label="Désactivé"
            active={prefs.background_animation === "off"}
            onClick={() => update({ background_animation: "off" as BackgroundAnimation })}
            dots={3}
            muted
          />
        </div>

        <p className="text-sm text-ink-600 mb-4">Police d&apos;affichage</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-2xl mb-8">
          <FontCard label="Par défaut" active={prefs.font === "default"} onClick={() => update({ font: "default" as Font })} />
          <FontCard label="Sans" active={prefs.font === "sans"} onClick={() => update({ font: "sans" as Font })} />
          <FontCard label="Système" active={prefs.font === "system"} onClick={() => update({ font: "system" as Font })} />
          <FontCard label="Adapté aux dyslexiques" active={prefs.font === "dyslexia"} onClick={() => update({ font: "dyslexia" as Font })} />
        </div>

        {/* === Taille du logo === */}
        <p className="text-sm text-ink-600 mb-2">Taille du logo</p>
        <p className="text-xs text-ink-500 mb-4">
          Ajustez la taille du logo FinSight affiché dans la barre de navigation et le pied de page.
          L&apos;aperçu se met à jour instantanément.
        </p>
        <div className="flex items-center gap-4 max-w-xl">
          <input
            type="range"
            min="0"
            max="5"
            step="1"
            value={LOGO_SIZES.findIndex((s) => s.value === prefs.logo_size)}
            onChange={(e) => {
              const idx = parseInt(e.target.value, 10);
              update({ logo_size: LOGO_SIZES[idx].value });
            }}
            className="flex-1 accent-navy-500"
          />
          <div className="text-sm font-medium text-ink-800 min-w-[110px]">
            {LOGO_SIZES.find((s) => s.value === prefs.logo_size)?.label}
            <span className="text-xs text-ink-500 ml-1">
              ({LOGO_SIZES.find((s) => s.value === prefs.logo_size)?.px})
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-2 max-w-xl text-[10px] text-ink-400 uppercase tracking-wider">
          {LOGO_SIZES.map((s) => (
            <button
              key={s.value}
              type="button"
              onClick={() => update({ logo_size: s.value })}
              className={
                "flex-1 text-center hover:text-ink-700 transition-colors " +
                (prefs.logo_size === s.value ? "text-navy-500 font-semibold" : "")
              }
            >
              {s.value}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

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

function ThemeCard({
  label,
  active,
  onClick,
  variant,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  variant: "light" | "auto" | "dark";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all " +
        (active ? "border-navy-500 ring-2 ring-navy-500/20" : "border-ink-200 hover:border-ink-300")
      }
    >
      <div className={
        "w-full h-14 rounded-md overflow-hidden flex " +
        (variant === "light" ? "bg-[#FAFAF5]" : variant === "dark" ? "bg-[#1B2A4A]" : "bg-gradient-to-r from-[#FAFAF5] to-[#1B2A4A]")
      }>
        <div className="flex-1 p-1.5">
          <div className={"h-1.5 w-full rounded " + (variant === "dark" ? "bg-white/20" : "bg-ink-300/40")} />
          <div className={"h-1.5 w-1/2 rounded mt-1 " + (variant === "dark" ? "bg-white/20" : "bg-ink-300/40")} />
        </div>
      </div>
      <span className="text-sm text-ink-800">{label}</span>
    </button>
  );
}

function AnimCard({
  label,
  active,
  onClick,
  dots = 3,
  muted = false,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  dots?: number;
  muted?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all " +
        (active ? "border-navy-500 ring-2 ring-navy-500/20" : "border-ink-200 hover:border-ink-300")
      }
    >
      <div className="w-full h-14 rounded-md bg-[#FAFAF5] flex items-center justify-center gap-1.5">
        {Array.from({ length: dots }).map((_, i) => (
          <span
            key={i}
            className={
              "w-1.5 h-1.5 rounded-full " +
              (muted ? "bg-ink-300" : "bg-ink-500")
            }
            style={!muted && active ? { animation: `pulse 1.4s ease-in-out ${i * 0.2}s infinite` } : {}}
          />
        ))}
      </div>
      <span className="text-sm text-ink-800">{label}</span>
    </button>
  );
}

function FontCard({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all " +
        (active ? "border-navy-500 ring-2 ring-navy-500/20" : "border-ink-200 hover:border-ink-300")
      }
    >
      <div className="w-full h-14 rounded-md bg-[#FAFAF5] flex items-center justify-center">
        <span className="text-3xl font-semibold text-ink-800">Aa</span>
      </div>
      <span className="text-xs text-ink-800 text-center leading-tight">{label}</span>
    </button>
  );
}
