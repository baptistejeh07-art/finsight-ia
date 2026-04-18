"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
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

            <TypewriterTitle text={TITLE} />
            <TypewriterParagraph text={PARA} />

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

/**
 * Typewriter qui s'écrit caractère par caractère quand l'élément
 * entre dans le viewport. Une seule fois.
 */
function useTypewriter(text: string, speed = 22) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const id = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) clearInterval(id);
    }, speed);
    return () => clearInterval(id);
  }, [inView, text, speed]);

  return { ref, displayed, done: displayed.length === text.length };
}

function TypewriterTitle({ text }: { text: string }) {
  const { ref, displayed, done } = useTypewriter(text, 35);
  return (
    <h3
      ref={ref}
      className="text-2xl md:text-3xl font-semibold leading-tight min-h-[5rem]"
    >
      {displayed.split("\n").map((line, i, arr) => (
        <span key={i}>
          {line}
          {i < arr.length - 1 && <br />}
        </span>
      ))}
      {!done && <span className="inline-block w-[2px] h-[1em] bg-text-inverse/70 align-middle ml-1 animate-pulse" />}
    </h3>
  );
}

function TypewriterParagraph({ text }: { text: string }) {
  const { ref, displayed, done } = useTypewriter(text, 12);
  return (
    <p
      ref={ref}
      className="text-sm md:text-[15px] text-text-inverse/75 leading-relaxed max-w-md min-h-[6rem]"
    >
      {displayed}
      {!done && <span className="inline-block w-[2px] h-[1em] bg-text-inverse/70 align-middle ml-0.5 animate-pulse" />}
    </p>
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

      {/* PDF — derrière à gauche, oscille (haut/droite -> bas/gauche) */}
      <FloatingCard
        translate="left-2 top-6"
        z="z-10"
        rotate="-rotate-6"
        floatY={[-6, 4, -6]}
        floatX={[0, 4, 0]}
        delay={0}
      >
        <MockCardContent
          icon={<FileText className="w-3.5 h-3.5" />}
          label="Rapport PDF"
          meta="20 pages · DCF · Scénarios"
        />
      </FloatingCard>

      {/* Excel — milieu droit, oscille (haut/gauche -> bas/droite) */}
      <FloatingCard
        translate="right-4 top-2"
        z="z-20"
        rotate="rotate-3"
        floatY={[-5, 5, -5]}
        floatX={[0, -3, 0]}
        delay={1.2}
      >
        <MockCardContent
          icon={<FileSpreadsheet className="w-3.5 h-3.5" />}
          label="Modèle Excel"
          meta="Inputs · DCF · Comparables · Sensibilités"
        />
      </FloatingCard>

      {/* PPTX — devant centre, monte/descend doucement */}
      <FloatingCard
        translate="left-1/2 -translate-x-1/2 top-24"
        z="z-30"
        rotate="-rotate-2"
        floatY={[-8, 6, -8]}
        floatX={[0, 0, 0]}
        delay={0.6}
        big
      >
        <MockCardContent
          icon={<Presentation className="w-3.5 h-3.5" />}
          label="Pitchbook PowerPoint"
          meta="20 slides · format Bloomberg"
        />
      </FloatingCard>
    </div>
  );
}

function FloatingCard({
  children,
  translate,
  z,
  rotate,
  floatY,
  floatX,
  delay,
  big = false,
}: {
  children: React.ReactNode;
  translate: string;
  z: string;
  rotate: string;
  floatY: number[];
  floatX: number[];
  delay: number;
  big?: boolean;
}) {
  return (
    <motion.div
      initial={{ y: floatY[0], x: floatX[0] }}
      animate={{ y: floatY, x: floatX }}
      transition={{
        duration: 5.5,
        ease: "easeInOut",
        repeat: Infinity,
        delay,
      }}
      className={`absolute ${translate} ${z} ${rotate} ${
        big ? "w-72 h-64" : "w-60 h-52"
      } rounded-xl bg-white/95 dark:bg-surface-elevated border border-white/10 shadow-2xl shadow-black/40 p-4 flex flex-col`}
    >
      {children}
    </motion.div>
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
        <div className="flex-1">
          <div className="text-xs font-semibold leading-tight">{label}</div>
          <div className="text-[10px] text-text-muted">{meta}</div>
        </div>
      </div>
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
    </>
  );
}
