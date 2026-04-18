import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { CAS_CATEGORIES, CAS_ROLES } from "@/data/cas-usage";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export const metadata: Metadata = {
  title: "Cas d'utilisation",
  description:
    "Comment des analystes, gérants, CFO, étudiants et investisseurs particuliers utilisent FinSight au quotidien.",
};

export default function CasUsagePage() {
  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="container-vitrine pt-20 md:pt-28 pb-16 max-w-4xl">
          <div className="label-vitrine mb-5">Cas d&apos;utilisation</div>
          <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-4xl md:text-6xl font-bold">
            Un outil. Dix usages.
            <br />
            <span className="text-text-muted">Le vôtre y est forcément.</span>
          </h1>
          <p className="mt-8 text-lg text-text-secondary leading-relaxed">
            FinSight s&apos;adapte à votre métier — du junior en banque
            d&apos;investissement à l&apos;étudiant en master finance, du CFO
            de PME au gérant de fonds. Voici comment.
          </p>
        </section>

        {/* Catégories */}
        <section className="bg-surface-muted border-y border-border-default">
          <div className="container-vitrine py-20 md:py-24 max-w-6xl">
            <div className="mb-10">
              <div className="label-vitrine mb-3">Par catégorie</div>
              <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                Quel est votre terrain ?
              </h2>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {CAS_CATEGORIES.map((c) => (
                <CasCard
                  key={c.slug}
                  href={`/cas-usage/${c.slug}`}
                  title={c.title}
                  short={c.short}
                />
              ))}
            </div>
          </div>
        </section>

        {/* Rôles */}
        <section>
          <div className="container-vitrine py-20 md:py-24 max-w-6xl">
            <div className="mb-10">
              <div className="label-vitrine mb-3">Par rôle</div>
              <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary">
                Quel est votre métier ?
              </h2>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {CAS_ROLES.map((c) => (
                <CasCard
                  key={c.slug}
                  href={`/cas-usage/${c.slug}`}
                  title={c.title}
                  short={c.short}
                />
              ))}
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}

function CasCard({
  href,
  title,
  short,
}: {
  href: string;
  title: string;
  short: string;
}) {
  return (
    <Link
      href={href}
      className="card-vitrine group hover:border-border-strong transition-all"
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-base font-semibold text-text-primary group-hover:text-accent-primary transition-colors">
          {title}
        </h3>
        <ArrowUpRight className="w-4 h-4 text-text-muted group-hover:text-accent-primary transition-colors shrink-0" />
      </div>
      <p className="text-sm text-text-muted leading-relaxed">{short}</p>
    </Link>
  );
}
