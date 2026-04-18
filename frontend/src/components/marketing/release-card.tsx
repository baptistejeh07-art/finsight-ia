import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { Annonce } from "@/data/annonces";

export function ReleaseCard({ annonce }: { annonce: Annonce }) {
  const ctaLabel = annonce.kind === "release" ? "Lire l'annonce" : "Lire l'annonce";
  return (
    <article className="card-vitrine flex flex-col h-full hover:border-border-strong transition-colors">
      <div className="flex-1">
        <h3 className="text-lg font-semibold text-text-primary leading-snug mb-2">
          {annonce.title}
        </h3>
        <p className="text-sm text-text-muted leading-relaxed">
          {annonce.summary}
        </p>
      </div>

      <div className="mt-6 pt-4 border-t border-border-default">
        <div className="grid grid-cols-2 gap-2 mb-3 text-2xs uppercase tracking-widest text-text-muted">
          <div>
            <div className="opacity-60">Date</div>
            <div className="text-text-secondary normal-case tracking-normal text-xs mt-0.5">
              {annonce.dateLabel}
            </div>
          </div>
          <div>
            <div className="opacity-60">Catégorie</div>
            <div className="text-text-secondary normal-case tracking-normal text-xs mt-0.5">
              {annonce.category}
            </div>
          </div>
        </div>
        <Link
          href={`/annonces/${annonce.slug}`}
          className="inline-flex items-center gap-1.5 text-sm text-text-primary hover:text-accent-primary transition-colors group"
        >
          {ctaLabel}
          <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </div>
    </article>
  );
}
