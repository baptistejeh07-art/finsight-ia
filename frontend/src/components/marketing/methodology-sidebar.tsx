"use client";

import { useEffect, useState } from "react";

interface SectionLink {
  id: string;
  label: string;
  number: string;
}

const SECTIONS: SectionLink[] = [
  { number: "01", id: "pipeline",     label: "Pipeline LangGraph" },
  { number: "02", id: "gouvernance",  label: "Gouvernance IA" },
  { number: "03", id: "sources",      label: "Sources de données" },
  { number: "04", id: "score",        label: "Score FinSight" },
  { number: "05", id: "backtest",     label: "Backtest walk-forward" },
  { number: "06", id: "limites",      label: "Limites et biais" },
  { number: "07", id: "profils",      label: "Profils sectoriels" },
  { number: "08", id: "stack",        label: "Stack technique" },
  { number: "09", id: "choix",        label: "Choix de conception" },
  { number: "10", id: "securite",     label: "Sécurité et RGPD" },
  { number: "11", id: "roadmap",      label: "Roadmap" },
];

export function MethodologySidebar() {
  const [activeId, setActiveId] = useState<string>("pipeline");

  useEffect(() => {
    const handler = () => {
      const scrollY = window.scrollY + 180;
      let current = SECTIONS[0].id;
      for (const s of SECTIONS) {
        const el = document.getElementById(s.id);
        if (el && el.offsetTop <= scrollY) {
          current = s.id;
        }
      }
      setActiveId(current);
    };
    handler();
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return (
    <aside className="hidden lg:block w-60 shrink-0">
      <nav className="sticky top-24">
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-text-secondary mb-4">
          Sommaire
        </div>
        <ul className="space-y-1">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                className={
                  "flex items-baseline gap-2 text-sm py-1.5 px-2 rounded transition-colors " +
                  (activeId === s.id
                    ? "text-text-primary font-semibold bg-surface-muted"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface-muted")
                }
              >
                <span className="font-mono text-[10px] text-text-tertiary w-5 shrink-0">{s.number}</span>
                <span>{s.label}</span>
              </a>
            </li>
          ))}
        </ul>
        <div className="mt-6 pt-4 border-t border-border-default text-xs text-text-secondary leading-relaxed">
          Documentation technique maintenue en continu. Des questions&nbsp;?{" "}
          <a href="mailto:baptiste.jeh07@gmail.com" className="text-text-primary underline underline-offset-2">
            Écrire au fondateur
          </a>
        </div>
      </nav>
    </aside>
  );
}
