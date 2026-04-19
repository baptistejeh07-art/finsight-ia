"use client";

import { Building2, FileSpreadsheet, Database, Plus } from "lucide-react";

const CONNECTEURS = [
  {
    id: "pennylane",
    name: "Pennylane",
    description: "Connectez votre comptabilité Pennylane pour importer vos écritures et états financiers.",
    status: "coming_soon" as const,
    icon: Building2,
  },
  {
    id: "sage",
    name: "Sage",
    description: "Importez vos FEC et balances Sage directement dans vos analyses.",
    status: "coming_soon" as const,
    icon: FileSpreadsheet,
  },
  {
    id: "fec",
    name: "Fichier FEC",
    description: "Import manuel d'un Fichier des Écritures Comptables (format FEC).",
    status: "coming_soon" as const,
    icon: Database,
  },
];

export default function ConnecteursPage() {
  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <h2 className="text-lg font-semibold text-ink-900 mb-2">Connecteurs</h2>
        <p className="text-sm text-ink-600 mb-6 max-w-xl">
          Connectez votre logiciel de comptabilité pour que FinSight analyse vos
          comptes réels (P&L, bilan, flux de trésorerie) en plus des données de marché.
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
                      Bientôt
                    </span>
                  </div>
                  <p className="text-xs text-ink-500 leading-relaxed">{c.description}</p>
                </div>
                <button
                  type="button"
                  disabled
                  className="px-4 py-2 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed shrink-0"
                >
                  Connecter
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
          Ajouter un connecteur personnalisé
        </button>
      </section>

      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-2">
          Pourquoi des connecteurs&nbsp;?
        </h3>
        <p className="text-sm text-ink-600 leading-relaxed max-w-2xl">
          Les connecteurs comptables permettront à FinSight de croiser vos données
          internes (CA réel, marges, trésorerie) avec les données publiques de marché.
          Idéal pour les experts-comptables, CGP et dirigeants de PME/ETI qui veulent
          un audit de leur positionnement sectoriel.
        </p>
      </section>
    </div>
  );
}
