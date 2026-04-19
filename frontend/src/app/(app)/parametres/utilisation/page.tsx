export default function UtilisationPage() {
  // Données placeholder tant que le système de quotas n'est pas branché.
  const usage = [
    { label: "Analyses société (LTM)", used: 4, total: 10, reset: "Réinitialisation dans 22 j" },
    { label: "Analyses sectorielles", used: 1, total: 5, reset: "Réinitialisation dans 22 j" },
    { label: "Analyses indice", used: 0, total: 2, reset: "Réinitialisation dans 22 j" },
    { label: "Portraits entreprise", used: 2, total: 5, reset: "Réinitialisation dans 22 j" },
  ];

  return (
    <div className="space-y-10 max-w-3xl">
      <section>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-ink-900">Limites d&apos;utilisation du forfait</h2>
          <span className="text-xs text-ink-500">Plan Découverte</span>
        </div>
        <p className="text-sm text-ink-600 mb-6">
          Consommation actuelle sur le cycle en cours. Ces métriques seront
          connectées au système de quotas en phase bêta.
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
        <h3 className="text-base font-semibold text-ink-900 mb-2">Historique d&apos;utilisation</h3>
        <p className="text-sm text-ink-600">
          Un graphique d&apos;utilisation mensuel apparaîtra ici dès que le système
          de quotas sera connecté.
        </p>
        <div className="mt-4 py-12 text-center text-sm text-ink-400 border border-dashed border-ink-200 rounded-md">
          Graphique d&apos;utilisation — bientôt disponible
        </div>
      </section>
    </div>
  );
}
