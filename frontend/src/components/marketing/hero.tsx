import Link from "next/link";

export function Hero() {
  return (
    <section className="bg-surface-muted border-b border-border-default">
      <div className="container-vitrine py-20 md:py-28 grid grid-cols-1 md:grid-cols-12 gap-10 md:gap-16 items-end">
        <div className="md:col-span-8 animate-fade-in">
          <h1 className="font-serif text-text-primary leading-[1.05] tracking-tight text-[2.2rem] sm:text-[2.8rem] md:text-[3.5rem] font-bold">
            L&apos;
            <Link href="/analyste" className="underline-link">
              analyse institutionnelle
            </Link>
            ,
            <br />
            enfin accessible.
          </h1>
        </div>

        <div className="md:col-span-4 md:pb-3 animate-slide-up">
          <p className="text-base md:text-[17px] text-text-secondary leading-relaxed">
            FinSight livre des analyses financières structurées — DCF, ratios,
            scénarios, comparables — sur n&apos;importe quelle société cotée,
            PME française, secteur ou indice. Rapport PDF, pitchbook PowerPoint
            et modèle Excel en 60 secondes. Score propriétaire validé
            statistiquement sur backtest sp100 10 ans.
          </p>
        </div>
      </div>
    </section>
  );
}
