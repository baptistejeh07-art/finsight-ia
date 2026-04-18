import Link from "next/link";

export function Hero() {
  return (
    <section className="bg-surface-muted border-b border-border-default">
      <div className="container-vitrine py-20 md:py-28 grid grid-cols-1 md:grid-cols-12 gap-10 md:gap-16 items-end">
        <div className="md:col-span-8 animate-fade-in">
          <h1 className="font-serif text-text-primary leading-[1.05] tracking-tight text-[2.4rem] sm:text-5xl md:text-6xl font-bold">
            Votre propre{" "}
            <Link href="/analyste" className="underline-link">
              analyste
            </Link>
            ,
            <br />
            où que vous soyez,
            <br />
            quand vous en avez besoin.
          </h1>
        </div>

        <div className="md:col-span-4 md:pb-3 animate-slide-up">
          <p className="text-sm md:text-[15px] text-text-secondary leading-relaxed">
            FinSight livre des analyses financières de niveau institutionnel —
            DCF, ratios, scénarios, comparables — sur n&apos;importe quelle
            société cotée, secteur ou indice. Récupérez votre rapport PDF,
            pitchbook PowerPoint et modèle Excel en quelques minutes.
          </p>
        </div>
      </div>
    </section>
  );
}
