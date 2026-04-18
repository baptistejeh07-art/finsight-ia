import { RELEASES } from "@/data/annonces";
import { ReleaseCard } from "./release-card";

export function LatestReleases() {
  return (
    <section className="bg-surface">
      <div className="container-vitrine py-20 md:py-24">
        <div className="flex items-end justify-between mb-10">
          <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
            Dernières sorties
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {RELEASES.map((a) => (
            <ReleaseCard key={a.slug} annonce={a} />
          ))}
        </div>
      </div>
    </section>
  );
}
