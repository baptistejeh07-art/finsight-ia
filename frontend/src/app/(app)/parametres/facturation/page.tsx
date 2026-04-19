"use client";

import { CreditCard, Sparkles } from "lucide-react";

export default function FacturationPage() {
  return (
    <div className="space-y-10 max-w-3xl">
      {/* === Plan actuel === */}
      <section>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="shrink-0 w-12 h-12 rounded-md bg-navy-50 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-navy-500" />
            </div>
            <div>
              <div className="text-base font-semibold text-ink-900">Plan Découverte</div>
              <div className="text-xs text-ink-500 mt-0.5">
                3 analyses par mois incluses · Facturation à venir
              </div>
              <div className="text-xs text-ink-400 mt-0.5">
                La facturation sera activée en phase bêta ouverte.
              </div>
            </div>
          </div>
          <button
            type="button"
            disabled
            className="px-4 py-2 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed"
            title="Bientôt disponible"
          >
            Modifier l&apos;abonnement
          </button>
        </div>
      </section>

      {/* === Paiement === */}
      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-5">Paiement</h3>
        <div className="flex items-center justify-between py-4 border border-ink-200 rounded-md px-4">
          <div className="flex items-center gap-3 text-sm text-ink-500">
            <CreditCard className="w-5 h-5 text-ink-400" />
            <span>Aucune méthode de paiement enregistrée</span>
          </div>
          <button
            type="button"
            disabled
            className="px-4 py-1.5 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed"
          >
            Ajouter
          </button>
        </div>
      </section>

      {/* === Usage supplémentaire === */}
      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-2">Usage supplémentaire</h3>
        <p className="text-sm text-ink-600 mb-5 max-w-xl">
          Achetez des analyses supplémentaires pour dépasser votre quota mensuel.
          Disponible à l&apos;ouverture de la facturation.
        </p>
        <div className="flex items-center justify-between py-4 border border-ink-200 rounded-md px-4">
          <div>
            <div className="text-sm font-mono text-ink-900">0,00 €</div>
            <div className="text-xs text-ink-500 mt-0.5">Solde actuel</div>
          </div>
          <button
            type="button"
            disabled
            className="px-4 py-1.5 rounded-md border border-ink-200 text-sm text-ink-400 cursor-not-allowed"
          >
            Acheter
          </button>
        </div>
      </section>

      {/* === Factures === */}
      <section className="border-t border-ink-200 pt-8">
        <h3 className="text-base font-semibold text-ink-900 mb-5">Factures</h3>
        <div className="py-8 text-center text-sm text-ink-500 border border-dashed border-ink-200 rounded-md">
          Aucune facture — vous n&apos;avez pas encore été facturé.
        </div>
      </section>
    </div>
  );
}
