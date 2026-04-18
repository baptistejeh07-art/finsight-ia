import { UPCOMING } from "@/data/annonces";
import { ReleaseCard } from "./release-card";

export function UpcomingFeatures() {
  return (
    <section className="bg-surface-muted border-y border-border-default">
      <div className="container-vitrine py-20 md:py-24">
        <div className="flex items-end justify-between mb-10">
          <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
            Prochainement
          </h2>
          <p className="hidden md:block text-sm text-text-muted">
            Ce que nous préparons pour les mois à venir.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {UPCOMING.map((a) => (
            <ReleaseCard key={a.slug} annonce={a} />
          ))}
        </div>
      </div>
    </section>
  );
}
