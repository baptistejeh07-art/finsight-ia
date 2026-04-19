"use client";

import Link from "next/link";
import { Shield } from "lucide-react";
import { useUserPreferences } from "@/hooks/use-user-preferences";

export default function ConfidentialitePage() {
  const { prefs, update, loading } = useUserPreferences();

  if (loading) return <div className="text-sm text-ink-500">Chargement…</div>;

  return (
    <div className="space-y-10 max-w-3xl">
      {/* === Header sécurité === */}
      <section>
        <div className="flex items-start gap-3 mb-4">
          <div className="shrink-0 w-10 h-10 rounded-md bg-ink-100 flex items-center justify-center">
            <Shield className="w-5 h-5 text-ink-700" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-ink-900">Confidentialité</h2>
            <p className="text-sm text-ink-600">
              FinSight IA s&apos;engage pour la transparence des pratiques en matière de données.
            </p>
          </div>
        </div>

        <p className="text-sm text-ink-700 leading-relaxed">
          Découvrez comment vos informations sont protégées lors de l&apos;utilisation de FinSight.{" "}
          Consultez notre{" "}
          <Link href="/privacy" className="text-navy-500 underline">
            Politique de confidentialité
          </Link>{" "}
          et nos{" "}
          <Link href="/securite" className="text-navy-500 underline">
            pratiques de sécurité
          </Link>{" "}
          pour plus de détails.
        </p>

        <div className="mt-5 space-y-2">
          <Link href="/privacy" className="block text-sm text-ink-700 hover:text-navy-500">
            Comment nous protégeons vos données ›
          </Link>
          <Link href="/privacy" className="block text-sm text-ink-700 hover:text-navy-500">
            Comment nous utilisons vos données ›
          </Link>
        </div>
      </section>

      {/* === Paramètres === */}
      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-5">Paramètres de confidentialité</h3>

        <ActionRow
          title="Exporter les données"
          description="Téléchargez une archive de toutes vos analyses et préférences."
          buttonLabel="Exporter les données"
          disabled
        />
        <ActionRow
          title="Préférences de mémoire"
          description="Gérez ce que FinSight retient de vos précédentes analyses."
          buttonLabel="Gérer"
          disabled
        />

        <ToggleRow
          title="Métadonnées de localisation"
          description="Autoriser FinSight à utiliser les métadonnées de localisation approximative (ville/région) pour adapter les analyses aux indices/secteurs locaux."
          value={prefs.privacy.location_metadata}
          onChange={(v) => update({ privacy: { ...prefs.privacy, location_metadata: v } })}
        />
        <ToggleRow
          title="Aider à améliorer FinSight"
          description="Autoriser l'utilisation de vos analyses (anonymisées) pour entraîner et améliorer les modèles d'IA de FinSight."
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
  disabled = false,
}: {
  title: string;
  description: string;
  buttonLabel: string;
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
        title={disabled ? "Bientôt disponible" : undefined}
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
