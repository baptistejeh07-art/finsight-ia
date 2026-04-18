import Link from "next/link";
import { ArrowRight, FileText, Presentation, FileSpreadsheet } from "lucide-react";

export function StackSection() {
  return (
    <section className="bg-surface-inverse text-text-inverse">
      <div className="container-vitrine py-24 md:py-32">
        <h2 className="font-serif text-center text-3xl md:text-5xl font-bold tracking-tight leading-[1.1] max-w-4xl mx-auto">
          Pour obtenir des résultats différents,
          <br />
          il faut une pile différente.
        </h2>

        <div className="mt-16 grid grid-cols-1 md:grid-cols-12 gap-12 md:gap-16 items-center">
          <div className="md:col-span-5 space-y-6">
            <div className="text-xs font-semibold tracking-widest uppercase text-accent-primary">
              ✦  La pile FinSight
            </div>
            <h3 className="text-2xl md:text-3xl font-semibold leading-tight">
              D&apos;autres résument.
              <br />
              Nous livrons un pitchbook.
            </h3>
            <p className="text-sm md:text-[15px] text-text-inverse/75 leading-relaxed max-w-md">
              Sept agents spécialisés — collecte de données, calculs déterministes,
              synthèse, contradiction, gouvernance — convergent sur une analyse
              auditable. Chaque chiffre est sourcé, chaque hypothèse documentée,
              chaque livrable prêt pour comité.
            </p>
            <Link
              href="/analyste"
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent-primary text-accent-primary-fg text-sm font-medium rounded-md hover:bg-accent-primary-hover transition-colors group"
            >
              En savoir plus
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>

          <div className="md:col-span-7">
            <PitchbookMockup />
          </div>
        </div>
      </div>
    </section>
  );
}

function PitchbookMockup() {
  return (
    <div className="relative h-[360px] md:h-[420px]">
      {/* Glow */}
      <div
        aria-hidden
        className="absolute inset-0 rounded-3xl opacity-40 blur-3xl"
        style={{
          background:
            "radial-gradient(60% 60% at 50% 50%, rgb(var(--accent-primary)/0.6), transparent 70%)",
        }}
      />

      {/* PDF — derrière à gauche */}
      <MockCard
        icon={<FileText className="w-3.5 h-3.5" />}
        label="Rapport PDF"
        meta="20 pages · DCF · Scénarios"
        rotate="-rotate-6"
        translate="left-2 top-6"
        z="z-10"
      />
      {/* Excel — milieu */}
      <MockCard
        icon={<FileSpreadsheet className="w-3.5 h-3.5" />}
        label="Modèle Excel"
        meta="Inputs · DCF · Comparables · Sensibilités"
        rotate="rotate-3"
        translate="right-4 top-2"
        z="z-20"
      />
      {/* PPTX — devant centre */}
      <MockCard
        icon={<Presentation className="w-3.5 h-3.5" />}
        label="Pitchbook PowerPoint"
        meta="20 slides · format Bloomberg"
        rotate="-rotate-2"
        translate="left-1/2 -translate-x-1/2 top-24"
        z="z-30"
        big
      />
    </div>
  );
}

function MockCard({
  icon,
  label,
  meta,
  rotate,
  translate,
  z,
  big = false,
}: {
  icon: React.ReactNode;
  label: string;
  meta: string;
  rotate: string;
  translate: string;
  z: string;
  big?: boolean;
}) {
  return (
    <div
      className={`absolute ${translate} ${z} ${rotate} ${
        big ? "w-72 h-64" : "w-60 h-52"
      } rounded-xl bg-white/95 dark:bg-surface-elevated border border-white/10 shadow-2xl shadow-black/40 p-4 flex flex-col`}
    >
      <div className="flex items-center gap-2 text-text-primary">
        <span className="w-7 h-7 rounded-md bg-accent-primary/10 text-accent-primary flex items-center justify-center">
          {icon}
        </span>
        <div className="flex-1">
          <div className="text-xs font-semibold leading-tight">{label}</div>
          <div className="text-[10px] text-text-muted">{meta}</div>
        </div>
      </div>
      {/* fake content lines */}
      <div className="flex-1 mt-4 space-y-2">
        <div className="h-1.5 rounded bg-text-muted/20 w-full" />
        <div className="h-1.5 rounded bg-text-muted/20 w-5/6" />
        <div className="h-1.5 rounded bg-text-muted/20 w-4/6" />
        <div className="mt-3 grid grid-cols-3 gap-1.5">
          <div className="h-12 rounded bg-accent-primary/15" />
          <div className="h-12 rounded bg-accent-primary/30" />
          <div className="h-12 rounded bg-accent-primary/45" />
        </div>
      </div>
    </div>
  );
}
