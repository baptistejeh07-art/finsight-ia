import Link from "next/link";
import { ArrowRight, FileText, Presentation, FileSpreadsheet } from "lucide-react";

const TITLE = "D'autres résument.\nNous livrons un pitchbook.";
const PARA =
  "Sept agents spécialisés — collecte de données, calculs déterministes, synthèse, contradiction, gouvernance — convergent sur une analyse auditable. Chaque chiffre est sourcé, chaque hypothèse documentée, chaque livrable prêt pour comité.";

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
            <div className="text-xs font-semibold tracking-widest uppercase text-text-inverse">
              ✦  La pile FinSight
            </div>

            <h3 className="text-2xl md:text-3xl font-semibold leading-tight">
              {TITLE.split("\n").map((line, i, arr) => (
                <span key={i}>
                  {line}
                  {i < arr.length - 1 && <br />}
                </span>
              ))}
            </h3>

            <p className="text-sm md:text-[15px] text-text-inverse/75 leading-relaxed max-w-md">
              {PARA}
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

      {/* PDF — derrière à gauche (statique) */}
      <StaticCard translate="left-2 top-6" z="z-10" rotate="-rotate-6">
        <MockCardContent
          icon={<FileText className="w-3.5 h-3.5" />}
          label="Rapport PDF"
          meta="20 pages · DCF · Scénarios"
        />
      </StaticCard>

      {/* Excel — milieu droit (statique) */}
      <StaticCard translate="right-4 top-2" z="z-20" rotate="rotate-3">
        <MockCardContent
          icon={<FileSpreadsheet className="w-3.5 h-3.5" />}
          label="Modèle Excel"
          meta="Inputs · DCF · Comparables · Sensibilités"
        />
      </StaticCard>

      {/* PPTX — devant centre (statique) */}
      <StaticCard
        translate="left-1/2 -translate-x-1/2 top-24"
        z="z-30"
        rotate="-rotate-2"
        big
      >
        <MockCardContent
          icon={<Presentation className="w-3.5 h-3.5" />}
          label="Pitchbook PowerPoint"
          meta="20 slides · format Bloomberg"
        />
      </StaticCard>
    </div>
  );
}

function StaticCard({
  children,
  translate,
  z,
  rotate,
  big = false,
}: {
  children: React.ReactNode;
  translate: string;
  z: string;
  rotate: string;
  big?: boolean;
}) {
  return (
    <div
      className={`absolute ${translate} ${z} ${rotate} ${
        big ? "w-72 h-64" : "w-60 h-52"
      } rounded-xl bg-white/95 dark:bg-surface-elevated border border-white/10 shadow-2xl shadow-black/40 p-4 flex flex-col`}
    >
      {children}
    </div>
  );
}

function MockCardContent({
  icon,
  label,
  meta,
}: {
  icon: React.ReactNode;
  label: string;
  meta: string;
}) {
  return (
    <>
      <div className="flex items-center gap-2 text-text-primary">
        <span className="w-7 h-7 rounded-md bg-accent-primary/10 text-accent-primary flex items-center justify-center">
          {icon}
        </span>
        <span className="text-sm font-semibold">{label}</span>
      </div>
      <div className="mt-2 text-xs text-text-muted">{meta}</div>
      <div className="mt-4 flex-1 space-y-1.5">
        <div className="h-1.5 rounded bg-text-primary/10 w-full" />
        <div className="h-1.5 rounded bg-text-primary/10 w-5/6" />
        <div className="h-1.5 rounded bg-text-primary/10 w-4/6" />
        <div className="h-1.5 rounded bg-text-primary/10 w-full" />
        <div className="h-1.5 rounded bg-text-primary/10 w-3/4" />
      </div>
    </>
  );
}
