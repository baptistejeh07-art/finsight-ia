import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { UPCOMING_FEATURED } from "@/data/annonces";
import { ReleaseCard } from "./release-card";

export function UpcomingFeatures() {
  return (
    <section className="bg-surface-muted border-y border-border-default">
      <div className="container-vitrine py-20 md:py-24">
        <div className="flex items-end justify-between mb-10 gap-6">
          <div>
            <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
              Prochainement
            </h2>
            <p className="hidden md:block text-sm text-text-muted mt-1">
              Ce que nous préparons pour les mois à venir.
            </p>
          </div>
          <Link
            href="/roadmap"
            className="hidden md:inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary transition-colors group shrink-0"
          >
            Voir la roadmap complète
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {UPCOMING_FEATURED.map((a) => (
            <ReleaseCard key={a.slug} annonce={a} />
          ))}
        </div>
      </div>
    </section>
  );
}
