import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { CAS_LIST, getCasBySlug } from "@/data/cas-usage";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export function generateStaticParams() {
  return CAS_LIST.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const cas = getCasBySlug(slug);
  if (!cas) return { title: "Cas d'utilisation" };
  return {
    title: `${cas.title} — FinSight pour ${cas.kind === "role" ? "les " : "le "}${cas.title.toLowerCase()}`,
    description: cas.short,
  };
}

export default async function CasUsageDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const cas = getCasBySlug(slug);
  if (!cas) notFound();

  return (
    <>
      <MarketingNav />

      <main className="bg-surface">
        <section className="container-vitrine pt-16 md:pt-24 pb-12 max-w-4xl">
          <Link
            href="/cas-usage"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary mb-8"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Tous les cas d&apos;utilisation
          </Link>
          <div className="label-vitrine mb-4">
            {cas.kind === "categorie" ? "Catégorie" : "Rôle"}
          </div>
          <h1 className="font-serif text-text-primary leading-[1.1] tracking-tight text-4xl md:text-5xl font-bold">
            {cas.title}
          </h1>
          <p className="mt-6 text-lg text-text-secondary leading-relaxed">
            {cas.intro}
          </p>
        </section>

        <section className="border-t border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-4xl grid md:grid-cols-12 gap-10">
            <div className="md:col-span-4">
              <div className="label-vitrine mb-3">Le problème</div>
            </div>
            <div className="md:col-span-8 text-text-secondary leading-relaxed">
              {cas.problem}
            </div>
          </div>
        </section>

        <section className="bg-surface-muted border-y border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-4xl grid md:grid-cols-12 gap-10">
            <div className="md:col-span-4">
              <div className="label-vitrine mb-3">La réponse FinSight</div>
            </div>
            <div className="md:col-span-8 text-text-secondary leading-relaxed">
              {cas.solution}
            </div>
          </div>
        </section>

        <section>
          <div className="container-vitrine py-16 md:py-20 max-w-4xl grid md:grid-cols-12 gap-10">
            <div className="md:col-span-4">
              <div className="label-vitrine mb-3">Workflow type</div>
            </div>
            <div className="md:col-span-8">
              <ol className="space-y-3">
                {cas.workflow.map((step, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-3 text-text-secondary leading-relaxed"
                  >
                    <span className="w-6 h-6 rounded-full bg-accent-primary/10 text-accent-primary text-xs font-semibold flex items-center justify-center shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <section className="bg-surface-muted border-y border-border-default">
          <div className="container-vitrine py-16 md:py-20 max-w-4xl grid md:grid-cols-12 gap-10">
            <div className="md:col-span-4">
              <div className="label-vitrine mb-3">Ce que vous récupérez</div>
            </div>
            <div className="md:col-span-8">
              <ul className="space-y-2">
                {cas.livrables.map((l) => (
                  <li
                    key={l}
                    className="flex items-center gap-2 text-text-secondary"
                  >
                    <Check className="w-4 h-4 text-accent-primary shrink-0" />
                    {l}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="bg-surface-inverse text-text-inverse">
          <div className="container-vitrine py-20 md:py-24 max-w-3xl text-center">
            <h2 className="font-serif text-3xl md:text-4xl font-semibold tracking-tight mb-4">
              Prêt à essayer ?
            </h2>
            <p className="text-text-inverse/70 mb-8">
              Le plan Découverte est gratuit. Trois analyses suffisent pour
              juger.
            </p>
            <Link
              href="/app"
              className="inline-flex items-center gap-2 px-5 py-3 bg-accent-primary text-accent-primary-fg text-sm font-medium rounded-md hover:bg-accent-primary-hover transition-colors group"
            >
              Lancer une analyse
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}
