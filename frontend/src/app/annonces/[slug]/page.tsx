import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Clock } from "lucide-react";
import { ANNONCES, getAnnonceBySlug } from "@/data/annonces";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export function generateStaticParams() {
  return ANNONCES.map((a) => ({ slug: a.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const annonce = getAnnonceBySlug(slug);
  if (!annonce) return { title: "Annonce" };
  return {
    title: annonce.title,
    description: annonce.summary,
  };
}

export default async function AnnoncePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const annonce = getAnnonceBySlug(slug);
  if (!annonce) notFound();

  // Trouver l'annonce suivante (même type) pour CTA bas
  const sameKind = ANNONCES.filter((a) => a.kind === annonce.kind);
  const idx = sameKind.findIndex((a) => a.slug === annonce.slug);
  const next = sameKind[(idx + 1) % sameKind.length];
  const isReleased = annonce.kind === "release";

  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        {/* En-tête éditorial */}
        <section className="border-b border-border-default">
          <div className="container-vitrine pt-16 md:pt-24 pb-12 max-w-3xl">
            <Link
              href={isReleased ? "/#sorties" : "/#sorties"}
              className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary mb-10"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Toutes les annonces
            </Link>

            <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-text-muted mb-5">
              <span className="text-accent-primary font-semibold">
                {annonce.category}
              </span>
              <span aria-hidden>·</span>
              <span>{annonce.dateLabel}</span>
              <span aria-hidden>·</span>
              <span className="inline-flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {annonce.readTime} de lecture
              </span>
            </div>

            <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-3xl md:text-5xl font-bold mb-6">
              {annonce.title}
            </h1>
            <p className="text-lg md:text-xl text-text-secondary leading-relaxed">
              {annonce.summary}
            </p>
          </div>
        </section>

        {/* Corps de l'annonce */}
        <article className="container-vitrine py-16 md:py-20 max-w-3xl">
          {annonce.sections.map((section, i) => (
            <section key={i} className="mb-12 last:mb-0">
              <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary leading-tight mb-5">
                {section.title}
              </h2>
              <div className="space-y-4 text-[16px] text-text-secondary leading-[1.75]">
                {section.paragraphs.map((p, j) => (
                  <p key={j}>{p}</p>
                ))}
              </div>
              {section.bullets && section.bullets.length > 0 && (
                <ul className="mt-5 space-y-2.5">
                  {section.bullets.map((b, k) => (
                    <li
                      key={k}
                      className="flex items-start gap-3 text-[15px] text-text-secondary leading-relaxed"
                    >
                      <span className="mt-2 w-1 h-1 rounded-full bg-accent-primary shrink-0" />
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </article>

        {/* CTA contextuel */}
        <section className="bg-surface-inverse text-text-inverse">
          <div className="container-vitrine py-16 md:py-20 max-w-3xl">
            <div className="grid md:grid-cols-12 gap-8 items-center">
              <div className="md:col-span-7">
                <div className="text-2xs uppercase tracking-widest text-text-inverse/50 mb-2">
                  {isReleased ? "Lire l'annonce suivante" : "Une autre feature à venir"}
                </div>
                <h3 className="font-serif text-xl md:text-2xl font-semibold leading-tight">
                  {next.title}
                </h3>
                <p className="mt-3 text-sm text-text-inverse/70 leading-relaxed">
                  {next.summary}
                </p>
              </div>
              <div className="md:col-span-5 flex md:justify-end">
                <Link
                  href={`/annonces/${next.slug}`}
                  className="inline-flex items-center gap-2 px-5 py-3 bg-accent-primary text-accent-primary-fg text-sm font-medium rounded-md hover:bg-accent-primary-hover transition-colors group"
                >
                  Lire l&apos;annonce
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Try CTA */}
        <section>
          <div className="container-vitrine py-16 md:py-20 max-w-3xl text-center">
            <h2 className="font-serif text-2xl md:text-3xl font-semibold text-text-primary tracking-tight mb-3">
              Prêt à essayer FinSight ?
            </h2>
            <p className="text-text-muted mb-7">
              Le plan Découverte est gratuit. Trois analyses suffisent pour juger.
            </p>
            <Link href="/app" className="btn-cta">
              Lancer une analyse
              <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Link>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}
