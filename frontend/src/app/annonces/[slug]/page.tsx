import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ANNONCES, getAnnonceBySlug } from "@/data/annonces";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { MarketingFooter } from "@/components/marketing/marketing-footer";

export function generateStaticParams() {
  return ANNONCES.map((a) => ({ slug: a.slug }));
}

export default async function AnnoncePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const annonce = getAnnonceBySlug(slug);
  if (!annonce) notFound();

  return (
    <>
      <MarketingNav />
      <main className="container-vitrine py-16 md:py-24 max-w-3xl">
        <Link
          href="/#sorties"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary mb-8"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Toutes les annonces
        </Link>
        <div className="text-2xs uppercase tracking-widest text-text-muted mb-3">
          {annonce.category} · {annonce.dateLabel}
        </div>
        <h1 className="font-serif text-3xl md:text-5xl font-bold text-text-primary leading-tight mb-6">
          {annonce.title}
        </h1>
        <p className="text-lg text-text-secondary leading-relaxed mb-8">
          {annonce.summary}
        </p>
        <div className="text-base text-text-primary leading-relaxed">
          {annonce.body}
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
